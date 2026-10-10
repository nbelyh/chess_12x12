"""Разрешённые ходы (не оставляющие своего короля под шахом) и мат."""

from core.board import is_promotion_square_for
from core.moves import get_moves, cheetah_moves_second
from core.attacks import has_any_king_attacked, is_in_check
from core.castling import compute_castle_moves, apply_castle


def filter_legal_moves(position, c, r, color, moved_pawns, en_passant_moves):
    moves = get_moves(position, c, r, color, moved_pawns, en_passant_moves)
    legal = []
    for (mc, mr) in moves:
        new_position = dict(position)
        captured = new_position.pop((c, r))
        new_position[(mc, mr)] = captured
        if (mc, mr) in en_passant_moves:
            enemy_pos = en_passant_moves[(mc, mr)]
            if enemy_pos in new_position:
                del new_position[enemy_pos]
        if captured[1] == 'P' and is_promotion_square_for(color, mc, mr):
            new_position[(mc, mr)] = (color, 'Q')
        if not has_any_king_attacked(new_position, color):
            legal.append((mc, mr))
    return legal


def compute_double_moves_cheetah(position, c, r, color, moved_pawns, en_passant_moves):
    first_moves = filter_legal_moves(position, c, r, color, moved_pawns, en_passant_moves)
    double_moves = {}
    for (mc1, mr1) in first_moves:
        if (mc1, mr1) in position:
            continue
        new_pos = dict(position)
        moved = new_pos.pop((c, r))
        new_pos[(mc1, mr1)] = moved
        second_moves = cheetah_moves_second(new_pos, mc1, mr1, color)
        for (mc2, mr2) in second_moves:
            final_pos = dict(new_pos)
            captured2 = final_pos.pop((mc1, mr1))
            final_pos[(mc2, mr2)] = captured2
            if not has_any_king_attacked(final_pos, color):
                if (mc2, mr2) not in first_moves:
                    double_moves[(mc2, mr2)] = (mc1, mr1)
    return first_moves, double_moves


def has_any_legal_move(position, color, moved_pawns, en_passant_moves):
    for (c, r), (pc, pt) in position.items():
        if pc == color:
            if filter_legal_moves(position, c, r, color, moved_pawns, en_passant_moves):
                return True
            if pt != 'P':
                castles = compute_castle_moves(position, c, r, color)
                for (oc, or_) in castles:
                    test_pos = dict(position)
                    apply_castle(test_pos, c, r, oc, or_)
                    if not has_any_king_attacked(test_pos, color):
                        return True
    return False


def is_checkmate(position, color, moved_pawns, en_passant_moves):
    if not is_in_check(position, color):
        return False
    return not has_any_legal_move(position, color, moved_pawns, en_passant_moves)
