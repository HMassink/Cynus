"""Partijstatus met python-chess: FEN-updates, SAN-zetten en SVG-bord."""

from __future__ import annotations

import io
from datetime import datetime
from typing import Optional

import chess
import chess.pgn
import chess.svg

from .i18n import DEFAULT_LANGUAGE, tr


def _placement_only(fen_or_placement: str) -> str:
    """Haal alleen het stukkenplaatsing-deel uit een (mogelijk volledige) FEN."""
    return fen_or_placement.strip().split()[0]


class GameState:
    """Houdt een chess.Board bij, detecteert zetten uit FEN van de arm."""

    def __init__(self, turn: str = "b"):
        self.language = DEFAULT_LANGUAGE
        self._turn = "w" if turn == "w" else "b"
        self.board = chess.Board()
        self.moves_san: list[str] = []
        self.last_move: Optional[chess.Move] = None
        self._has_position = False
        self._root_fen: Optional[str] = None
        # True als de eerste gedetecteerde zet van zwart was (notatie 1...)
        self._black_started = False
        # Replay-state voor het naspelen van een geladen PGN-partij.
        self.replay_moves: list[chess.Move] = []
        self.replay_sans: list[str] = []
        self.replay_index = 0
        self.replay_headers: dict = {}
        self.replay_active = False
        self.replay_loaded = False

    @property
    def has_position(self) -> bool:
        return self._has_position

    def set_turn(self, turn: str) -> None:
        if turn in ("w", "b"):
            self._turn = turn

    def reset(self) -> None:
        self.board = chess.Board()
        self.moves_san = []
        self.last_move = None
        self._has_position = False
        self._root_fen = None
        self._black_started = False
        self.clear_replay()

    def clear_replay(self) -> None:
        self.replay_moves = []
        self.replay_sans = []
        self.replay_index = 0
        self.replay_headers = {}
        self.replay_active = False
        self.replay_loaded = False

    def clear_moves(self) -> None:
        """Leeg alleen de zettenlijst (bord blijft tot de volgende FEN)."""
        self.moves_san = []
        self.last_move = None
        self._black_started = False

    def sync_from_scan(self, fen_or_placement: str, *, keep_history: bool = False) -> dict:
        """Synchroniseer stelling na scan board.

        Standaard wordt de zettenlijst geleegd; met keep_history=True blijft
        de historie staan (bijv. verder spelen na een nagespeelde PGN).
        """
        try:
            placement = _placement_only(fen_or_placement)
            chess.Board().set_board_fen(placement)
        except (ValueError, IndexError):
            return self.render(error=tr(self.language, "invalid_fen", fen=f"{fen_or_placement!r}"))

        if not keep_history:
            self._set_from_placement(placement, clear_history=True)
            return self.render(reset=True)

        if self._has_position and self.board.board_fen() == placement:
            return self.render()

        # Scan wijkt af van de verwachte stelling: stukken bijwerken,
        # historie en kleur-aan-zet behouden.
        self.board.set_board_fen(placement)
        self.board.castling_rights &= self._infer_castling_rights(self.board)
        self.board.ep_square = None
        self.last_move = None
        self._has_position = True
        return self.render(gap=True)

    def update_from_placement(self, fen_or_placement: str) -> dict:
        """Verwerk een stukkenplaatsing (of volledige FEN) van de arm."""
        try:
            placement = _placement_only(fen_or_placement)
            chess.Board().set_board_fen(placement)
        except (ValueError, IndexError):
            return self.render(error=tr(self.language, "invalid_fen", fen=f"{fen_or_placement!r}"))

        # Expliciete startpositie = nieuw spel (historie wissen).
        if placement == chess.STARTING_BOARD_FEN and self._has_position and self.moves_san:
            if self.board.board_fen() != placement:
                self._set_from_placement(placement, clear_history=True)
                return self.render(reset=True)

        if not self._has_position:
            self._set_from_placement(placement, clear_history=True)
            return self.render(reset=True)

        if self.board.board_fen() == placement:
            return self.render()

        sequence = self._find_move_sequence(placement, max_depth=2)
        if sequence:
            for move in sequence:
                self._push_detected(move)
            return self.render()

        # Geen pad gevonden: bord bijwerken maar historie BEHOUDEN.
        self._apply_placement_keep_history(placement)
        return self.render(gap=True)

    def validate_uci_move(self, uci: str) -> dict:
        """Valideer een handmatige UCI-zet op basis van de huidige stelling."""
        uci = uci.strip()
        if not uci:
            return {"ok": False, "move": "", "reason": tr(self.language, "reason.empty_move")}

        if not self.has_position:
            return {
                "ok": False,
                "move": uci,
                "reason": tr(self.language, "reason.no_position"),
            }

        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return {
                "ok": False,
                "move": uci,
                "reason": tr(self.language, "reason.bad_uci"),
            }

        board = self.board.copy(stack=False)
        if move not in board.legal_moves:
            return {
                "ok": False,
                "move": uci,
                "reason": tr(self.language, "reason.illegal"),
            }

        return {
            "ok": True,
            "move": uci,
            "san": board.san(move),
        }

    # -- PGN naspelen ---------------------------------------------------------

    def load_pgn(self, text: str) -> dict:
        """Laad een PGN-partij (vanuit de beginstand) voor het naspelen."""
        text = text.strip()
        if not text:
            return {"ok": False, "reason": tr(self.language, "reason.pgn_empty")}

        try:
            pgn_game = chess.pgn.read_game(io.StringIO(text))
        except Exception as exc:
            return {"ok": False, "reason": tr(self.language, "reason.pgn_unreadable", error=exc)}
        if pgn_game is None:
            return {"ok": False, "reason": tr(self.language, "reason.pgn_no_game")}
        if pgn_game.errors:
            return {"ok": False, "reason": tr(self.language, "reason.pgn_errors", error=pgn_game.errors[0])}
        if pgn_game.headers.get("FEN"):
            return {"ok": False, "reason": tr(self.language, "reason.pgn_fen_header")}

        moves: list[chess.Move] = []
        sans: list[str] = []
        board = chess.Board()
        for move in pgn_game.mainline_moves():
            sans.append(board.san(move))
            board.push(move)
            moves.append(move)
        if not moves:
            return {"ok": False, "reason": tr(self.language, "reason.pgn_no_moves")}

        headers = pgn_game.headers
        self.replay_moves = moves
        self.replay_sans = sans
        self.replay_index = 0
        self.replay_headers = {
            "white": headers.get("White", "?"),
            "black": headers.get("Black", "?"),
            "event": headers.get("Event", ""),
            "date": headers.get("Date", ""),
            "result": headers.get("Result", "*"),
        }
        self.replay_active = True
        self.replay_loaded = True

        # Bord en zettenlijst terug naar de beginstand.
        self.board = chess.Board()
        self.moves_san = []
        self.last_move = None
        self._has_position = True
        self._root_fen = chess.STARTING_FEN
        self._black_started = False
        self._turn = "w"
        return {"ok": True, "total": len(moves), "headers": dict(self.replay_headers)}

    def replay_next(self) -> dict:
        """Voer de volgende replayzet uit op het interne bord."""
        if not self.replay_loaded:
            return {"ok": False, "reason": tr(self.language, "reason.no_pgn_loaded")}
        if self.replay_index >= len(self.replay_moves):
            return {"ok": False, "reason": tr(self.language, "reason.replay_finished")}

        move = self.replay_moves[self.replay_index]
        san = self.replay_sans[self.replay_index]
        self._push_detected(move)
        self.replay_index += 1
        done = self.replay_index >= len(self.replay_moves)
        if done:
            self.replay_active = False
        return {
            "ok": True,
            "uci": move.uci(),
            "san": san,
            "index": self.replay_index,
            "total": len(self.replay_moves),
            "done": done,
        }

    def stop_replay(self) -> None:
        """Stop het naspelen; bord en historie blijven staan."""
        self.replay_active = False

    def replay_state(self) -> dict:
        return {
            "type": "replay",
            "loaded": self.replay_loaded,
            "active": self.replay_active,
            "index": self.replay_index,
            "total": len(self.replay_moves),
            "sans": list(self.replay_sans),
            "headers": dict(self.replay_headers),
        }

    def _push_detected(self, move: chess.Move) -> None:
        if move not in self.board.legal_moves:
            self.board.turn = not self.board.turn
        if self.board.castling_rights == 0:
            self.board.castling_rights = self._infer_castling_rights(self.board)
        mover = self.board.turn
        if not self.moves_san and mover == chess.BLACK:
            self._black_started = True
        san = self.board.san(move)
        self.board.push(move)
        self.moves_san.append(san)
        self.last_move = move
        self._turn = "w" if self.board.turn == chess.WHITE else "b"

    def _set_from_placement(self, placement: str, *, clear_history: bool) -> None:
        """Zet stukken; behoud zo veel mogelijk rokaderechten."""
        board = chess.Board()
        board.set_board_fen(placement)
        board.turn = chess.WHITE if self._turn == "w" else chess.BLACK
        board.castling_rights = self._infer_castling_rights(board)
        board.ep_square = None
        board.halfmove_clock = 0
        board.fullmove_number = 1
        self.board = board
        self.last_move = None
        self._has_position = True
        self._root_fen = board.fen()
        if clear_history:
            self.moves_san = []
            self._black_started = False

    def _apply_placement_keep_history(self, placement: str) -> None:
        """Werk alleen de stukken bij; wissen van de zettenlijst vermijden."""
        previous_turn = self.board.turn
        self.board.set_board_fen(placement)
        self.board.castling_rights = self._infer_castling_rights(self.board)
        self.board.ep_square = None
        # Na een gemiste overgang: wissel van kleur is de beste schatting.
        self.board.turn = not previous_turn
        self.last_move = None
        self._turn = "w" if self.board.turn == chess.WHITE else "b"

    @staticmethod
    def _infer_castling_rights(board: chess.Board) -> int:
        rights = 0
        if board.piece_at(chess.E1) == chess.Piece.from_symbol("K"):
            if board.piece_at(chess.H1) == chess.Piece.from_symbol("R"):
                rights |= chess.BB_H1
            if board.piece_at(chess.A1) == chess.Piece.from_symbol("R"):
                rights |= chess.BB_A1
        if board.piece_at(chess.E8) == chess.Piece.from_symbol("k"):
            if board.piece_at(chess.H8) == chess.Piece.from_symbol("r"):
                rights |= chess.BB_H8
            if board.piece_at(chess.A8) == chess.Piece.from_symbol("r"):
                rights |= chess.BB_A8
        return rights

    def _find_move_sequence(self, placement: str, max_depth: int = 2) -> Optional[list[chess.Move]]:
        """Zoek het kortste legale zettenpad (1..max_depth) naar de nieuwe plaatsing."""
        for depth in range(1, max_depth + 1):
            for try_turn in (self.board.turn, not self.board.turn):
                found = self._search_exact_depth(placement, try_turn, depth)
                if found is not None:
                    return found
        return None

    def _search_exact_depth(
        self,
        placement: str,
        try_turn: chess.Color,
        depth: int,
    ) -> Optional[list[chess.Move]]:
        root = self.board.copy(stack=False)
        root.turn = try_turn
        if root.castling_rights == 0:
            root.castling_rights = self._infer_castling_rights(root)

        if depth == 1:
            for move in root.legal_moves:
                root.push(move)
                match = root.board_fen() == placement
                root.pop()
                if match:
                    return [move]
            return None

        # depth == 2 (of hoger): alleen korte paden, geen diepe BFS
        for move1 in list(root.legal_moves):
            root.push(move1)
            if depth == 2:
                for move2 in list(root.legal_moves):
                    root.push(move2)
                    match = root.board_fen() == placement
                    root.pop()
                    if match:
                        root.pop()
                        return [move1, move2]
            else:
                # depth 3: beperkt, alleen indien echt nodig
                for move2 in list(root.legal_moves):
                    root.push(move2)
                    for move3 in list(root.legal_moves):
                        root.push(move3)
                        match = root.board_fen() == placement
                        root.pop()
                        if match:
                            root.pop()
                            root.pop()
                            return [move1, move2, move3]
                    root.pop()
            root.pop()
        return None

    def move_rows(self) -> list[dict]:
        """Rijen voor de UI: [{n, w, b}, ...] met ondersteuning voor 1..."""
        rows: list[dict] = []
        sans = self.moves_san
        if not sans:
            return rows

        i = 0
        n = 1
        if self._black_started:
            rows.append({"n": 1, "w": None, "b": sans[0]})
            i = 1
            n = 2

        while i < len(sans):
            rows.append({
                "n": n,
                "w": sans[i],
                "b": sans[i + 1] if i + 1 < len(sans) else None,
            })
            i += 2
            n += 1
        return rows

    def export_pgn(self, *, white_name: str = "White", black_name: str = "Black") -> str:
        """Maak een eenvoudige PGN-export van de huidige zettenlijst."""
        headers = [
            '[Event "CYNUS Session"]',
            '[Site "Local"]',
            f'[Date "{datetime.now().strftime("%Y.%m.%d")}"]',
            '[Round "-"]',
            f'[White "{white_name}"]',
            f'[Black "{black_name}"]',
            '[Result "*"]',
        ]
        if self._root_fen and self._root_fen != chess.STARTING_FEN:
            headers.append(f'[FEN "{self._root_fen}"]')
            headers.append('[SetUp "1"]')

        movetext_parts: list[str] = []
        move_no = 1
        white_to_move = not self._black_started
        for san in self.moves_san:
            if white_to_move:
                movetext_parts.append(f"{move_no}.{san}")
                white_to_move = False
            else:
                if movetext_parts:
                    movetext_parts[-1] = f"{movetext_parts[-1]} {san}"
                else:
                    movetext_parts.append(f"{move_no}...{san}")
                move_no += 1
                white_to_move = True
        movetext_parts.append("*")

        # Regels maximaal ~80 tekens houden (PGN-conventie).
        lines: list[str] = []
        current = ""
        for part in movetext_parts:
            if not current:
                current = part
            elif len(current) + 1 + len(part) <= 79:
                current = f"{current} {part}"
            else:
                lines.append(current)
                current = part
        if current:
            lines.append(current)
        movetext = "\n".join(lines)
        return "\n".join(headers) + "\n\n" + movetext + "\n"

    def render(
        self,
        *,
        orientation: str = "w",
        reset: bool = False,
        gap: bool = False,
        error: Optional[str] = None,
    ) -> dict:
        last = self.last_move
        svg = chess.svg.board(
            self.board,
            size=400,
            lastmove=last,
            coordinates=True,
            orientation=chess.WHITE if orientation == "w" else chess.BLACK,
        )
        return {
            "type": "board",
            "svg": svg,
            "moves": list(self.moves_san),
            "move_rows": self.move_rows(),
            "fen": self.board.fen() if self._has_position else None,
            "placement": self.board.board_fen() if self._has_position else None,
            "last_move": last.uci() if last else None,
            "reset": reset,
            "gap": gap,
            "error": error,
        }
