"""FastAPI-server: serveert de webinterface en koppelt die via een WebSocket
aan de BLE-schaakarm en de Stockfish-engine."""

import asyncio
import json
import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .ble_manager import BleManager
from .engine import Engine
from .game import GameState
from .i18n import DEFAULT_LANGUAGE, tr

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

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
        self.ponder_fen: str | None = None
        self.ponder_task: asyncio.Task | None = None
        self.ponder_result: dict | None = None

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

    def status_message(self) -> dict:
        return {
            "type": "status",
            "connected": self.robot_connected,
            "name": self.ble.device_name,
            "address": self.ble.device_address,
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
        if self.robot_connected:
            return True
        await self.log("info", self.msg("no_connection", action=self.msg(action)))
        await self.broadcast(self.status_message())
        return False

    def cancel_ponder(self) -> None:
        if self.ponder_task and not self.ponder_task.done():
            self.ponder_task.cancel()
        self.ponder_task = None
        self.ponder_fen = None
        self.ponder_result = None

    async def start_ponder(self, fen: str) -> None:
        if not self.auto_mode or not self.engine.available:
            return
        if self.pending_scan_sync or self.pending_check:
            return
        if self.game.replay_active:
            return
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
        if cleaned.strip().lower() == "new game":
            self.game.reset()
            self.game.set_turn(self.engine.settings.get("turn", "b"))
            self.last_fen = None
            await self.log("info", self.msg("new_game"))
            await self.broadcast(self.board_message())
            await self.broadcast(self.game.replay_state())

    async def on_fen(self, fen: str) -> None:
        if self.pending_check:
            self.pending_check = False
            current = self.game.board.board_fen() if self.game.has_position else (
                self.last_fen or "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
            )
            if fen.strip() == current.strip():
                await self.log("info", self.msg("check_ok"))
                await self.broadcast({"type": "check_result", "ok": True, "robot_fen": fen, "expected_fen": current})
            else:
                await self.log("info", self.msg("check_bad"))
                await self.broadcast({"type": "check_result", "ok": False, "robot_fen": fen, "expected_fen": current})
            return

        if self.game.replay_active:
            # Tijdens het naspelen is het app-bord leidend: de scan van de arm
            # mag de replaystelling nooit overschrijven.
            self.last_fen = fen
            expected = self.game.board.board_fen()
            scanned = fen.strip().split()[0]
            if scanned == expected:
                await self.broadcast({"type": "check_result", "ok": True, "robot_fen": scanned, "expected_fen": expected})
            else:
                await self.log("info", self.msg("replay_scan_mismatch"))
                await self.broadcast({"type": "check_result", "ok": False, "robot_fen": scanned, "expected_fen": expected})
            return

        expected_before = self.game.board.board_fen() if self.game.has_position else (
            self.last_fen or "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
        )
        self.last_fen = fen
        self.cancel_ponder()
        if self.pending_scan_sync:
            self.pending_scan_sync = False
            keep_history = self.pending_scan_keep_history
            self.pending_scan_keep_history = False
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
            await self.start_ponder(fen)
            return

        payload = self.orient_board_payload(self.game.update_from_placement(fen))
        if payload.get("error"):
            await self.log("info", payload["error"])
        elif payload.get("reset") and not payload.get("last_move"):
            await self.log("info", self.msg("board_synced"))
        elif payload.get("gap"):
            await self.log("info", self.msg("board_gap"))
        elif payload.get("last_move"):
            await self.log("info", self.msg("move_detected", move=payload["last_move"]))

        if payload.get("error") or payload.get("gap"):
            await self.broadcast({
                "type": "check_result",
                "ok": False,
                "robot_fen": fen,
                "expected_fen": expected_before,
            })
            await self.log("info", self.msg("auto_check_bad"))
        else:
            await self.broadcast({
                "type": "check_result",
                "ok": True,
                "robot_fen": fen,
                "expected_fen": fen,
            })

        await self.broadcast(payload)
        if payload.get("last_move"):
            await self.announce_check_state()
        await self.start_ponder(fen)

    async def on_get_move(self) -> None:
        await self.log("info", self.msg("get_move"))
        if not self.auto_mode:
            await self.log("info", self.msg("auto_mode_off_no_move"))
            return
        await self.play_robot_move(reason="reason.get_move")

    async def play_robot_move(self, *, reason: str = "reason.manual") -> None:
        """Laat Stockfish een zet berekenen en stuur die naar de arm."""
        reason_text = self.msg(reason)
        if self.game.replay_active:
            await self.log("info", self.msg("replay_active_block"))
            return
        if self.pending_scan_sync:
            await self.log("info", self.msg("wait_scan"))
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
        fen = self.last_fen
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
            except RuntimeError as exc:
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
        await self.send_to_arm(f"move {move}")
        self.ponder_result = None

    async def on_ble_disconnect(self) -> None:
        self.cancel_ponder()
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

    async def announce_check_state(self) -> None:
        """Laat de robot 'check' of 'checkmate' uitspreken na een zet."""
        board = self.game.board
        if board.is_checkmate():
            await self.log("info", self.msg("checkmate"))
            await self.send_to_arm("play audio checkmate")
        elif board.is_check():
            await self.log("info", self.msg("check"))
            await self.send_to_arm("play audio check")

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
            address = msg.get("address", "")
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
            await self.ble.disconnect()
            self.robot_connected = False
            await self.log("info", self.msg("disconnected"))
            await self.broadcast(self.status_message())

        elif msg_type == "robot_move":
            if not await self.require_robot_connection("action.robot_move"):
                return
            await self.play_robot_move(reason="reason.robot_move_button")

        elif msg_type == "scan_board":
            if not await self.require_robot_connection("action.scan_board"):
                return
            self.pending_scan_sync = True
            # Zettenlijst meteen leegmaken; bord volgt na de FEN van de arm.
            self.game.clear_moves()
            if self.game.replay_loaded:
                self.game.clear_replay()
                await self.broadcast(self.game.replay_state())
            await self.broadcast(self.game.render(orientation=self.human_color, reset=True))
            await self.send_to_arm("scan board")
            await self.log("info", self.msg("scan_board_sent"))

        elif msg_type == "check_position":
            if not await self.require_robot_connection("action.check"):
                return
            if self.pending_scan_sync:
                await self.log("info", self.msg("wait_current_scan"))
                return
            self.pending_check = True
            await self.send_to_arm("scan board")
            await self.log("info", self.msg("check_started"))

        elif msg_type == "load_pgn":
            result = self.game.load_pgn(str(msg.get("pgn", "")))
            if not result.get("ok"):
                await self.log("info", self.msg("pgn_load_failed", reason=result.get("reason")))
                await self.broadcast({"type": "replay_error", "reason": result.get("reason")})
                return
            self.cancel_ponder()
            self.last_fen = None
            self.pending_scan_sync = False
            self.pending_scan_keep_history = False
            self.pending_check = False
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

        elif msg_type == "replay_next":
            if not await self.require_robot_connection("action.replay_next"):
                return
            result = self.game.replay_next()
            if not result.get("ok"):
                await self.log("info", self.msg("replay_info", reason=result.get("reason")))
                await self.broadcast(self.game.replay_state())
                return
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

        elif msg_type == "replay_stop":
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
            self.last_fen = None
            if self.game.replay_loaded:
                # Verder spelen na een (gedeeltelijk) nagespeelde PGN:
                # zettenlijst en stelling behouden.
                self.game.stop_replay()
                self.pending_scan_keep_history = True
                await self.broadcast(self.game.replay_state())
            else:
                self.game.clear_moves()
                await self.broadcast(self.game.render(orientation=self.human_color, reset=True))
            await self.send_to_arm("scan board")
            await self.log("info", self.msg("scan_after_side"))

        elif msg_type == "set_engine":
            settings = self.engine.update_settings(msg.get("settings", {}))
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
            await state.handle_message(msg)
    except WebSocketDisconnect:
        pass
    finally:
        state.clients.discard(ws)


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/download/pgn")
async def download_pgn():
    stockfish_name = f'Stockfish ({state.engine.settings.get("elo", "?")})'
    player_name = tr(state.language, "player_name")
    if state.human_color == "w":
        white_name = player_name
        black_name = stockfish_name
    else:
        white_name = stockfish_name
        black_name = player_name
    return Response(
        content=state.game.export_pgn(white_name=white_name, black_name=black_name),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="cynus-game.pgn"'},
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main():
    uvicorn.run("app.server:app", host="127.0.0.1", port=8000, loop="asyncio", reload=True)


if __name__ == "__main__":
    main()
