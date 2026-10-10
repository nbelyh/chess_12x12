"""Ходы фигур без учёта шаха.

Обозначения: P пешка, N конь, N2 орёл, B слон, R ладья, R2 гепард, Q ферзь, J джинн, K король.
"""

from core.board import PAWN_FORWARD, in_bounds, is_enemy


def compute_en_passant(position, en_passant_move):
    result = {}
    if en_passant_move is None:
        return result
    fc, fr, tc, tr, pawn_color = en_passant_move
    if (tc, tr) not in position:
        return result
    if position[(tc, tr)][1] != 'P' or position[(tc, tr)][0] != pawn_color:
        return result
    our_color = 'b' if pawn_color == 'w' else 'w'
    our_dc, our_dr = PAWN_FORWARD[our_color]
    enemy_dc, enemy_dr = PAWN_FORWARD[pawn_color]
    for (c, r), (pc, pt) in position.items():
        if pc != our_color or pt != 'P':
            continue
        if enemy_dc == 0:
            if abs(c - fc) != 1:
                continue
            step_dir = 1 if tr > fr else -1
            for mid_r in range(fr + step_dir, tr, step_dir):
                for ddc in [-1, +1]:
                    if c + ddc == fc and r + our_dr == mid_r:
                        if (fc, mid_r) not in position:
                            result[(fc, mid_r)] = (tc, tr)
                        break
        else:
            if abs(r - fr) != 1:
                continue
            step_dir = 1 if tc > fc else -1
            for mid_c in range(fc + step_dir, tc, step_dir):
                for ddr in [-1, +1]:
                    if c + our_dc == mid_c and r + ddr == fr:
                        if (mid_c, fr) not in position:
                            result[(mid_c, fr)] = (tc, tr)
                        break
    return result


def sliding_moves(position, c, r, color, directions):
    moves = []
    for dc, dr in directions:
        nc, nr = c + dc, r + dr
        while in_bounds(nc, nr):
            if (nc, nr) in position:
                if is_enemy(color, position[(nc, nr)][0]):
                    moves.append((nc, nr))
                break
            moves.append((nc, nr))
            nc += dc
            nr += dr
    return moves


def king_moves(position, c, r, color):
    moves = []
    for dc in [-1, 0, 1]:
        for dr in [-1, 0, 1]:
            if dc == 0 and dr == 0:
                continue
            nc, nr = c + dc, r + dr
            if not in_bounds(nc, nr):
                continue
            if (nc, nr) in position:
                if is_enemy(color, position[(nc, nr)][0]):
                    moves.append((nc, nr))
            else:
                moves.append((nc, nr))
    return moves


def knight_moves(position, c, r, color):
    moves = []
    for dc, dr in [(1, 2), (2, 1), (-1, 2), (-2, 1),
                   (1, -2), (2, -1), (-1, -2), (-2, -1)]:
        nc, nr = c + dc, r + dr
        if not in_bounds(nc, nr):
            continue
        if (nc, nr) in position:
            if is_enemy(color, position[(nc, nr)][0]):
                moves.append((nc, nr))
        else:
            moves.append((nc, nr))
    return moves


def eagle_moves(position, c, r, color):
    moves = []
    for dc, dr in [(1, 3), (3, 1), (-1, 3), (-3, 1),
                   (1, -3), (3, -1), (-1, -3), (-3, -1)]:
        nc, nr = c + dc, r + dr
        if not in_bounds(nc, nr):
            continue
        if (nc, nr) in position:
            if is_enemy(color, position[(nc, nr)][0]):
                moves.append((nc, nr))
        else:
            moves.append((nc, nr))
    return moves


def cheetah_moves(position, c, r, color):
    moves = []
    for dc, dr in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
        nc, nr = c + dc, r + dr
        jumped = False
        while in_bounds(nc, nr):
            if (nc, nr) in position:
                target_color, target_type = position[(nc, nr)]
                if is_enemy(color, target_color):
                    moves.append((nc, nr))
                    break
                else:
                    if jumped:
                        break
                    jc, jr = nc + dc, nr + dr
                    if not in_bounds(jc, jr):
                        break
                    if (jc, jr) in position:
                        break
                    moves.append((jc, jr))
                    jumped = True
                    break
            else:
                moves.append((nc, nr))
            nc += dc
            nr += dr
    return moves


def cheetah_moves_second(position, c, r, color):
    moves = []
    for dc, dr in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
        nc, nr = c + dc, r + dr
        while in_bounds(nc, nr):
            if (nc, nr) in position:
                break
            moves.append((nc, nr))
            nc += dc
            nr += dr
    return moves


def genie_moves(position, c, r, color):
    moves = []
    directions = [
        (0, -1), (0, 1), (-1, 0), (1, 0),
        (-1, -1), (-1, 1), (1, -1), (1, 1),
    ]
    for dc, dr in directions:
        nc, nr = c + dc, r + dr
        while in_bounds(nc, nr):
            if (nc, nr) in position:
                target_color, target_type = position[(nc, nr)]
                if is_enemy(color, target_color):
                    moves.append((nc, nr))
                    break
                else:
                    jc, jr = nc + dc, nr + dr
                    if not in_bounds(jc, jr):
                        break
                    if (jc, jr) in position:
                        break
                    moves.append((jc, jr))
                    break
            else:
                moves.append((nc, nr))
            nc += dc
            nr += dr
    return moves


def pawn_moves(position, c, r, color, moved_pawns, en_passant_moves):
    moves = []
    dc, dr = PAWN_FORWARD[color]
    on_start = (c, r) not in moved_pawns
    max_steps = 3 if on_start else 2
    for step in range(1, max_steps + 1):
        nc, nr = c + dc * step, r + dr * step
        if not in_bounds(nc, nr):
            break
        if (nc, nr) in position:
            break
        moves.append((nc, nr))
    diagonals = [(-1, dr), (+1, dr)]
    for ddc, ddr in diagonals:
        nc, nr = c + ddc, r + ddr
        if not in_bounds(nc, nr):
            continue
        if (nc, nr) in position:
            if is_enemy(color, position[(nc, nr)][0]):
                moves.append((nc, nr))
    for (tc, tr) in en_passant_moves.keys():
        for ddc, ddr in diagonals:
            if c + ddc == tc and r + ddr == tr:
                moves.append((tc, tr))
                break
    return moves


def get_moves(position, c, r, color, moved_pawns, en_passant_moves):
    if (c, r) not in position:
        return []
    pc, pt = position[(c, r)]
    if pt == 'P':
        return pawn_moves(position, c, r, pc, moved_pawns, en_passant_moves)
    elif pt == 'N':
        return knight_moves(position, c, r, pc)
    elif pt == 'N2':
        return eagle_moves(position, c, r, pc)
    elif pt == 'R2':
        return cheetah_moves(position, c, r, pc)
    elif pt == 'J':
        return genie_moves(position, c, r, pc)
    elif pt == 'R':
        return sliding_moves(position, c, r, pc,
                             [(0, -1), (0, 1), (-1, 0), (1, 0)])
    elif pt == 'B':
        return sliding_moves(position, c, r, pc,
                             [(-1, -1), (-1, 1), (1, -1), (1, 1)])
    elif pt == 'Q':
        return sliding_moves(position, c, r, pc,
                             [(-1, -1), (-1, 1), (1, -1), (1, 1),
                              (0, -1), (0, 1), (-1, 0), (1, 0)])
    elif pt == 'K':
        return king_moves(position, c, r, pc)
    return []
