"""Rules for the 'triples' tournament game.

Two teams per board. Each team must hit the triple of every number from 10 up
to 20, in any order the players choose. A dart only counts if it is a triple
of a number the team still has to do. Points per hit are the normal dart value
(T10 = 30 ... T20 = 60). Change TARGETS / points_for_target to tweak the rules.
A team's state is the list of numbers it still has to hit.
"""

TARGETS = list(range(10, 21))


def fresh_remaining():
    return list(TARGETS)


def points_for_target(number):
    return number * 3


def remaining_label(remaining):
    """Short text for a scoreboard: the numbers still to hit, or 'Klaar'."""
    return 'Klaar' if not remaining else ' '.join(str(n) for n in remaining)


def hit_number(dart):
    """The number a dart counts for in this game, or None (only triples count)."""
    if isinstance(dart, str) and dart[:1] == 'T' and dart[1:].isdigit():
        return int(dart[1:])
    return None


def apply_visit(remaining, darts):
    """Return (points, new_remaining) for a list of darts thrown in order."""
    remaining = list(remaining)
    points = 0
    for dart in darts:
        number = hit_number(dart)
        if number in remaining:
            remaining.remove(number)
            points += points_for_target(number)
    return points, remaining


def apply_correction(remaining, score, number, delta):
    """Organiser marks a number as hit (delta > 0) or not hit (delta < 0)."""
    remaining = list(remaining)
    if number not in TARGETS:
        return remaining, score
    if delta > 0 and number in remaining:
        remaining.remove(number)
        score += points_for_target(number)
    elif delta < 0 and number not in remaining:
        remaining.append(number)
        remaining.sort()
        score -= points_for_target(number)
    return remaining, max(0, score)
