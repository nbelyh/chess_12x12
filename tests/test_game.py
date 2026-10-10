"""Ход партии: core.game.Game."""

import pytest

from core.game import Game, MoveError


def game_with(position, current='w'):
    g = Game()
    g.position = dict(position)
    g.current = current
    g._legal = None
    return g


KINGS = {(11, 0): ('w', 'K'), (0, 11): ('b', 'K')}


def test_new_game_white_to_move():
    g = Game()
    assert g.current == 'w' and not g.over
    assert (5, 2) in g.legal_moves()           # пешка f3 может ходить


def test_move_switches_turn_and_records_last_move():
    g = Game()
    g.move('w', (5, 2), (5, 5))
    assert g.current == 'b'
    assert g.position[(5, 5)] == ('w', 'P') and (5, 2) not in g.position
    assert g.last_move == ((5, 2), (5, 5))


def test_rejects_wrong_turn_and_illegal_moves():
    g = Game()
    with pytest.raises(MoveError):
        g.move('b', (5, 9), (5, 8))
    with pytest.raises(MoveError):
        g.move('w', (5, 2), (5, 6))              # 4 клетки
    with pytest.raises(MoveError):
        g.move('w', (0, 5), (0, 6))              # пустое поле


def test_en_passant_over_a_triple_step():
    # Белая пешка идёт f3 -> f6 и проскакивает f5, которое бьёт чёрная пешка e6.
    g = game_with({**KINGS, (5, 2): ('w', 'P'), (4, 5): ('b', 'P')})
    g.move('w', (5, 2), (5, 5))
    assert g.legal_moves()[(4, 5)][(5, 4)] == 'ep'
    state = g.to_dict('b')
    assert [5, 4, 'ep', [5, 5]] in state['legal']['4,5']
    g.move('b', (4, 5), (5, 4))
    assert (5, 5) not in g.position              # белая пешка взята
    assert g.position[(5, 4)] == ('b', 'P')


def test_en_passant_is_only_for_pawns():
    g = game_with({**KINGS, (5, 2): ('w', 'P'), (4, 5): ('b', 'P'), (4, 6): ('b', 'N')})
    g.move('w', (5, 2), (5, 5))
    assert g.legal_moves()[(4, 6)].get((5, 4)) == 'move'   # конь просто встаёт на поле
    g.move('b', (4, 6), (5, 4))
    assert g.position[(5, 5)] == ('w', 'P')


def test_promotion_waits_for_choice():
    g = game_with({**KINGS, (2, 10): ('w', 'P')})
    g.moved_pawns.add((2, 10))
    g.move('w', (2, 10), (2, 11))
    assert g.promotion_pending == (2, 11, 'w')
    assert g.current == 'w' and g.legal_moves() == {}
    with pytest.raises(MoveError):
        g.promote('b', 'Q')
    with pytest.raises(MoveError):
        g.promote('w', 'K')
    g.promote('w', 'N')
    assert g.position[(2, 11)] == ('w', 'N')
    assert g.current == 'b' and g.promotion_pending is None


def test_checkmate_ends_the_game():
    g = game_with({(0, 11): ('b', 'K'), (0, 10): ('b', 'P'), (1, 10): ('b', 'P'),
                   (5, 0): ('w', 'R'), (11, 0): ('w', 'K')})
    g.move('w', (5, 0), (5, 11))
    assert g.result == 'mate' and g.winner == 'w'
    assert g.to_dict('b')['check'] == [[0, 11]]
    with pytest.raises(MoveError):
        g.move('b', (0, 11), (1, 11))


def test_stalemate_is_a_draw():
    g = game_with({(0, 11): ('b', 'K'), (2, 10): ('w', 'Q'), (11, 0): ('w', 'K')})
    g.move('w', (11, 0), (11, 1))
    assert g.result == 'stalemate' and g.winner is None


def test_castle_swaps_pieces():
    g = game_with({(5, 0): ('w', 'K'), (6, 0): ('w', 'J'), (0, 11): ('b', 'K')})
    assert g.legal_moves()[(5, 0)][(6, 0)] == 'castle'
    g.move('w', (5, 0), (6, 0))
    assert g.position[(5, 0)] == ('w', 'J') and g.position[(6, 0)] == ('w', 'K')


def test_cheetah_double_move():
    g = game_with({**KINGS, (5, 5): ('w', 'R2')})
    assert g.legal_moves()[(5, 5)][(6, 6)] == 'double'
    g.move('w', (5, 5), (6, 6))
    assert g.position[(6, 6)] == ('w', 'R2') and g.current == 'b'


def test_resign_and_draw_votes():
    g = Game()
    g.toggle_draw('w')
    assert not g.over
    g.toggle_draw('w')                           # передумал
    g.toggle_draw('b')
    assert not g.over
    g.toggle_draw('w')
    assert g.result == 'draw'

    g = Game()
    g.resign('b')
    assert g.result == 'resign' and g.winner == 'w' and g.resigned_by == 'b'
    with pytest.raises(MoveError):
        g.resign('w')


def test_undo_restores_previous_position():
    g = Game()
    before = dict(g.position)
    g.move('w', (5, 2), (5, 5))
    g.move('b', (6, 9), (6, 8))
    g.undo()
    assert g.current == 'b' and (6, 9) in g.position
    g.undo()
    assert g.position == before and g.current == 'w' and g.last_move is None
    with pytest.raises(MoveError):
        g.undo()


def test_legal_moves_sent_only_to_player_on_move():
    g = Game()
    assert g.to_dict('w')['legal']
    assert g.to_dict('b')['legal'] == {}
    assert g.to_dict(None)['legal'] == {}
