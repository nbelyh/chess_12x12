"""Атакованные поля и шах."""

from core.board import PAWN_FORWARD
from core.moves import get_moves


def find_all_kings(position, color):
    return [(c, r) for (c, r), (pc, pt) in position.items()
            if pc == color and pt == 'K']


def is_square_attacked(position, c, r, by_color):
    for (pc, pr), (color, typ) in position.items():
        if color != by_color:
            continue
        if typ == 'P':
            dc, dr = PAWN_FORWARD[color]
            for ddc, ddr in [(-1, dr), (+1, dr)]:
                if pc + ddc == c and pr + ddr == r:
                    return True
            continue
        # Для всех фигур, кроме пешки, поля боя совпадают с полями хода.
        if (c, r) in get_moves(position, pc, pr, color, set(), {}):
            return True
    return False


def is_square_attacked_by_piece(position, piece_c, piece_r, target_c, target_r):
    if (piece_c, piece_r) not in position:
        return False
    color, typ = position[(piece_c, piece_r)]
    if typ == 'P':
        dc, dr = PAWN_FORWARD[color]
        for ddc, ddr in [(-1, dr), (+1, dr)]:
            if piece_c + ddc == target_c and piece_r + ddr == target_r:
                return True
        return False
    test_pos = dict(position)
    if (target_c, target_r) in test_pos:
        del test_pos[(target_c, target_r)]
    moves = get_moves(test_pos, piece_c, piece_r, color, set(), {})
    return (target_c, target_r) in moves


def has_any_king_attacked(position, color):
    enemy = 'b' if color == 'w' else 'w'
    for kp in find_all_kings(position, color):
        if is_square_attacked(position, kp[0], kp[1], enemy):
            return True
    return False


def is_in_check(position, color):
    return has_any_king_attacked(position, color)
