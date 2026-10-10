"""Состояние одной онлайн-партии: ходы, превращение, ничья, сдача, возврат хода.

Правила ходов — в остальных модулях core (перенесены из настольной версии main.py);
здесь только ход партии и проверка, что игрок делает разрешённый ход.
"""

from core.board import (
    PROMOTION_CHOICES, PAWN_FORWARD, initial_position, is_promotion_square_for, other,
)
from core.moves import compute_en_passant
from core.attacks import find_all_kings, has_any_king_attacked, is_in_check, is_square_attacked
from core.castling import compute_castle_moves, apply_castle
from core.legal import filter_legal_moves, compute_double_moves_cheetah, has_any_legal_move


class MoveError(Exception):
    pass


class Game:
    def __init__(self):
        self.position = initial_position()
        self.moved_pawns = set()
        self.en_passant_move = None
        self.en_passant_moves = {}
        self.current = 'w'
        self.result = None          # None | 'mate' | 'stalemate' | 'resign' | 'draw'
        self.winner = None
        self.resigned_by = None
        self.draw_votes = {'w': False, 'b': False}
        self.promotion_pending = None   # (c, r, color)
        self.last_move = None
        self.history = []           # снимки состояния перед каждым ходом
        self._legal = None

    @property
    def over(self):
        return self.result is not None

    # --- Разрешённые ходы ---

    def legal_moves(self):
        """{(c, r): {(tc, tr): вид}} для игрока, чей ход.

        Вид: 'move', 'capture', 'ep' (взятие на проходе), 'double' (двойной ход гепарда),
        'castle' (рокировка-обмен).
        """
        if self.over or self.promotion_pending:
            return {}
        if self._legal is None:
            self._legal = self._compute_legal()
        return self._legal

    def _compute_legal(self):
        color = self.current
        result = {}
        for (c, r), (pc, pt) in list(self.position.items()):
            if pc != color:
                continue
            # Взятие на проходе — только для пешек.
            ep = self.en_passant_moves if pt == 'P' else {}
            targets = {}
            if pt == 'R2':
                first, double = compute_double_moves_cheetah(
                    self.position, c, r, color, self.moved_pawns, ep)
            else:
                first = filter_legal_moves(self.position, c, r, color, self.moved_pawns, ep)
                double = {}
            for t in first:
                if t in ep:
                    targets[t] = 'ep'
                elif t in self.position:
                    targets[t] = 'capture'
                else:
                    targets[t] = 'move'
            for t in double:
                targets.setdefault(t, 'double')
            if pt != 'P':
                for t in compute_castle_moves(self.position, c, r, color):
                    test = dict(self.position)
                    apply_castle(test, c, r, t[0], t[1])
                    if not has_any_king_attacked(test, color):
                        targets[t] = 'castle'
            if targets:
                result[(c, r)] = targets
        return result

    # --- Действия игроков ---

    def move(self, color, frm, to):
        if self.over:
            raise MoveError("Партия окончена")
        if self.promotion_pending:
            raise MoveError("Сначала выберите фигуру для превращения")
        if color != self.current:
            raise MoveError("Сейчас не ваш ход")
        kind = self.legal_moves().get(frm, {}).get(to)
        if kind is None:
            raise MoveError("Так ходить нельзя")

        self.history.append(self._snapshot())

        if kind == 'castle':
            apply_castle(self.position, frm[0], frm[1], to[0], to[1])
            self.en_passant_move = None
            self.en_passant_moves = {}
        else:
            if kind == 'ep':
                self.position.pop(self.en_passant_moves[to], None)
            piece = self.position.pop(frm)
            self.position[to] = piece

            self.en_passant_move = None
            if piece[1] == 'P':
                dc, dr = PAWN_FORWARD[color]
                distance = abs(to[1] - frm[1]) if dr != 0 else abs(to[0] - frm[0])
                if distance >= 2:
                    self.en_passant_move = (frm[0], frm[1], to[0], to[1], color)
                self.moved_pawns.add(to)
            self.en_passant_moves = compute_en_passant(self.position, self.en_passant_move)

            if piece[1] == 'P' and is_promotion_square_for(color, to[0], to[1]):
                self.promotion_pending = (to[0], to[1], color)

        self.last_move = (frm, to)
        self._legal = None
        if not self.promotion_pending:
            self._end_turn()

    def promote(self, color, typ):
        if not self.promotion_pending or self.promotion_pending[2] != color:
            raise MoveError("Нет пешки для превращения")
        if typ not in PROMOTION_CHOICES:
            raise MoveError("Неизвестная фигура")
        c, r, _ = self.promotion_pending
        self.position[(c, r)] = (color, typ)
        self.promotion_pending = None
        self.en_passant_move = None
        self.en_passant_moves = {}
        self._end_turn()

    def resign(self, color):
        if self.over:
            raise MoveError("Партия окончена")
        self.result = 'resign'
        self.resigned_by = color
        self.winner = other(color)
        self._legal = None

    def toggle_draw(self, color):
        if self.over:
            raise MoveError("Партия окончена")
        self.draw_votes[color] = not self.draw_votes[color]
        if all(self.draw_votes.values()):
            self.result = 'draw'
            self._legal = None

    def undo(self):
        if not self.history or self.over:
            raise MoveError("Нечего возвращать")
        (self.position, self.moved_pawns, self.en_passant_move, self.en_passant_moves,
         self.current, self.last_move) = self.history.pop()
        self.promotion_pending = None
        self._legal = None

    def _snapshot(self):
        return (dict(self.position), set(self.moved_pawns), self.en_passant_move,
                dict(self.en_passant_moves), self.current, self.last_move)

    def _end_turn(self):
        self.current = other(self.current)
        self._legal = None
        if not has_any_legal_move(self.position, self.current, self.moved_pawns,
                                  self.en_passant_moves):
            if is_in_check(self.position, self.current):
                self.result = 'mate'
                self.winner = other(self.current)
            else:
                self.result = 'stalemate'

    # --- Для отправки в браузер ---

    def _target_json(self, target, kind):
        entry = [target[0], target[1], kind]
        if kind == 'ep':
            entry.append(list(self.en_passant_moves[target]))   # где стоит взятая пешка
        return entry

    def to_dict(self, viewer):
        checks = []
        if not self.over or self.result == 'mate':
            enemy = other(self.current)
            for (c, r) in find_all_kings(self.position, self.current):
                if is_square_attacked(self.position, c, r, enemy):
                    checks.append([c, r])
        legal = {}
        if viewer == self.current:
            legal = {f"{c},{r}": [self._target_json(t, kind) for t, kind in targets.items()]
                     for (c, r), targets in self.legal_moves().items()}
        return {
            'board': [[c, r, color, typ] for (c, r), (color, typ) in self.position.items()],
            'turn': self.current,
            'result': self.result,
            'winner': self.winner,
            'resignedBy': self.resigned_by,
            'drawVotes': self.draw_votes,
            'promotion': list(self.promotion_pending) if self.promotion_pending else None,
            'lastMove': [list(self.last_move[0]), list(self.last_move[1])] if self.last_move else None,
            'check': checks,
            'legal': legal,
            'moves': len(self.history),
        }
