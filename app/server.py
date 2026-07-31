"""FastAPI-server: serveert de webinterface en koppelt die via een WebSocket
aan de BLE-schaakarm en de Stockfish-engine."""

import asyncio
import json
import logging
import re
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .ble_manager import BleManager
from .engine import Engine
from .game import GameState
from .i18n import DEFAULT_LANGUAGE, tr
from . import pgn_store
from .version import get_version

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
PENDING_SCAN_TIMEOUT_S = 30.0
MAX_PGN_CHARS = 200_000

app = FastAPI(title="CYNUS schaakarm interface")


class AppState:
    def __init__(self):
        self.clients: set[WebSocket] = set()
        self.engine = Engine()
        self.game = GameState(turn=self.engine.settings.get("turn", "b"))
        self.ble = BleManager(
            on_fen=self.on_fen,
            on_get_move=self.on_get_move,
            on_rx=self.on_rx,
            on_disconnect=self.on_ble_disconnect,
        )
        self.auto_mode = True
        self.language = DEFAULT_LANGUAGE
        self.last_fen: str | None = None
        self.robot_connected = False
        # human_color: kleur van de speler tegen de arm ("w" of "b")
        self.human_color = "w"
        # Wacht op een nieuwe FEN na expliciete bordsync/kleurwissel.
        self.pending_scan_sync = False
        # Bij de eerstvolgende scan-sync de zettenlijst behouden (replay).
        self.pending_scan_keep_history = False
        # Wacht op een FEN voor een losse controlevergelijking na echte bordscan.
        self.pending_check = False
        # Controle na robotzet: scan zonder app-stelling te overschrijven.
        self.pending_verify_after_move = False
        self._verify_fen_future: asyncio.Future | None = None
        self._status_futures: list[asyncio.Future] = []
        self._pending_timeout_task: asyncio.Task | None = None
        self._pending_timeout_token = 0
        self.robot_move_busy = False
        # Na scan-mismatch: eerstvolgende get move van de arm negeren.
        self._suppress_next_get_move = False
        self.ponder_fen: str | None = None
        self.ponder_task: asyncio.Task | None = None
        self.ponder_result: dict | None = None
        self.replay_auto_task: asyncio.Task | None = None
        self.replay_auto_running = False
        self.replay_auto_interval = 10.0
        # Arms scherm: toon_text + auto-clear
        self._display_clear_task: asyncio.Task | None = None
        self._display_retry_task: asyncio.Task | None = None
        self._last_displayed_turn: str | None = None

    # -- broadcast ----------------------------------------------------------

    async def broadcast(self, message: dict) -> None:
        dead = []
        for ws in self.clients:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    async def log(self, direction: str, text: str) -> None:
        """direction: 'rx', 'tx' of 'info'."""
        await self.broadcast({"type": "log", "dir": direction, "text": text})

    def msg(self, key: str, **params) -> str:
        """Vertaal een consolemelding naar de ingestelde taal."""
        return tr(self.language, key, **params)

    def pgn_player_names(self) -> tuple[str, str]:
        stockfish_name = f'Stockfish ({self.engine.settings.get("elo", "?")})'
        player_name = tr(self.language, "player_name")
        if self.human_color == "w":
            return player_name, stockfish_name
        return stockfish_name, player_name

    def persist_pgn_current(self) -> None:
        white_name, black_name = self.pgn_player_names()
        pgn_store.save_current(self.game, white_name=white_name, black_name=black_name)

    async def archive_pgn_if_needed(self) -> None:
        white_name, black_name = self.pgn_player_names()
        path = pgn_store.archive_current(
            self.game, white_name=white_name, black_name=black_name
        )
        if path is not None:
            await self.log("info", self.msg("pgn_archived", file=path.name))

    def status_message(self) -> dict:
        return {
            "type": "status",
            "connected": self.robot_connected,
            "name": self.ble.device_name,
            "address": self.ble.device_address,
            "version": get_version(),
        }

    def engine_message(self) -> dict:
        return {
            "type": "engine",
            "available": self.engine.available,
            "settings": self.engine.settings,
            "error": self.engine.error,
            "path": self.engine.path,
        }

    def board_message(self) -> dict:
        return self.game.render(orientation=self.human_color)

    def orient_board_payload(self, payload: dict) -> dict:
        oriented = dict(payload)
        oriented["svg"] = self.game.render(orientation=self.human_color)["svg"]
        return oriented

    def side_message(self) -> dict:
        robot = "b" if self.human_color == "w" else "w"
        return {
            "type": "side",
            "human": self.human_color,
            "robot": robot,
            "flip": "off" if self.human_color == "w" else "on",
        }

    async def require_robot_connection(self, action: str) -> bool:
        connected = self.robot_connected and self.ble.connected
        if connected:
            self.robot_connected = True
            return True
        if self.robot_connected and not self.ble.connected:
            self.robot_connected = False
        await self.log("info", self.msg("no_connection", action=self.msg(action)))
        await self.broadcast(self.status_message())
        return False

    def cancel_pending_timeout(self) -> None:
        if self._pending_timeout_task and not self._pending_timeout_task.done():
            self._pending_timeout_task.cancel()
        self._pending_timeout_task = None

    def arm_pending_timeout(self, kind: str) -> None:
        """Start een timeout voor pending_scan_sync of pending_check."""
        self.cancel_pending_timeout()
        self._pending_timeout_token += 1
        token = self._pending_timeout_token

        async def run() -> None:
            try:
                await asyncio.sleep(PENDING_SCAN_TIMEOUT_S)
            except asyncio.CancelledError:
                raise
            if token != self._pending_timeout_token:
                return
            if kind == "scan" and self.pending_scan_sync:
                self.pending_scan_sync = False
                self.pending_scan_keep_history = False
                await self.log("info", self.msg("pending_scan_timeout"))
            elif kind == "check" and self.pending_check:
                self.pending_check = False
                await self.log("info", self.msg("pending_check_timeout"))

        try:
            self._pending_timeout_task = asyncio.create_task(run())
        except RuntimeError:
            # Geen lopende event loop bij constructie/tests.
            self._pending_timeout_task = None

    def clear_pending_scan(self) -> None:
        self.pending_scan_sync = False
        self.pending_scan_keep_history = False
        if not self.pending_check:
            self.cancel_pending_timeout()

    def clear_pending_check(self) -> None:
        self.pending_check = False
        if not self.pending_scan_sync:
            self.cancel_pending_timeout()

    def analysis_fen(self) -> str:
        """Volledige FEN voor Stockfish: bordstaat als bekend, anders last_fen."""
        if self.game.has_position:
            return self.game.board.fen()
        placement = self.last_fen or "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
        return self.engine.full_fen(placement)

    def cancel_ponder(self) -> None:
        if self.ponder_task and not self.ponder_task.done():
            self.ponder_task.cancel()
        self.ponder_task = None
        self.ponder_fen = None
        self.ponder_result = None

    async def start_ponder(self, fen: str | None = None) -> None:
        if not self.auto_mode or not self.engine.available:
            return
        if self.pending_scan_sync or self.pending_check or self.pending_verify_after_move:
            return
        if self.game.replay_active or self.robot_move_busy:
            return
        fen = fen or self.analysis_fen()
        if self.ponder_fen == fen and self.ponder_task and not self.ponder_task.done():
            return
        self.cancel_ponder()
        self.ponder_fen = fen

        async def run() -> None:
            try:
                result = await asyncio.to_thread(self.engine.analyze, fen)
                if self.ponder_fen == fen:
                    self.ponder_result = result
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug("Pondering mislukt: %s", exc)

        self.ponder_task = asyncio.create_task(run())

    # -- BLE-callbacks --------------------------------------------------------

    async def on_rx(self, text: str) -> None:
        cleaned = text.rstrip("\r\n")
        await self.log("rx", cleaned)
        status = self._parse_robot_status(cleaned)
        if status is not None:
            for fut in list(self._status_futures):
                if not fut.done():
                    fut.set_result(status)
        if cleaned.strip().lower() == "new game":
            await self.start_new_game(notify_arm=False)

    @staticmethod
    def _parse_robot_status(text: str) -> str | None:
        match = re.match(r"robot is (\w+)", text.strip().lower())
        return match.group(1) if match else None

    async def start_new_game(self, *, notify_arm: bool = False) -> None:
        """Reset partij in de app; optioneel ook new game naar de arm."""
        await self.archive_pgn_if_needed()
        self.cancel_ponder()
        await self.stop_replay_auto(log_stop=False)
        self.clear_pending_scan()
        self.clear_pending_check()
        self.pending_verify_after_move = False
        self._suppress_next_get_move = False
        if self._verify_fen_future and not self._verify_fen_future.done():
            self._verify_fen_future.cancel()
        self._verify_fen_future = None
        self.game.reset()
        self.game.set_turn(self.engine.settings.get("turn", "b"))
        self.last_fen = None
        self._last_displayed_turn = None
        await self.log("info", self.msg("new_game"))
        await self.broadcast(self.board_message())
        await self.broadcast(self.game.replay_state())
        await self.broadcast({
            "type": "engine_move",
            "move": "",
            "fen": None,
            "candidates": [],
            "full_fen": None,
        })
        if notify_arm and self.robot_connected and self.ble.connected:
            await self.send_to_arm("new game")
        elif notify_arm:
            await self.log("info", self.msg("new_game_local_only"))
        if self.robot_connected and self.ble.connected:
            await self.toon_aan_zet(for_turn="w")

    async def on_fen(self, fen: str) -> None:
        if self.pending_verify_after_move:
            scanned = fen.strip().split()[0]
            fut = self._verify_fen_future
            if fut is not None and not fut.done():
                fut.set_result(scanned)
            return

        if self.pending_check:
            self.clear_pending_check()
            current = self.game.board.board_fen() if self.game.has_position else (
                self.last_fen or "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
            )
            check_ok = fen.strip() == current.strip()
            if check_ok:
                await self.log("info", self.msg("check_ok"))
                await self.broadcast({"type": "check_result", "ok": True, "robot_fen": fen, "expected_fen": current})
            else:
                await self.log("info", self.msg("check_bad"))
                await self.broadcast({"type": "check_result", "ok": False, "robot_fen": fen, "expected_fen": current})
            await self.toon_aan_zet()
            if not check_ok:
                self.cancel_display_retry()
                self._display_retry_task = asyncio.create_task(self._toon_aan_zet_later(3.0))
            return

        if self.game.replay_active:
            # Tijdens het naspelen is het app-bord leidend: de scan van de arm
            # mag de replaystelling nooit overschrijven.
            self.last_fen = fen
            expected = self.game.board.board_fen()
            scanned = fen.strip().split()[0]
            replay_ok = scanned == expected
            if replay_ok:
                await self.broadcast({"type": "check_result", "ok": True, "robot_fen": scanned, "expected_fen": expected})
            else:
                await self.log("info", self.msg("replay_scan_mismatch"))
                await self.broadcast({"type": "check_result", "ok": False, "robot_fen": scanned, "expected_fen": expected})
            await self.toon_aan_zet()
            if not replay_ok:
                self.cancel_display_retry()
                self._display_retry_task = asyncio.create_task(self._toon_aan_zet_later(3.0))
            return

        expected_before = self.game.board.board_fen() if self.game.has_position else (
            self.last_fen or "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
        )
        scanned = fen.strip().split()[0]
        # Beginstelling wist de historie in game.py – archiveer eerst.
        if (
            scanned == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
            and self.game.has_position
            and self.game.moves_san
            and self.game.board.board_fen() != scanned
        ):
            await self.archive_pgn_if_needed()

        self.last_fen = fen
        self.cancel_ponder()
        if self.pending_scan_sync:
            keep_history = self.pending_scan_keep_history
            self.clear_pending_scan()
            payload = self.orient_board_payload(
                self.game.sync_from_scan(fen, keep_history=keep_history)
            )
            if keep_history:
                if payload.get("gap"):
                    await self.log("info", self.msg("scan_keep_gap"))
                else:
                    await self.log("info", self.msg("scan_keep_ok"))
            else:
                await self.log("info", self.msg("scan_synced"))
            await self.broadcast(payload)
            await self.toon_aan_zet()
            await self.start_ponder()
            return

        # App/Stockfish leidend: bij gap de robotstelling niet overnemen.
        payload = self.orient_board_payload(
            self.game.update_from_placement(fen, adopt_on_gap=False)
        )
        if payload.get("error"):
            await self.log("info", payload["error"])
        elif payload.get("reset") and not payload.get("last_move"):
            await self.log("info", self.msg("board_synced"))
        elif payload.get("gap"):
            await self.log("info", self.msg("board_gap"))
        elif payload.get("last_move"):
            await self.log("info", self.msg("move_detected", move=payload["last_move"]))

        had_error = bool(payload.get("error") or payload.get("gap"))
        expected_fen = (
            expected_before
            if had_error
            else (self.game.board.board_fen() if self.game.has_position else fen)
        )
        if had_error:
            # Voorkom dat een meegeleverde get move Stockfish voor de speler laat zetten.
            self._suppress_next_get_move = True
            await self.broadcast({
                "type": "check_result",
                "ok": False,
                "robot_fen": scanned,
                "expected_fen": expected_fen,
            })
            await self.log("info", self.msg("auto_check_bad"))
        else:
            self._suppress_next_get_move = False
            await self.broadcast({
                "type": "check_result",
                "ok": True,
                "robot_fen": scanned,
                "expected_fen": expected_fen,
            })

        await self.broadcast(payload)
        if payload.get("last_move"):
            await self.announce_check_state()
            self.persist_pgn_current()
        # Altijd tonen wie aan zet is – ook na error/gap (illegale zet / scanfout).
        await self.toon_aan_zet()
        if had_error:
            # Arm toont zelf vaak een error; zetbeurt kort daarna opnieuw.
            self.cancel_display_retry()
            self._display_retry_task = asyncio.create_task(self._toon_aan_zet_later(3.0))
        await self.start_ponder()

    async def on_get_move(self) -> None:
        await self.log("info", self.msg("get_move"))
        if not self.auto_mode:
            await self.log("info", self.msg("auto_mode_off_no_move"))
            return
        if self._suppress_next_get_move:
            self._suppress_next_get_move = False
            await self.log("info", self.msg("get_move_after_mismatch"))
            return
        if self.game.has_position and not self._is_robot_turn():
            await self.log("info", self.msg("not_robot_turn"))
            await self.toon_aan_zet()
            return
        await self.play_robot_move(reason="reason.get_move")

    def _is_robot_turn(self) -> bool:
        """True als de robotkleur (tegenover human_color) aan zet is."""
        if not self.game.has_position:
            return False
        robot = "b" if self.human_color == "w" else "w"
        turn = "w" if self.game.board.turn else "b"
        return turn == robot

    def _ensure_game_position(self) -> None:
        """Zorg dat game.has_position gezet is (nodig om robotzetten lokaal te pushen)."""
        if self.game.has_position:
            return
        placement = self.last_fen or "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
        self.game.sync_from_scan(placement, keep_history=False)

    async def wait_until_arm_idle(self, timeout_s: float = 30.0) -> bool:
        """Poll get robot status tot idle (waiting/idling/sleeping) of timeout."""
        idle = {"waiting", "idling", "sleeping"}
        busy = {"moving", "scanning", "thinking", "upgrading", "starting"}
        deadline = asyncio.get_running_loop().time() + timeout_s
        while asyncio.get_running_loop().time() < deadline:
            if not (self.robot_connected and self.ble.connected):
                return False
            fut: asyncio.Future = asyncio.get_running_loop().create_future()
            self._status_futures.append(fut)
            try:
                await self.send_to_arm("get robot status")
                status = await asyncio.wait_for(fut, timeout=2.5)
            except (asyncio.TimeoutError, RuntimeError):
                status = None
            finally:
                if fut in self._status_futures:
                    self._status_futures.remove(fut)
            if status in idle:
                return True
            if status in busy or status is None:
                await asyncio.sleep(0.6)
                continue
            # Onbekende status: kort wachten en opnieuw.
            await asyncio.sleep(0.6)
        return False

    async def request_verify_scan(self, timeout_s: float = 30.0) -> str | None:
        """scan board voor verificatie; FEN komt via on_fen → future."""
        if not (self.robot_connected and self.ble.connected):
            return None
        loop = asyncio.get_running_loop()
        self.pending_verify_after_move = True
        self._verify_fen_future = loop.create_future()
        try:
            await self.send_to_arm("scan board")
            return await asyncio.wait_for(self._verify_fen_future, timeout=timeout_s)
        except (asyncio.TimeoutError, RuntimeError):
            return None
        finally:
            self.pending_verify_after_move = False
            self._verify_fen_future = None

    async def verify_and_correct_robot_move(
        self,
        uci: str,
        piece_s: str,
        piece_t: str | None,
    ) -> None:
        """Na robotzet: scan, vergelijk met app; bij verschil één force-retry."""
        await self.log("info", self.msg("verify_started"))
        await self.wait_until_arm_idle(30.0)
        expected = self.game.board.board_fen()
        scanned = await self.request_verify_scan()
        if scanned is None:
            await self.log("info", self.msg("verify_scan_timeout"))
            await self.broadcast({
                "type": "check_result",
                "ok": False,
                "robot_fen": "",
                "expected_fen": expected,
            })
            return
        if scanned == expected:
            await self.log("info", self.msg("verify_ok"))
            await self.broadcast({
                "type": "check_result",
                "ok": True,
                "robot_fen": scanned,
                "expected_fen": expected,
            })
            self.last_fen = scanned
            return

        # Rokade: normale move opnieuw (force verplaatst alleen de koning).
        # Slag/overig: force-move met stukletters.
        uci_clean = uci.strip().lower()
        files = "abcdefgh"
        is_castle = False
        if piece_s.upper() == "K" and len(uci_clean) >= 4:
            try:
                is_castle = abs(files.index(uci_clean[0]) - files.index(uci_clean[2])) > 1
            except ValueError:
                is_castle = False
        if is_castle:
            force_cmd = f"move {uci_clean}"
        else:
            force_cmd = f"move {uci_clean} {piece_s}"
            if piece_t:
                force_cmd += f" {piece_t}"
        await self.log("info", self.msg("verify_mismatch_retry", command=force_cmd))
        await self.send_to_arm(force_cmd)
        await self.wait_until_arm_idle(30.0)
        scanned2 = await self.request_verify_scan()
        if scanned2 is None:
            await self.log("info", self.msg("verify_scan_timeout"))
            await self.broadcast({
                "type": "check_result",
                "ok": False,
                "robot_fen": scanned,
                "expected_fen": expected,
            })
            return
        if scanned2 == expected:
            await self.log("info", self.msg("verify_ok"))
            await self.broadcast({
                "type": "check_result",
                "ok": True,
                "robot_fen": scanned2,
                "expected_fen": expected,
            })
            self.last_fen = scanned2
            return

        await self.log(
            "info",
            self.msg("verify_failed", expected=expected, scanned=scanned2),
        )
        await self.broadcast({
            "type": "check_result",
            "ok": False,
            "robot_fen": scanned2,
            "expected_fen": expected,
        })
        self.cancel_display_retry()
        self._display_retry_task = asyncio.create_task(self._toon_aan_zet_later(3.0))

    async def execute_robot_uci(self, uci: str) -> bool:
        """Pas robotzet lokaal toe, stuur naar arm, verifieer. True als verstuurd.

        Alleen toegestaan als de robotkleur aan zet is (nooit voor de speler).
        """
        self._ensure_game_position()
        if not self._is_robot_turn():
            await self.log("info", self.msg("not_robot_turn"))
            return False
        piece_s, piece_t = self.game.force_move_pieces(uci)
        applied = self.game.apply_uci_move(uci)
        if not applied.get("ok"):
            await self.log(
                "info",
                self.msg("verify_apply_failed", reason=applied.get("reason", "?")),
            )
            return False

        await self.send_to_arm(f"move {uci}")
        await self.broadcast(self.board_message())
        await self.announce_check_state()
        self.persist_pgn_current()
        self.last_fen = self.game.board.board_fen()
        await self.toon_aan_zet()
        await self.verify_and_correct_robot_move(uci, piece_s, piece_t)
        await self.toon_aan_zet()
        return True

    async def play_robot_move(self, *, reason: str = "reason.manual") -> None:
        """Laat Stockfish een zet berekenen en stuur die naar de arm."""
        reason_text = self.msg(reason)
        if self.robot_move_busy:
            await self.log("info", self.msg("robot_move_busy"))
            return
        if self.game.replay_active:
            await self.log("info", self.msg("replay_active_block"))
            return
        if self.pending_scan_sync or self.pending_verify_after_move:
            await self.log("info", self.msg("wait_scan"))
            return
        self._ensure_game_position()
        if self.game.has_position and not self._is_robot_turn():
            await self.log("info", self.msg("not_robot_turn"))
            await self.toon_aan_zet()
            return
        if self.last_fen is None:
            # Geen FEN van de arm: gebruik startpositie of huidige game-stelling.
            if self.game.has_position:
                self.last_fen = self.game.board.board_fen()
            else:
                self.last_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
            await self.log("info", self.msg("no_fen_fallback"))
        if not self.engine.available:
            await self.log("info", self.msg("engine_unavailable", error=self.engine.error))
            return

        self.robot_move_busy = True
        try:
            self._ensure_game_position()
            fen = self.analysis_fen()
            result = None
            if self.ponder_fen == fen:
                if self.ponder_result is not None:
                    result = self.ponder_result
                    await self.log("info", self.msg("ponder_cache", reason=reason_text))
                elif self.ponder_task is not None:
                    await self.broadcast({"type": "engine_thinking", "fen": fen})
                    await self.log("info", self.msg("ponder_finish", reason=reason_text))
                    try:
                        await self.ponder_task
                    except asyncio.CancelledError:
                        pass
                    result = self.ponder_result

            if result is None:
                await self.broadcast({"type": "engine_thinking", "fen": fen})
                await self.log("info", self.msg("engine_analyzing", reason=reason_text))
                try:
                    result = await asyncio.to_thread(self.engine.analyze, fen)
                except (RuntimeError, ValueError) as exc:
                    await self.log("info", str(exc))
                    await self.broadcast(self.engine_message())
                    await self.toon_aan_zet()
                    return

            if not result or not result.get("move"):
                await self.log("info", self.msg("engine_no_move", fen=fen))
                await self.toon_aan_zet()
                return

            move = result["move"]
            candidates = result.get("candidates") or []
            score = candidates[0]["score"] if candidates else "?"
            await self.broadcast({
                "type": "engine_move",
                "move": move,
                "fen": fen,
                "candidates": candidates,
                "full_fen": result.get("fen"),
            })
            await self.log("info", self.msg("engine_chooses", move=move, score=score))
            await self.execute_robot_uci(move)
            self.ponder_result = None
        finally:
            self.robot_move_busy = False

    async def calculate_best_move(self) -> None:
        """Forceer een verse Stockfish-analyse voor de kleur die aan zet is."""
        if self.robot_move_busy:
            await self.log("info", self.msg("robot_move_busy"))
            return
        if not self.engine.available:
            await self.log("info", self.msg("engine_unavailable", error=self.engine.error))
            return

        # Altijd de actuele bordstelling (inclusief juiste kleur-aan-zet).
        self._ensure_game_position()
        fen = self.game.board.fen()
        turn = "w" if self.game.board.turn else "b"
        turn_name = self.msg("color.white" if turn == "w" else "color.black")

        self.cancel_ponder()
        self.robot_move_busy = True
        try:
            await self.broadcast({"type": "engine_thinking", "fen": fen})
            await self.log(
                "info",
                self.msg("engine_calculating", turn=turn_name),
            )
            try:
                result = await asyncio.to_thread(self.engine.analyze, fen)
            except (RuntimeError, ValueError) as exc:
                await self.log("info", str(exc))
                await self.broadcast(self.engine_message())
                return

            move = result["move"]
            candidates = result.get("candidates") or []
            score = candidates[0]["score"] if candidates else "?"
            await self.broadcast({
                "type": "engine_move",
                "move": move,
                "fen": fen,
                "candidates": candidates,
                "full_fen": result.get("fen"),
            })
            await self.log("info", self.msg("engine_chooses", move=move, score=score))
            if self.robot_connected and self.ble.connected:
                if self._is_robot_turn():
                    await self.execute_robot_uci(move)
                else:
                    await self.log("info", self.msg("not_robot_turn"))
            else:
                await self.log("info", self.msg("engine_calc_no_arm", move=move))
        finally:
            self.robot_move_busy = False

    async def on_ble_disconnect(self) -> None:
        self.cancel_ponder()
        self.clear_pending_scan()
        self.clear_pending_check()
        self.pending_verify_after_move = False
        if self._verify_fen_future and not self._verify_fen_future.done():
            self._verify_fen_future.cancel()
        self._verify_fen_future = None
        for fut in self._status_futures:
            if not fut.done():
                fut.cancel()
        self._status_futures.clear()
        self.cancel_display_clear()
        self.cancel_display_retry()
        self._last_displayed_turn = None
        self.robot_connected = False
        await self.log("info", self.msg("arm_disconnected"))
        await self.broadcast(self.status_message())

    # -- acties vanuit de UI --------------------------------------------------

    async def send_to_arm(self, command: str) -> None:
        try:
            await self.ble.send(command)
            await self.log("tx", command)
        except Exception as exc:
            await self.log("info", self.msg("send_failed", error=exc))

    def cancel_display_clear(self) -> None:
        if self._display_clear_task and not self._display_clear_task.done():
            self._display_clear_task.cancel()
        self._display_clear_task = None

    def cancel_display_retry(self) -> None:
        if self._display_retry_task and not self._display_retry_task.done():
            self._display_retry_task.cancel()
        self._display_retry_task = None

    async def _toon_aan_zet_later(self, delay_s: float = 3.0) -> None:
        """Opnieuw zetbeurt tonen na delay (arm-error overlay verdwijnt vaak eerst)."""
        try:
            await asyncio.sleep(delay_s)
            await self.toon_aan_zet(force=True)
        except asyncio.CancelledError:
            raise

    async def _clear_display_after(self, duration_s: float) -> None:
        try:
            await asyncio.sleep(duration_s)
            if self.robot_connected and self.ble.connected:
                await self.send_to_arm("display txt  ")
            self._last_displayed_turn = None
        except asyncio.CancelledError:
            raise

    async def toon_text(self, text: str, duration_s: float = 10.0) -> bool:
        """Toon tekst op het armscherm (max 10 tekens); wis na duration_s seconden."""
        cleaned = (text or "").strip()
        if not cleaned:
            return False
        if len(cleaned) > 10:
            await self.log("info", self.msg("display_text_too_long", length=len(cleaned)))
            return False
        if not (self.robot_connected and self.ble.connected):
            return False
        await self.send_to_arm(f"display txt {cleaned}")
        self.cancel_display_clear()
        try:
            duration = float(duration_s)
        except (TypeError, ValueError):
            duration = 10.0
        duration = max(0.5, min(300.0, duration))
        self._display_clear_task = asyncio.create_task(self._clear_display_after(duration))
        return True

    async def toon_aan_zet(
        self,
        for_turn: str | None = None,
        *,
        next_player: bool = False,
        force: bool = True,
    ) -> None:
        """Toon wie er aan zet is op het armscherm (korte Wit/Zwart-label).

        force=True (default): altijd tonen, ook bij dezelfde kleur (na error/clear).
        """
        if for_turn is None:
            if not self.game.has_position and not next_player:
                return
            current = "w" if self.game.board.turn else "b"
            for_turn = ("b" if current == "w" else "w") if next_player else current
        if for_turn not in ("w", "b"):
            return
        if not force and for_turn == self._last_displayed_turn:
            return
        label = self.msg("display.turn_white" if for_turn == "w" else "display.turn_black")
        if await self.toon_text(label):
            self._last_displayed_turn = for_turn

    async def announce_check_state(self) -> None:
        """Laat de robot 'check' of 'checkmate' uitspreken na een zet."""
        board = self.game.board
        if board.is_checkmate():
            await self.log("info", self.msg("checkmate"))
            await self.send_to_arm("play audio checkmate")
        elif board.is_check():
            await self.log("info", self.msg("check"))
            await self.send_to_arm("play audio check")

    def cancel_replay_auto(self) -> None:
        if self.replay_auto_task and not self.replay_auto_task.done():
            self.replay_auto_task.cancel()
        self.replay_auto_task = None
        self.replay_auto_running = False

    async def execute_replay_move(self) -> dict:
        """Voer één replayzet uit op bord + robot. Geeft het resultaat van replay_next terug."""
        result = self.game.replay_next()
        if not result.get("ok"):
            await self.log("info", self.msg("replay_info", reason=result.get("reason")))
            await self.broadcast(self.game.replay_state())
            return result
        await self.send_to_arm(f"move {result['uci']}")
        await self.log(
            "info",
            self.msg(
                "replay_move",
                index=result["index"],
                total=result["total"],
                san=result["san"],
                uci=result["uci"],
            ),
        )
        if result.get("done"):
            await self.log("info", self.msg("replay_done"))
        await self.broadcast(self.board_message())
        await self.broadcast(self.game.replay_state())
        await self.announce_check_state()
        await self.toon_aan_zet()
        self.persist_pgn_current()
        return result

    async def start_replay_auto(self, interval: float) -> None:
        self.cancel_replay_auto()
        self.replay_auto_interval = interval
        self.replay_auto_running = True
        await self.broadcast({
            "type": "replay_auto",
            "running": True,
            "interval": interval,
        })
        await self.log("info", self.msg("replay_auto_started", seconds=interval))

        async def run() -> None:
            try:
                while self.game.replay_active and self.replay_auto_running:
                    result = await self.execute_replay_move()
                    if not result.get("ok") or result.get("done"):
                        break
                    await asyncio.sleep(self.replay_auto_interval)
            except asyncio.CancelledError:
                raise
            finally:
                was_running = self.replay_auto_running
                self.replay_auto_running = False
                self.replay_auto_task = None
                await self.broadcast({
                    "type": "replay_auto",
                    "running": False,
                    "interval": self.replay_auto_interval,
                })
                if was_running and not self.game.replay_active:
                    await self.log("info", self.msg("replay_auto_finished"))

        self.replay_auto_task = asyncio.create_task(run())

    async def stop_replay_auto(self, *, log_stop: bool = True) -> None:
        running = self.replay_auto_running
        self.cancel_replay_auto()
        await self.broadcast({
            "type": "replay_auto",
            "running": False,
            "interval": self.replay_auto_interval,
        })
        if running and log_stop:
            await self.log("info", self.msg("replay_auto_stopped"))

    async def handle_message(self, msg: dict) -> None:
        msg_type = msg.get("type")

        if msg_type == "scan":
            await self.log("info", self.msg("scanning"))
            try:
                devices = await self.ble.scan()
            except Exception as exc:
                await self.log("info", self.msg("scan_failed", error=exc))
                devices = []
            await self.broadcast({"type": "devices", "devices": devices})
            await self.log("info", self.msg("scan_done", count=len(devices)))

        elif msg_type == "connect":
            address = str(msg.get("address", "")).strip()
            if not address:
                await self.log("info", self.msg("connect_no_address"))
                return
            await self.log("info", self.msg("connecting", address=address))
            try:
                await self.ble.connect(address)
                self.robot_connected = True
                await self.log("info", self.msg("connected", name=self.ble.device_name, address=address))
            except Exception as exc:
                self.robot_connected = False
                await self.log("info", self.msg("connect_failed", error=exc))
            await self.broadcast(self.status_message())

        elif msg_type == "disconnect":
            try:
                await self.ble.disconnect()
            except Exception as exc:
                await self.log("info", self.msg("disconnect_failed", error=exc))
            finally:
                self.robot_connected = False
                self.clear_pending_scan()
                self.clear_pending_check()
                self.cancel_ponder()
            await self.log("info", self.msg("disconnected"))
            await self.broadcast(self.status_message())

        elif msg_type == "robot_move":
            if not await self.require_robot_connection("action.robot_move"):
                return
            await self.play_robot_move(reason="reason.robot_move_button")

        elif msg_type == "calculate_move":
            await self.calculate_best_move()

        elif msg_type == "new_game":
            await self.start_new_game(notify_arm=True)

        elif msg_type == "scan_board":
            if not await self.require_robot_connection("action.scan_board"):
                return
            self.pending_scan_sync = True
            self.pending_scan_keep_history = True
            self.pending_check = False
            self.arm_pending_timeout("scan")
            # Zettenlijst blijft; alleen Nieuw spel wist historie.
            await self.send_to_arm("scan board")
            await self.log("info", self.msg("scan_board_sent"))

        elif msg_type == "check_position":
            if not await self.require_robot_connection("action.check"):
                return
            if self.pending_scan_sync:
                await self.log("info", self.msg("wait_current_scan"))
                return
            self.pending_check = True
            self.arm_pending_timeout("check")
            await self.send_to_arm("scan board")
            await self.log("info", self.msg("check_started"))

        elif msg_type == "load_pgn":
            pgn_text = str(msg.get("pgn", ""))
            if len(pgn_text) > MAX_PGN_CHARS:
                await self.log("info", self.msg("pgn_too_large", max=MAX_PGN_CHARS))
                await self.broadcast({"type": "replay_error", "reason": self.msg("pgn_too_large", max=MAX_PGN_CHARS)})
                return
            await self.archive_pgn_if_needed()
            result = self.game.load_pgn(pgn_text)
            if not result.get("ok"):
                await self.log("info", self.msg("pgn_load_failed", reason=result.get("reason")))
                await self.broadcast({"type": "replay_error", "reason": result.get("reason")})
                return
            self.cancel_ponder()
            self.last_fen = None
            self.clear_pending_scan()
            self.clear_pending_check()
            headers = result.get("headers", {})
            await self.log(
                "info",
                self.msg(
                    "pgn_loaded",
                    white=headers.get("white", "?"),
                    black=headers.get("black", "?"),
                    total=result.get("total"),
                ),
            )
            await self.broadcast(self.game.render(orientation=self.human_color, reset=True))
            await self.broadcast(self.game.replay_state())
            await self.stop_replay_auto(log_stop=False)

        elif msg_type == "replay_next":
            if not await self.require_robot_connection("action.replay_next"):
                return
            if self.replay_auto_running:
                await self.log("info", self.msg("replay_auto_busy"))
                return
            await self.execute_replay_move()

        elif msg_type == "replay_auto_start":
            if not await self.require_robot_connection("action.replay_next"):
                return
            if not self.game.replay_active:
                await self.log("info", self.msg("replay_auto_not_active"))
                return
            if self.replay_auto_running:
                await self.log("info", self.msg("replay_auto_busy"))
                return
            try:
                interval = float(msg.get("interval", 10))
            except (TypeError, ValueError):
                interval = 10.0
            interval = max(1.0, min(300.0, interval))
            await self.start_replay_auto(interval)

        elif msg_type == "replay_auto_stop":
            await self.stop_replay_auto()

        elif msg_type == "replay_stop":
            await self.stop_replay_auto(log_stop=False)
            self.game.stop_replay()
            await self.log("info", self.msg("replay_stopped"))
            await self.broadcast(self.game.replay_state())

        elif msg_type == "send_move":
            if not await self.require_robot_connection("action.send_move"):
                return
            uci = str(msg.get("move", "")).strip()
            if uci:
                validation = self.game.validate_uci_move(uci)
                if validation["ok"]:
                    await self.log("info", self.msg("move_legal", san=validation["san"], uci=uci))
                    await self.send_to_arm(f"move {uci}")
                    await self.broadcast({"type": "move_validation", "ok": True, "move": uci, "san": validation["san"]})
                else:
                    await self.log("info", self.msg("move_rejected", uci=uci, reason=validation["reason"]))
                    await self.broadcast({
                        "type": "move_validation",
                        "ok": False,
                        "move": uci,
                        "reason": validation["reason"],
                    })

        elif msg_type == "force_send_move":
            if not await self.require_robot_connection("action.force_move"):
                return
            uci = str(msg.get("move", "")).strip()
            if uci:
                await self.log("info", self.msg("move_override", uci=uci))
                await self.send_to_arm(f"move {uci}")
                await self.broadcast({"type": "move_forced", "move": uci})

        elif msg_type == "send_raw":
            if not await self.require_robot_connection("action.send_command"):
                return
            command = str(msg.get("command", "")).strip()
            if command:
                await self.send_to_arm(command)

        elif msg_type == "toon_text":
            if not await self.require_robot_connection("action.toon_text"):
                return
            text = str(msg.get("text", ""))
            duration = msg.get("duration", 10.0)
            await self.toon_text(text, duration_s=duration)

        elif msg_type == "set_side":
            human = str(msg.get("color", "w")).lower()
            if human not in ("w", "b"):
                await self.log("info", self.msg("invalid_color"))
                return
            self.human_color = human
            flip = "off" if human == "w" else "on"
            robot_turn = "b" if human == "w" else "w"
            self.engine.update_settings({"turn": robot_turn})
            self.game.set_turn(robot_turn)
            # Bordoriëntatie en UI meteen bijwerken (wit/zwart onderaan).
            await self.broadcast(self.side_message())
            await self.broadcast(self.engine_message())
            await self.broadcast(self.board_message())
            await self.log(
                "info",
                self.msg("side_set", human=human, robot=robot_turn, flip=flip),
            )
            if not await self.require_robot_connection("action.set_side"):
                return
            # Interne engine uit zodat Stockfish via deze app de zetten levert.
            await self.send_to_arm("set internal engine off")
            await self.send_to_arm(f"set flip board {flip}")
            # Na flip board altijd eerst opnieuw synchroniseren.
            self.pending_scan_sync = True
            self.pending_check = False
            self.last_fen = None
            self.arm_pending_timeout("scan")
            if self.game.replay_loaded:
                # Verder spelen na een (gedeeltelijk) nagespeelde PGN:
                # zettenlijst en stelling behouden.
                await self.stop_replay_auto(log_stop=False)
                self.game.stop_replay()
                self.pending_scan_keep_history = True
                await self.broadcast(self.game.replay_state())
            else:
                await self.archive_pgn_if_needed()
                self.game.clear_moves()
                await self.broadcast(self.game.render(orientation=self.human_color, reset=True))
            await self.send_to_arm("scan board")
            await self.log("info", self.msg("scan_after_side"))
            await self.toon_aan_zet()

        elif msg_type == "set_engine":
            try:
                settings = self.engine.update_settings(msg.get("settings", {}) or {})
            except ValueError as exc:
                await self.log("info", self.msg("engine_settings_invalid", error=exc))
                await self.broadcast(self.engine_message())
                return
            self.game.set_turn(settings.get("turn", "b"))
            await self.log("info", self.msg("engine_updated", settings=settings))
            await self.broadcast(self.engine_message())

        elif msg_type == "toggle_auto":
            self.auto_mode = bool(msg.get("enabled", True))
            await self.log("info", self.msg("auto_enabled" if self.auto_mode else "auto_disabled"))
            await self.broadcast({"type": "auto", "enabled": self.auto_mode})

        elif msg_type == "set_language":
            lang = str(msg.get("language", DEFAULT_LANGUAGE)).lower()
            if lang not in ("nl", "en"):
                lang = DEFAULT_LANGUAGE
            self.language = lang
            self.game.language = lang
            await self.log("info", self.msg("language_set"))

        else:
            await self.log("info", self.msg("unknown_type", type=msg_type))


