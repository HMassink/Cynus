"""Stockfish-wrapper voor de schaakarm-interface.

De arm stuurt alleen de stukkenplaatsing van de FEN; net als in het voorbeeld
(documentation/ble_stockfish2.py) vullen we die aan tot een volledige FEN
voordat die naar Stockfish gaat.

Startwaarden komen uit ``engine_defaults.json`` in de projectroot.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Any, Optional

import chess
from stockfish import Stockfish, StockfishException

logger = logging.getLogger(__name__)

# Conservatieve fallback als engine_defaults.json ontbreekt of ongeldig is.
_FALLBACK_SETTINGS = {
    "elo": 2000,
    "analysis_depth": 15,
    "movetime": 5000,
    "turn": "b",
    "candidates": 5,
    "hash": 512,
    "threads": 4,
}

SETTING_BOUNDS: dict[str, tuple[int, int]] = {
    "elo": (1320, 3190),
    "analysis_depth": (1, 40),
    "movetime": (100, 300_000),
    "candidates": (1, 10),
    "hash": (1, 65_536),
    "threads": (1, 64),
}

_DEFAULTS_FILE = Path(__file__).resolve().parent.parent / "engine_defaults.json"


def _clamp_int(key: str, value: int) -> int:
    low, high = SETTING_BOUNDS[key]
    return max(low, min(high, value))


def load_default_settings() -> dict:
    """Laad startinstellingen uit engine_defaults.json, anders fallback."""
    settings = dict(_FALLBACK_SETTINGS)
    try:
        raw = json.loads(_DEFAULTS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning(
            "engine_defaults.json niet gevonden (%s); gebruik fallback",
            _DEFAULTS_FILE,
        )
        return settings
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("engine_defaults.json onleesbaar: %s; gebruik fallback", exc)
        return settings

    if not isinstance(raw, dict):
        logger.warning("engine_defaults.json is geen object; gebruik fallback")
        return settings

    for key, default in _FALLBACK_SETTINGS.items():
        if key not in raw or raw[key] in (None, ""):
            continue
        if key == "turn":
            value = str(raw[key]).lower()
            if value in ("w", "b"):
                settings[key] = value
            continue
        try:
            settings[key] = _clamp_int(key, int(raw[key]))
        except (TypeError, ValueError):
            logger.warning("Ongeldige default voor %s=%r; behoud %s", key, raw[key], default)
    logger.info("Engine-defaults geladen uit %s", _DEFAULTS_FILE.name)
    return settings


DEFAULT_SETTINGS = load_default_settings()


def find_stockfish_path() -> Optional[str]:
    """Zoekt de Stockfish-executable: env-var, projectmap, app/stockfish, PATH."""
    env_path = os.environ.get("STOCKFISH_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    root = Path(__file__).resolve().parent.parent
    search_dirs = [
        Path.cwd(),
        root,
        root / "app" / "stockfish",
        Path(__file__).resolve().parent / "stockfish",
    ]
    patterns = ("stockfish*.exe", "stockfish*")
    for directory in search_dirs:
        if not directory.is_dir():
            continue
        for pattern in patterns:
            for candidate in sorted(directory.glob(pattern)):
                if candidate.is_file():
                    return str(candidate.resolve())
    return shutil.which("stockfish")


class Engine:
    """Beheert een Stockfish-instantie met instelbare opties.

    Alle toegang tot het Stockfish-proces gaat via ``_lock`` (threading),
    omdat analyze() via asyncio.to_thread parallel kan lopen.
    """

    def __init__(self, path: Optional[str] = None):
        self.settings = dict(DEFAULT_SETTINGS)
        self.path = path or find_stockfish_path()
        self.error: Optional[str] = None
        self._sf: Optional[Stockfish] = None
        self._lock = threading.Lock()
        self._start()

    @property
    def available(self) -> bool:
        return self._sf is not None

    def _start(self) -> None:
        if not self.path:
            self.error = (
                "Stockfish-executable niet gevonden. Zet die in de projectmap "
                "of stel de omgevingsvariabele STOCKFISH_PATH in."
            )
            logger.warning(self.error)
            return
        try:
            self._sf = Stockfish(path=self.path)
            self._apply_settings_unlocked()
            self.error = None
            logger.info("Stockfish gestart: %s", self.path)
        except Exception as exc:
            self._sf = None
            self.error = f"Stockfish starten mislukt ({self.path}): {exc}"
            logger.warning(self.error)

    def _apply_settings_unlocked(self) -> None:
        if self._sf is None:
            return
        self._sf.set_elo_rating(int(self.settings["elo"]))
        self._sf.set_depth(int(self.settings["analysis_depth"]))
        self._sf.update_engine_parameters({
            "Hash": int(self.settings["hash"]),
            "Threads": int(self.settings["threads"]),
        })

    def update_settings(self, new_settings: dict) -> dict:
        """Neemt bekende sleutels over, clampt waarden en past ze toe."""
        if not isinstance(new_settings, dict):
            return self.settings
        with self._lock:
            for key in _FALLBACK_SETTINGS:
                if key not in new_settings or new_settings[key] in (None, ""):
                    continue
                if key == "turn":
                    value = str(new_settings[key]).lower()
                    if value in ("w", "b"):
                        self.settings[key] = value
                    continue
                try:
                    self.settings[key] = _clamp_int(key, int(new_settings[key]))
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Ongeldige waarde voor {key}: {new_settings[key]!r}") from exc
            self._apply_settings_unlocked()
            return dict(self.settings)

    def full_fen(self, fen_or_placement: str) -> str:
        """Maak een volledige FEN; laat een al volledige FEN intact."""
        text = fen_or_placement.strip()
        parts = text.split()
        if len(parts) >= 4:
            return text
        placement = parts[0] if parts else text
        return f"{placement} {self.settings['turn']} - - 0 15"

    @staticmethod
    def _format_score(centipawn: Optional[int], mate: Optional[int]) -> str:
        if mate is not None:
            return f"#{mate}" if mate > 0 else f"#-{abs(mate)}"
        if centipawn is None:
            return "–"
        return f"{centipawn / 100:+.2f}"

    def _uci_line_to_san(self, board: chess.Board, uci_line: str) -> str:
        probe = board.copy(stack=False)
        sans: list[str] = []
        for token in (uci_line or "").split():
            try:
                move = chess.Move.from_uci(token)
                if move not in probe.legal_moves:
                    break
                sans.append(probe.san(move))
                probe.push(move)
            except (ValueError, chess.InvalidMoveError):
                break
            if len(sans) >= 8:
                break
        return " ".join(sans)

    def analyze(self, fen_placement: str) -> dict[str, Any]:
        """Berekent topzetten met waardering (blocking; via asyncio.to_thread)."""
        with self._lock:
            if self._sf is None:
                raise RuntimeError(self.error or "Engine niet beschikbaar")
            fen = self.full_fen(fen_placement)
            num = max(1, min(10, int(self.settings.get("candidates", 5))))
            try:
                self._sf.set_fen_position(fen)
                self._sf.set_depth(int(self.settings["analysis_depth"]))
                raw = self._sf.get_top_moves(num, verbose=True)
                # Gespeelde zet volgt skill/ELO; kandidaten zijn full-strength analyse.
                self._sf.set_fen_position(fen)
                played = self._sf.get_best_move_time(int(self.settings["movetime"]))
            except StockfishException as exc:
                logger.warning("StockfishException: %s; engine wordt herstart", exc)
                self._start()
                raise RuntimeError(f"Stockfish-fout: {exc}") from exc

            if not raw and not played:
                raise RuntimeError(f"Geen zet gevonden voor stelling: {fen}")

            try:
                board = chess.Board(fen)
            except ValueError:
                board = chess.Board()

            candidates = []
            for entry in raw or []:
                uci = str(entry.get("Move") or "")
                cp = entry.get("Centipawn")
                mate = entry.get("Mate")
                pv_uci = str(entry.get("PVMoves") or uci)
                san = ""
                try:
                    move = chess.Move.from_uci(uci)
                    if move in board.legal_moves:
                        san = board.san(move)
                except (ValueError, chess.InvalidMoveError):
                    san = uci
                candidates.append({
                    "move": uci,
                    "san": san or uci,
                    "centipawn": cp,
                    "mate": mate,
                    "score": self._format_score(
                        int(cp) if cp is not None else None,
                        int(mate) if mate is not None else None,
                    ),
                    "pv": self._uci_line_to_san(board, pv_uci),
                    "depth": entry.get("SelectiveDepth"),
                    "multipv": entry.get("MultiPVNumber"),
                })

            best = played or (candidates[0]["move"] if candidates else None)
            if not best:
                raise RuntimeError(f"Geen zet gevonden voor stelling: {fen}")

            return {
                "move": best,
                "fen": fen,
                "candidates": candidates,
            }

    def best_move(self, fen_placement: str) -> str:
        """Berekent de beste zet (blocking; aanroepen via asyncio.to_thread)."""
        return self.analyze(fen_placement)["move"]
