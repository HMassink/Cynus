"""BLE-communicatie met de CYNUS-schaakarm.

Protocol (zie documentation/ble_stockfish2.py):
- Apparaatnaam begint met "CYNUS-" of "CMR".
- Characteristic FFF1 wordt gebruikt voor zowel notificaties als schrijven.
- Robot -> host: b"fen: <stelling>\r\n" en b"get move".
- Host -> robot: tekstcommando's afgesloten met b"\r\n", bijv. b"move e2e4\r\n".
"""

import asyncio
import logging
from typing import Awaitable, Callable, Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

logger = logging.getLogger(__name__)

# 16-bit UUID 0xFFF1 uitgeschreven als volledige 128-bit UUID.
CHAR_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
DEVICE_NAME_PREFIXES = ("CYNUS-", "CMR")
# Voorkom onbegrensde groei bij ontbrekende newlines.
_MAX_RX_BUFFER = 4096
_CONNECT_TIMEOUT_S = 20.0
_WRITE_TIMEOUT_S = 10.0

AsyncCallback = Callable[..., Awaitable[None]]


class BleManager:
    """Beheert scan, verbinding en het notify/write-protocol van de arm."""

    def __init__(
        self,
        on_fen: AsyncCallback,
        on_get_move: AsyncCallback,
        on_rx: AsyncCallback,
        on_disconnect: AsyncCallback,
    ):
        self._on_fen = on_fen
        self._on_get_move = on_get_move
        self._on_rx = on_rx
        self._on_disconnect = on_disconnect
        self._client: Optional[BleakClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._rx_buffer = bytearray()
        self.device_name: Optional[str] = None
        self.device_address: Optional[str] = None
        # Serialiseer BLE→app handlers (voorkomt races tussen fen / get move).
        self._job_queue: Optional[asyncio.Queue[Awaitable[None]]] = None
        self._worker_task: Optional[asyncio.Task] = None
        self._intentional_disconnect = False

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    async def scan(self, timeout: float = 6.0) -> list[dict]:
        devices = await BleakScanner.discover(timeout=timeout)
        found = []
        for d in devices:
            if d.name and str(d.name).startswith(DEVICE_NAME_PREFIXES):
                found.append({"name": str(d.name), "address": d.address})
        return found

    async def connect(self, address: str) -> None:
        if not address or not str(address).strip():
            raise RuntimeError("Geen BLE-adres opgegeven")
        if self.connected:
            await self.disconnect()

        device = await BleakScanner.find_device_by_address(address, timeout=10.0)
        if device is None:
            raise RuntimeError(f"Apparaat met adres {address} niet gevonden")

        self._loop = asyncio.get_running_loop()
        self._rx_buffer.clear()
        self._intentional_disconnect = False
        self._ensure_worker()
        client = BleakClient(device, disconnected_callback=self._handle_disconnect)
        await asyncio.wait_for(client.connect(), timeout=_CONNECT_TIMEOUT_S)
        await client.start_notify(CHAR_UUID, self._notification_handler)
        self._client = client
        self.device_name = device.name
        self.device_address = address

    def _ensure_worker(self) -> None:
        if self._loop is None:
            return
        if self._job_queue is None:
            self._job_queue = asyncio.Queue()
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = self._loop.create_task(self._job_worker())

    async def _job_worker(self) -> None:
        assert self._job_queue is not None
        while True:
            coro = await self._job_queue.get()
            try:
                await coro
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("BLE handler mislukt")
            finally:
                self._job_queue.task_done()

    async def disconnect(self) -> None:
        self._intentional_disconnect = True
        client = self._client
        self._client = None
        self.device_name = None
        self.device_address = None
        self._rx_buffer.clear()
        if client is not None and client.is_connected:
            try:
                await client.stop_notify(CHAR_UUID)
            except Exception as exc:
                logger.debug("BLE stop_notify: %s", exc)
            try:
                await client.disconnect()
            except Exception as exc:
                logger.debug("BLE disconnect: %s", exc)

    async def shutdown(self) -> None:
        """Verbreek verbinding en stop de handler-worker."""
        await self.disconnect()
        task = self._worker_task
        self._worker_task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._job_queue = None

    async def send(self, command: str) -> None:
        """Schrijft een tekstcommando met \r\n-afsluiting naar de arm."""
        if not self.connected:
            raise RuntimeError("Niet verbonden met de arm")
        assert self._client is not None
        await asyncio.wait_for(
            self._client.write_gatt_char(CHAR_UUID, command.encode("utf-8") + b"\r\n"),
            timeout=_WRITE_TIMEOUT_S,
        )

    # -- interne handlers ---------------------------------------------------

    def _notification_handler(self, _char: BleakGATTCharacteristic, data: bytearray) -> None:
        """Buffer notify-bytes tot volledige regels (protocol eindigt op \\n)."""
        self._rx_buffer.extend(data)
        if len(self._rx_buffer) > _MAX_RX_BUFFER:
            # Bewaar eventuele incomplete regel na laatste newline.
            nl = self._rx_buffer.rfind(b"\n")
            if nl >= 0:
                del self._rx_buffer[: nl + 1]
                logger.warning("BLE RX-buffer te groot; oude data tot laatste newline weggegooid")
            else:
                logger.warning("BLE RX-buffer te groot; buffer geleegd")
                self._rx_buffer.clear()
                return

        while True:
            nl = self._rx_buffer.find(b"\n")
            if nl < 0:
                break
            line = bytes(self._rx_buffer[:nl]).rstrip(b"\r")
            del self._rx_buffer[: nl + 1]
            if line:
                self._dispatch_line(line)

    def _dispatch_line(self, line: bytes) -> None:
        text = line.decode("utf-8", errors="replace")
        self._schedule(self._on_rx(text))

        lower = line.lower()
        if lower.startswith(b"fen:"):
            fen = line.split(b":", 1)[1].decode("utf-8", errors="replace").strip()
            if fen:
                self._schedule(self._on_fen(fen))
        elif lower.startswith(b"get move"):
            self._schedule(self._on_get_move())

    def _handle_disconnect(self, _client: BleakClient) -> None:
        logger.info("BLE-verbinding verbroken")
        self._client = None
        self.device_name = None
        self.device_address = None
        self._rx_buffer.clear()
        if self._intentional_disconnect:
            self._intentional_disconnect = False
            return
        self._schedule(self._on_disconnect())

    def _schedule(self, coro: Awaitable[None]) -> None:
        """Plant een coroutine serialiseerbaar in de BLE-jobqueue."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return

        def enqueue() -> None:
            self._ensure_worker()
            assert self._job_queue is not None
            self._job_queue.put_nowait(coro)

        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            enqueue()
        else:
            loop.call_soon_threadsafe(enqueue)
