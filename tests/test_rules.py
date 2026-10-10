"""Правила ходов (core.moves / attacks / castling / legal)."""

import threading

from core.board import initial_position
from core.moves import get_moves, eagle_moves, cheetah_moves, genie_moves
from core.attacks import is_square_attacked, is_in_check
from core.castling import compute_castle_moves, can_castle
from core.legal import filter_legal_moves, compute_double_moves_cheetah, is_checkmate

KINGS = {(11, 0): ('w', 'K'), (0, 11): ('b', 'K')}


def board(**extra):
    """Позиция из двух королей в углах плюс переданные фигуры: board(a=((c, r), ('w', 'N')), ...)."""
    pos = dict(KINGS)
    for square, piece in extra.values():
        pos[square] = piece
    return pos


def test_initial_position_is_mirrored():
    pos = initial_position()
    assert len(pos) == 52
    for (c, r), (color, typ) in pos.items():
        if color == 'w':
            assert pos[(11 - c, 11 - r)] == ('b', typ)


def test_pawn_first_move_up_to_three_squares_then_two():
    pos = board(p=((5, 2), ('w', 'P')))
    assert sorted(get_moves(pos, 5, 2, 'w', set(), {})) == [(5, 3), (5, 4), (5, 5)]
    assert sorted(get_moves(pos, 5, 2, 'w', {(5, 2)}, {})) == [(5, 3), (5, 4)]


def test_pawn_is_blocked_and_captures_diagonally():
    pos = board(p=((5, 2), ('w', 'P')), block=((5, 4), ('b', 'N')), victim=((6, 3), ('b', 'B')))
    assert sorted(get_moves(pos, 5, 2, 'w', set(), {})) == [(5, 3), (6, 3)]


def test_black_pawn_moves_down():
    pos = board(p=((3, 9), ('b', 'P')))
    assert sorted(get_moves(pos, 3, 9, 'b', set(), {})) == [(3, 6), (3, 7), (3, 8)]


def test_eagle_jumps_one_by_three():
    pos = board(e=((5, 5), ('w', 'N2')), wall=((5, 6), ('w', 'P')))
    assert sorted(eagle_moves(pos, 5, 5, 'w')) == sorted(
        [(6, 8), (8, 6), (4, 8), (2, 6), (6, 2), (8, 4), (4, 2), (2, 4)])


def test_cheetah_jumps_over_own_piece_and_stops_behind_it():
    pos = board(ch=((0, 5), ('w', 'R2')), own=((0, 6), ('w', 'P')))
    moves = cheetah_moves(pos, 0, 5, 'w')
    assert (0, 7) in moves          # сразу за своей фигурой
    assert (0, 8) not in moves      # дальше нельзя
    assert (0, 6) not in moves      # на свою фигуру нельзя


def test_cheetah_cannot_jump_if_square_behind_is_taken():
    pos = board(ch=((0, 5), ('w', 'R2')), own=((0, 6), ('w', 'P')), behind=((0, 7), ('b', 'P')))
    assert not {(0, 6), (0, 7), (0, 8)} & set(cheetah_moves(pos, 0, 5, 'w'))


def test_genie_jumps_diagonally_over_own_piece():
    pos = board(j=((3, 3), ('w', 'J')), own=((4, 4), ('w', 'P')))
    moves = genie_moves(pos, 3, 3, 'w')
    assert (5, 5) in moves and (6, 6) not in moves


def test_cheetah_double_move_turns_a_corner():
    pos = board(ch=((5, 5), ('w', 'R2')))
    first, double = compute_double_moves_cheetah(pos, 5, 5, 'w', set(), {})
    assert (6, 6) not in first
    assert (6, 6) in double                      # например, вверх, потом вправо
    assert double[(6, 6)] in [(5, 6), (6, 5)]


def test_pawn_attacks_only_diagonally_forward():
    pos = board(p=((5, 5), ('b', 'P')))
    assert is_square_attacked(pos, 4, 4, 'b') and is_square_attacked(pos, 6, 4, 'b')
    assert not is_square_attacked(pos, 5, 4, 'b')


def test_cannot_leave_king_in_check():
    # Белый слон связан: уходит с линии — король под ладьёй.
    pos = {(5, 0): ('w', 'K'), (5, 3): ('w', 'B'), (5, 9): ('b', 'R'), (0, 11): ('b', 'K')}
    assert filter_legal_moves(pos, 5, 3, 'w', set(), {}) == []


def test_back_rank_mate():
    pos = {(0, 11): ('b', 'K'), (0, 10): ('b', 'P'), (1, 10): ('b', 'P'),
           (5, 11): ('w', 'R'), (11, 0): ('w', 'K')}
    assert is_in_check(pos, 'b')
    assert is_checkmate(pos, 'b', set(), {})


def test_knight_swaps_with_attacked_own_piece():
    # Ладья на j9 не на одной линии с конём, и конь до неё не достаёт.
    pos = board(n=((3, 3), ('w', 'N')), r=((4, 5), ('w', 'R')), far=((9, 8), ('w', 'R')))
    assert compute_castle_moves(pos, 3, 3, 'w') == [(4, 5)]


def test_swap_allowed_when_either_piece_attacks_the_other():
    # Конь слона не бьёт, но слон бьёт коня по свободной диагонали.
    pos = board(n=((3, 3), ('w', 'N')), b=((9, 9), ('w', 'B')))
    assert (9, 9) in compute_castle_moves(pos, 3, 3, 'w')


def test_knight_castling_does_not_hang():
    # Раньше проверка пути для коня никогда не доходила до цели и зависала навсегда.
    pos = board(n=((0, 0), ('w', 'N')), r=((1, 2), ('w', 'R')))
    result = []
    t = threading.Thread(target=lambda: result.append(compute_castle_moves(pos, 0, 0, 'w')), daemon=True)
    t.start()
    t.join(timeout=5)
    assert result == [[(1, 2)]]


def test_sliders_swap_only_through_empty_squares():
    pos = board(q=((2, 2), ('w', 'Q')), b=((5, 5), ('w', 'B')))
    assert can_castle(pos, 2, 2, 5, 5, 'w')
    pos[(3, 3)] = ('b', 'P')
    assert not can_castle(pos, 2, 2, 5, 5, 'w')


def test_pawns_never_castle():
    pos = board(q=((2, 2), ('w', 'Q')), p=((3, 3), ('w', 'P')))
    assert not can_castle(pos, 2, 2, 3, 3, 'w')


def test_king_castles_only_on_back_rank():
    pos = {(5, 0): ('w', 'K'), (6, 0): ('w', 'J'), (0, 11): ('b', 'K')}
    assert (6, 0) in compute_castle_moves(pos, 5, 0, 'w')
    moved = {(5, 1): ('w', 'K'), (6, 1): ('w', 'J'), (0, 11): ('b', 'K')}
    assert compute_castle_moves(moved, 5, 1, 'w') == []


def test_king_cannot_castle_out_of_check():
    pos = {(5, 0): ('w', 'K'), (6, 0): ('w', 'J'), (5, 9): ('b', 'R'), (0, 11): ('b', 'K')}
    assert (6, 0) not in compute_castle_moves(pos, 5, 0, 'w')
