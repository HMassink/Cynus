"""Automatisch PGN bewaren in de map ``pgn/`` naast de projectroot."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .game import GameState

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PGN_DIR = _PROJECT_ROOT / "pgn"
_CURRENT_NAME = "current.pgn"


def pgn_dir() -> Path:
    """Geef de pgn-map terug en maak die aan indien nodig."""
    _PGN_DIR.mkdir(parents=True, exist_ok=True)
    return _PGN_DIR


def save_current(game: GameState, *, white_name: str, black_name: str) -> Path | None:
    """Schrijf de lopende partij naar ``pgn/current.pgn``."""
    if not game.moves:
        return None
    try:
        directory = pgn_dir()
        path = directory / _CURRENT_NAME
        path.write_text(
            game.export_pgn(white_name=white_name, black_name=black_name),
            encoding="utf-8",
        )
        return path
    except OSError as exc:
        logger.warning("PGN current opslaan mislukt: %s", exc)
        return None


def archive_current(game: GameState, *, white_name: str, black_name: str) -> Path | None:
    """Archiveer de lopende partij als die zetten heeft (vóór reset/wissen)."""
    if not game.moves:
        return None
    try:
        directory = pgn_dir()
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        path = directory / f"{stamp}.pgn"
        # Unieke naam als er binnen dezelfde seconde twee archieven komen.
        if path.exists():
            path = directory / f"{stamp}_{len(game.moves)}.pgn"
        content = game.export_pgn(white_name=white_name, black_name=black_name)
        path.write_text(content, encoding="utf-8")
        # Houd current.pgn synchroon met het archief tot de caller wist.
        current = directory / _CURRENT_NAME
        current.write_text(content, encoding="utf-8")
        logger.info("PGN gearchiveerd: %s", path.name)
        return path
    except OSError as exc:
        logger.warning("PGN archiveren mislukt: %s", exc)
        return None
