"""Рокировка-обмен: любые две свои фигуры меняются местами (см. README)."""

from core.board import KING_BACK_ROW
from core.attacks import is_square_attacked, is_square_attacked_by_piece


def is_aligned(c1, r1, c2, r2):
    return c1 == c2 or r1 == r2 or abs(c1 - c2) == abs(r1 - r2)


def is_path_clear(position, c1, r1, c2, r2):
    # Не на одной линии — значит, бьёт конь или орёл: они прыгают, путь не нужен.
    # (Без этой проверки цикл ниже никогда не доходил до цели и зависал.)
    if not is_aligned(c1, r1, c2, r2):
        return True
    dc = (c2 > c1) - (c2 < c1)
    dr = (r2 > r1) - (r2 < r1)
    nc, nr = c1 + dc, r1 + dr
    while (nc, nr) != (c2, r2):
        if (nc, nr) in position:
            return False
        nc += dc
        nr += dr
    return True


def is_adjacent(c1, r1, c2, r2):
    return abs(c1 - c2) <= 1 and abs(r1 - r2) <= 1 and (c1 != c2 or r1 != r2)


def is_king_castle_safe(position, king_c, king_r, partner_c, partner_r, color):
    enemy = 'b' if color == 'w' else 'w'
    if is_square_attacked(position, king_c, king_r, enemy):
        return False
    dc = (partner_c > king_c) - (partner_c < king_c)
    dr = (partner_r > king_r) - (partner_r < king_r)
    cur_c, cur_r = king_c + dc, king_r + dr
    while (cur_c, cur_r) != (partner_c, partner_r):
        if is_square_attacked(position, cur_c, cur_r, enemy):
            return False
        cur_c += dc
        cur_r += dr
    if is_square_attacked(position, partner_c, partner_r, enemy):
        return False
    return True


def can_castle(position, c1, r1, c2, r2, color):
    if (c1, r1) not in position or (c2, r2) not in position:
        return False
    p1_color, p1_type = position[(c1, r1)]
    p2_color, p2_type = position[(c2, r2)]
    if p1_color != color or p2_color != color:
        return False
    if p1_type == 'P' or p2_type == 'P':
        return False

    attack_1_on_2 = is_square_attacked_by_piece(position, c1, r1, c2, r2)
    attack_2_on_1 = is_square_attacked_by_piece(position, c2, r2, c1, r1)
    if not attack_1_on_2 and not attack_2_on_1:
        return False

    if p1_type == 'K':
        king_c, king_r = c1, r1
        partner_c, partner_r = c2, r2
    elif p2_type == 'K':
        king_c, king_r = c2, r2
        partner_c, partner_r = c1, r1
    else:
        king_c = None

    if king_c is not None:
        if king_r != KING_BACK_ROW[color]:
            return False
        if partner_r != KING_BACK_ROW[color]:
            return False
        if not is_adjacent(king_c, king_r, partner_c, partner_r):
            if not is_square_attacked_by_piece(position, partner_c, partner_r,
                                               king_c, king_r):
                return False
            if not is_path_clear(position, king_c, king_r, partner_c, partner_r):
                return False
        if not is_king_castle_safe(position, king_c, king_r,
                                   partner_c, partner_r, color):
            return False
        return True

    if not is_path_clear(position, c1, r1, c2, r2):
        return False
    return True


def compute_castle_moves(position, c, r, color):
    if (c, r) not in position:
        return []
    result = []
    for (oc, or_), (ocolor, otype) in position.items():
        if (oc, or_) == (c, r):
            continue
        if ocolor != color:
            continue
        if can_castle(position, c, r, oc, or_, color):
            result.append((oc, or_))
    return result


def apply_castle(position, c1, r1, c2, r2):
    p1 = position[(c1, r1)]
    p2 = position[(c2, r2)]
    position[(c1, r1)] = p2
    position[(c2, r2)] = p1
