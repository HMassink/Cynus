"""Zoek historische zetten in een PGN-bestand op basis van EPD-stelling."""

from __future__ import annotations

import logging
import random
from collections import Counter
from pathlib import Path
from typing import Any

import chess
import chess.pgn

logger = logging.getLogger(__name__)


def _verzamel_mainline(partij: chess.pgn.Game, huidige_epd: str, teller: Counter[chess.Move]) -> None:
    game_board = partij.board()
    for move in partij.mainline_moves():
        if game_board.epd() == huidige_epd:
            teller[move] += 1
        game_board.push(move)


def _verzamel_met_varianten(
    node: chess.pgn.GameNode,
    board: chess.Board,
    huidige_epd: str,
    teller: Counter[chess.Move],
) -> None:
    """Loop recursief over hoofdlijn én zijvarianten."""
    for child in node.variations:
        move = child.move
        if move is None:
            continue
        if board.epd() == huidige_epd:
            teller[move] += 1
        board.push(move)
        _verzamel_met_varianten(child, board, huidige_epd, teller)
        board.pop()


def _scan_pgn(
    huidig_bord: chess.Board,
    pgn_pad: str | Path,
    *,
    include_variations: bool,
) -> Counter[chess.Move] | None:
    """Tel legale zetten voor de huidige EPD. None bij ontbrekend/onleesbaar bestand."""
    huidige_epd = huidig_bord.epd()
    teller: Counter[chess.Move] = Counter()
    path = Path(pgn_pad)

    try:
        with path.open("r", encoding="utf-8") as pgn_file:
            while True:
                partij = chess.pgn.read_game(pgn_file)
                if partij is None:
                    break

                if include_variations:
                    _verzamel_met_varianten(partij, partij.board(), huidige_epd, teller)
                else:
                    _verzamel_mainline(partij, huidige_epd, teller)
    except FileNotFoundError:
        logger.warning("PGN-database niet gevonden: %s", path)
        return None
    except OSError as exc:
        logger.warning("PGN-database onleesbaar (%s): %s", path, exc)
        return None

    legale = Counter({m: n for m, n in teller.items() if m in huidig_bord.legal_moves})
    return legale


def lijst_historische_zetten(
    huidig_bord: chess.Board,
    pgn_pad: str | Path,
    *,
    include_variations: bool = False,
) -> list[dict[str, Any]] | None:
    """Alle unieke legale historische zetten met frequentie, gesorteerd op aantal.

    Geeft None als het bestand ontbreekt; lege lijst als de stelling niet voorkomt.
    """
    teller = _scan_pgn(huidig_bord, pgn_pad, include_variations=include_variations)
    if teller is None:
        return None
    if not teller:
        return []
    kandidaten = sorted(teller.keys(), key=lambda m: (-teller[m], m.uci()))
    return [{"move": m, "count": teller[m]} for m in kandidaten]


def zoek_historische_zet(
    huidig_bord: chess.Board,
    pgn_pad: str | Path,
    *,
    include_variations: bool = False,
) -> dict[str, Any] | None:
    """Doorzoek een PGN naar de huidige stelling (EPD) en kies een historische zet.

    Verzamelt alle unieke legale zetten die in die stelling zijn gespeeld (met
    frequentie), kiest er willekeurig één uit, en geeft die terug samen met de
    kandidatenlijst. Geeft None als de stelling niet voorkomt of het bestand
    ontbreekt.

    Met ``include_variations=True`` worden ook PGN-zijvarianten meegenomen;
    anders alleen de hoofdlijn.

    Returnvorm::

        {
            "move": chess.Move,
            "candidates": [{"move": chess.Move, "count": int}, ...],
        }
    """
    teller = _scan_pgn(huidig_bord, pgn_pad, include_variations=include_variations)
    if teller is None or not teller:
        return None

    legale = list(teller.keys())
    gekozen = random.choice(legale)
    kandidaten = sorted(
        legale,
        key=lambda m: (0 if m == gekozen else 1, -teller[m], m.uci()),
    )
    return {
        "move": gekozen,
        "candidates": [{"move": m, "count": teller[m]} for m in kandidaten],
    }
