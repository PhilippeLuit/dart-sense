"""Rules for the 'triples' tournament game.

Two teams per board. Each team must complete every number from 10 up to 20,
in any order the players choose. A number is complete after three hits on it:
a single counts one hit, a double two, a triple three. Hits beyond the third
on a number count for nothing. Points per hit are the number's value, so a
completed number is always worth three times the number (10 -> 30, 20 -> 60).

A team's state is a list with the number of hits (0..3) per number, in the
order of TARGETS. Change TARGETS, HITS_NEEDED or points_per_hit to tweak the
rules; the three pages under static/ carry the same TARGETS and HITS_NEEDED.
"""

TARGETS = list(range(10, 21))
HITS_NEEDED = 3


def fresh_progress():
    return [0] * len(TARGETS)


def points_per_hit(number):
    return number


def dart_hits(dart):
    """(number, hits) for a dart that can count in this game, else None."""
    if not isinstance(dart, str) or len(dart) < 2 or not dart[1:].isdigit():
        return None
    hits = {'S': 1, 'D': 2, 'T': 3}.get(dart[0])
    number = int(dart[1:])
    if hits is None or number not in TARGETS:
        return None
    return number, hits


def remaining(progress):
    """Numbers not yet complete."""
    return [n for n, h in zip(TARGETS, progress) if h < HITS_NEEDED]


def remaining_label(progress):
    """Short text for a scoreboard: open numbers with their hits so far, or 'Klaar'."""
    parts = [f'{n}' if h == 0 else f'{n}:{h}' for n, h in zip(TARGETS, progress) if h < HITS_NEEDED]
    return 'Klaar' if not parts else ' '.join(parts)


def _add_hits(progress, score, number, hits):
    idx = TARGETS.index(number)
    counted = max(0, min(hits, HITS_NEEDED - progress[idx]))
    progress[idx] += counted
    return score + counted * points_per_hit(number)


def apply_visit(progress, darts):
    """Return (points, new_progress) for a list of darts thrown in order."""
    progress = list(progress)
    points = 0
    for dart in darts:
        hit = dart_hits(dart)
        if hit:
            points = _add_hits(progress, points, *hit)
    return points, progress


def apply_correction(progress, score, number, delta):
    """One tap: delta > 0 adds a hit on the number, delta < 0 takes one back."""
    progress = list(progress)
    if number not in TARGETS:
        return progress, score
    idx = TARGETS.index(number)
    if delta > 0 and progress[idx] < HITS_NEEDED:
        progress[idx] += 1
        score += points_per_hit(number)
    elif delta < 0 and progress[idx] > 0:
        progress[idx] -= 1
        score -= points_per_hit(number)
    return progress, max(0, score)


def normalise_progress(values):
    """Clamp a list from the network to valid hit counts."""
    out = fresh_progress()
    for i, v in enumerate(list(values)[:len(TARGETS)]):
        try:
            out[i] = max(0, min(HITS_NEEDED, int(v)))
        except (TypeError, ValueError):
            pass
    return out
