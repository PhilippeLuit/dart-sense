"""Rules for the 'triples' tournament game.

Two teams per board. Each team climbs its own ladder: it must hit the triple
of its current target before moving on to the next number. Only a dart that
hits the current target counts. Change LADDER / points_for_target to tweak the
rules; the manual board page (static/board.html) has the same ladder in JS.
"""

LADDER = list(range(10, 21)) + ['B']  # T10 ... T20, then bull finishes the ladder


def target_label(index):
    if index >= len(LADDER):
        return 'Done'
    target = LADDER[index]
    return 'Bull' if target == 'B' else f'T{target}'


def points_for_target(target):
    return 50 if target == 'B' else target * 3


def is_hit(dart, target):
    if target == 'B':
        return dart == 'DB'
    return dart == f'T{target}'


def apply_visit(target_index, darts):
    """Return (points, new_target_index) for a list of darts thrown in order."""
    points = 0
    for dart in darts:
        if target_index >= len(LADDER):
            break
        target = LADDER[target_index]
        if is_hit(dart, target):
            points += points_for_target(target)
            target_index += 1
    return points, target_index
