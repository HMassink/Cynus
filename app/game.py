"""Partijstatus met python-chess: FEN-updates, SAN-zetten en SVG-bord."""

from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Optional

import chess
import chess.pgn
import chess.svg

from .i18n import DEFAULT_LANGUAGE, tr

logger = logging.getLogger(__name__)


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
        # Canonieke zetten voor PGN-export via chess.pgn (niet opnieuw SAN-parsen).
        self.moves: list[chess.Move] = []
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
        """Standaard-zetkleur voor FEN-sync (engine/robot), niet het live zetrecht."""
        if turn in ("w", "b"):
            self._turn = turn

    def reset(self) -> None:
        self.board = chess.Board()
        self.moves_san = []
        self.moves = []
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
        self.moves = []
        self.last_move = None
        self._black_started = False

    def sync_from_scan(self, fen_or_placement: str, *, keep_history: bool = False) -> dict:
        """Synchroniseer stelling na scan board.

        Met keep_history=True blijft de zettenlijst staan (knop Scan bord).
        keep_history=False wist historie (o.a. kleurwissel zonder replay).
        """
        try:
            placement = _placement_only(fen_or_placement)
            chess.Board().set_board_fen(placement)
        except (ValueError, IndexError):
            return self.render(error=tr(self.language, "invalid_fen", fen=f"{fen_or_placement!r}"))

        if not keep_history:
            self._set_from_placement(placement, clear_history=True)
            return self.render(reset=True)

        if not self._has_position:
            self._set_from_placement(placement, clear_history=False)
            return self.render(reset=True)

        if self.board.board_fen() == placement:
            return self.render()

        # Scan wijkt af: app blijft leidend (geen stukken/zetten/zetrecht wijzigen).
        return self.render(gap=True)

    def update_from_placement(
        self,
        fen_or_placement: str,
        *,
        adopt_on_gap: bool = True,
    ) -> dict:
        """Verwerk een stukkenplaatsing (of volledige FEN) van de arm.

        adopt_on_gap=False: bij geen zetpad de app-stelling behouden (app leidend).
        """
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
            if placement == chess.STARTING_BOARD_FEN and self.board.turn != chess.WHITE:
                self.board.turn = chess.WHITE
                self._turn = "w"
            return self.render()

        sequence = self._find_move_sequence(placement, max_depth=2)
        if sequence:
            for move in sequence:
                self._push_detected(move)
            return self.render()

        # Geen pad gevonden.
        if adopt_on_gap:
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

    def apply_uci_move(self, uci: str) -> dict:
        """Valideer en speel een UCI-zet op het app-bord (Stockfish/app leidend)."""
        validation = self.validate_uci_move(uci)
        if not validation.get("ok"):
            return validation
        try:
            move = chess.Move.from_uci(uci.strip())
        except ValueError:
            return {
                "ok": False,
                "move": uci,
                "reason": tr(self.language, "reason.bad_uci"),
            }
        self._push_detected(move)
        return {
            "ok": True,
            "move": uci.strip(),
            "san": validation["san"],
            "uci": uci.strip(),
        }

    def undo_last_move(self) -> bool:
        """Maak de laatste doorgeduwde zet ongedaan (bij mislukte arm-send)."""
        if not self.moves:
            return False
        self.board.pop()
        self.moves.pop()
        if self.moves_san:
            self.moves_san.pop()
        self.last_move = self.moves[-1] if self.moves else None
        self._turn = "w" if self.board.turn == chess.WHITE else "b"
        if not self.moves:
            self._black_started = False
        return True

    def force_move_pieces(self, uci: str) -> tuple[str, str | None]:
        """Stukletters (s, t) voor force-move vóór het pushen van de zet."""
        try:
            move = chess.Move.from_uci(uci.strip())
        except ValueError:
            return "P", None
        piece = self.board.piece_at(move.from_square)
        s = piece.symbol() if piece else "P"
        t: str | None = None
        if self.board.is_en_passant(move):
            cap_sq = chess.square(
                chess.square_file(move.to_square),
                chess.square_rank(move.from_square),
            )
            cap = self.board.piece_at(cap_sq)
            t = cap.symbol() if cap else "p"
        elif self.board.is_capture(move):
            cap = self.board.piece_at(move.to_square)
            t = cap.symbol() if cap else None
        return s, t

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
        self.moves = []
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
        if self.board.castling_rights == 0:
            self.board.castling_rights = self._infer_castling_rights(self.board)
        if move not in self.board.legal_moves:
            # Alleen omdraaien als de zet dan legaal is (scan/turn-mismatch).
            self.board.turn = not self.board.turn
            if move not in self.board.legal_moves:
                self.board.turn = not self.board.turn
                logger.warning(
                    "Zet %s genegeerd (illegaal in %s)",
                    move.uci(),
                    self.board.fen(),
                )
                return
        mover = self.board.turn
        if not self.moves and mover == chess.BLACK:
            self._black_started = True
            # Root zo zetten dat chess.pgn met zwart kan beginnen.
            root = chess.Board(self._root_fen or chess.STARTING_FEN)
            root.turn = chess.BLACK
            self._root_fen = root.fen()
        san = self.board.san(move)
        self.board.push(move)
        self.moves.append(move)
        self.moves_san.append(san)
        self.last_move = move
        self._turn = "w" if self.board.turn == chess.WHITE else "b"

    def _set_from_placement(self, placement: str, *, clear_history: bool) -> None:
        """Zet stukken; behoud zo veel mogelijk rokaderechten."""
        board = chess.Board()
        board.set_board_fen(placement)
        # Beginstelling: wit is altijd aan zet (niet de robotkleur).
        if placement == chess.STARTING_BOARD_FEN:
            board.turn = chess.WHITE
            self._turn = "w"
        else:
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
            self.moves = []
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
        """Exporteer de partij via ``chess.pgn`` (legale zetten vanaf root-FEN)."""
        try:
            root = chess.Board(self._root_fen) if self._root_fen else chess.Board()
        except ValueError:
            root = chess.Board()

        game = chess.pgn.Game()
        game.setup(root)
        game.headers["Event"] = "CYNUS Session"
        game.headers["Site"] = "Local"
        game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
        game.headers["Round"] = "-"
        game.headers["White"] = white_name
        game.headers["Black"] = black_name
        game.headers["Result"] = "*"

        node: chess.pgn.GameNode = game
        board = root.copy(stack=False)
        for move in self.moves:
            if move not in board.legal_moves:
                logger.warning(
                    "PGN-export gestopt: illegale zet %s in %s",
                    move.uci(),
                    board.fen(),
                )
                break
            node = node.add_main_variation(move)
            board.push(move)

        exporter = chess.pgn.StringExporter(
            headers=True,
            variations=False,
            comments=False,
        )
        return game.accept(exporter).strip() + "\n"

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
            # Altijd uit het bord; beginstelling (ook vóór eerste scan) = wit.
            "turn": "w" if self.board.turn == chess.WHITE else "b",
            "last_move": last.uci() if last else None,
            "reset": reset,
            "gap": gap,
            "error": error,
        }
