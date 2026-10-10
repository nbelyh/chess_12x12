"""Доска 12x12: размеры, константы и начальная расстановка."""

BOARD_SIZE = 12

TURN_ORDER = ['w', 'b']
PROMOTION_CHOICES = ['Q', 'R', 'B', 'N']
PAWN_FORWARD = {'w': (0, +1), 'b': (0, -1)}
PAWN_PROMOTION_LINE = {'w': 11, 'b': 0}

KING_BACK_ROW = {'w': 0, 'b': 11}


def other(color):
    return 'b' if color == 'w' else 'w'


def is_enemy(c1, c2):
    return c1 != c2


def initial_position():
    pos = {}
    pos[(3, 0)] = ('w', 'R2')
    pos[(4, 0)] = ('w', 'N2')
    pos[(5, 0)] = ('w', 'K')
    pos[(6, 0)] = ('w', 'J')
    pos[(7, 0)] = ('w', 'N2')
    pos[(8, 0)] = ('w', 'R2')

    pos[(2, 1)] = ('w', 'R')
    pos[(3, 1)] = ('w', 'N')
    pos[(4, 1)] = ('w', 'B')
    pos[(5, 1)] = ('w', 'Q')
    pos[(6, 1)] = ('w', 'Q')
    pos[(7, 1)] = ('w', 'B')
    pos[(8, 1)] = ('w', 'N')
    pos[(9, 1)] = ('w', 'R')

    for c in range(12):
        pos[(c, 2)] = ('w', 'P')

    for (c, r), (color, typ) in list(pos.items()):
        if color == 'w':
            mirror_c = 11 - c
            mirror_r = 11 - r
            pos[(mirror_c, mirror_r)] = ('b', typ)

    return pos


def in_bounds(c, r):
    return 0 <= c < BOARD_SIZE and 0 <= r < BOARD_SIZE


def is_promotion_square_for(color, c, r):
    return r == PAWN_PROMOTION_LINE[color]