state = AppState()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    state.clients.add(ws)
    await ws.send_text(json.dumps(state.status_message()))
    await ws.send_text(json.dumps(state.engine_message()))
    await ws.send_text(json.dumps({"type": "auto", "enabled": state.auto_mode}))
    await ws.send_text(json.dumps(state.side_message()))
    await ws.send_text(json.dumps(state.board_message()))
    await ws.send_text(json.dumps(state.game.replay_state()))
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, dict):
                continue
            try:
                await state.handle_message(msg)
            except Exception as exc:
                logger.exception("Fout bij verwerken van WebSocket-bericht: %s", exc)
                try:
                    await state.log("info", state.msg("handler_error", error=exc))
                except Exception:
                    pass
    except WebSocketDisconnect:
        pass
    finally:
        state.clients.discard(ws)


@app.get("/")
async def index():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    version = get_version()
    html = html.replace("__APP_VERSION__", version)
    html = re.sub(
        r'(id="app-version" class="app-version">)v[^<]*',
        rf"\1v{version}",
        html,
        count=1,
    )
    return Response(content=html, media_type="text/html; charset=utf-8")


@app.get("/api/version")
async def api_version():
    return {"version": get_version()}


@app.get("/download/pgn")
async def download_pgn():
    white_name, black_name = state.pgn_player_names()
    return Response(
        content=state.game.export_pgn(white_name=white_name, black_name=black_name),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="cynus-game.pgn"'},
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main():
    import os

    reload = os.environ.get("CYNUS_RELOAD", "").strip().lower() in ("1", "true", "yes")
    uvicorn.run("app.server:app", host="127.0.0.1", port=8000, loop="asyncio", reload=reload)


if __name__ == "__main__":
    main()
