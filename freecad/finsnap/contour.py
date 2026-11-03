# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""The fin under a round side that follows the contour of the part.

A part standing on the rim of a round side leans that side over the bed; its
fin stands under the lowest line. Above the side the part goes on, thinner or
thicker, through chamfers, fillets and curves. Cut by the upright plane
through the lowest line, in which the fin stands, the part shows that contour.

The contour is the outer rim of that cut from the point the part stands on
up to its highest point, the front way round: the side the fin stands on.
A separate piece of the cut, the far wall of a tube, is not part of it.

The flank follows the whole contour, the gap away from every part of the
cut, over steps and end faces alike; recesses lower than the bridge it spans
straight. It never runs inward up the part more steeply than FIN_FLANK_ANGLE
allows, so the fin itself prints without an overhang.

Tines rest only where the contour faces down, where the part lies over them
and they hold it; on a face looking up they would be printed onto the part,
and an upright one, such as a chamfer the tilt stands upright, needs no hold.

Heights are measured from the bed of the frame, positions outward along `out`
of the frame, as `s` in geometry.Frame.

INPUTS this has to withstand (Contour):
  plain cylinder on its rim             ->  flank as the plane of the side gives it,
                                            every tine resting, up to the front top edge
  step to a thinner part above, its
    end face looking up                 ->  flank along the end face, no tine on it;
                                            tines from the bottom of the thinner part on
  end face falling back steeper than
    FIN_FLANK_ANGLE                     ->  flank held at that angle, further off the
                                            part; tines it holds off left out, as
                                            receded()
  chamfer the tilt stands upright       ->  followed, no tine on it
  step to a thicker part above          ->  flank steps out, tines rest on it
  chamfer, fillet, hole or groove lower
    than the bridge                     ->  bridged: flank straight across, tines there
                                            left out, not receded()
  the same higher than the bridge       ->  followed
  bridge 0                              ->  every recess followed
  spline or Bezier curve in the contour ->  cut into pieces within CONTOUR_DEFLECTION,
                                            followed
  tube                                  ->  its front wall alone: the fin ends at the
                                            front top edge, not over the bore
  end face on top                       ->  looks up: no tine, the fin ends below it
  bump of the part towards the fin      ->  flank out past it, never closer than the gap
  plane misses the part                 ->  ContourError

INPUTS this has to withstand (reach()):
  height on a sloping piece             ->  the point on it, `radius` out along its normal
  height on a horizontal piece          ->  its outer end, or a corner `radius` out
  height above or below every piece by
    more than `radius`                  ->  None
  radius 0                              ->  the outermost point of the cut at that height
"""

import bisect
import math

import Part

from . import defaults as d
from .i18n import translate
from .shapes import bounds, keep, shape_key

# Places to which the ends of the pieces of a cut are compared, to join them.
JOIN_DECIMALS = 4
# Contours worked out, by part, plane and parameters (shapes.keep()): a fin
# dragged or set higher is built again and again on the same part.
_kept = {}


class ContourError(ValueError):
    """The contour of the part cannot be found."""


def cut_of(part, frame, t):
    """The cut of `part` with the upright plane at `t` along the face of
    `frame`, as lines of (s, z) points, one per edge, z from the bed."""
    box = bounds(part)
    size = 2 * box.DiagonalLength
    low, high = box.ZMin - 1, box.ZMax + 1
    ring = [frame.point(t, s, z) for s, z in ((-size, low), (size, low), (size, high), (-size, high))]
    cut = part.section(Part.Face(Part.makePolygon(ring + ring[:1])))
    lines = [[(point.dot(frame.out), point.z - frame.bed_z)
              for point in edge.discretize(Deflection=d.CONTOUR_DEFLECTION)]
             for edge in cut.Edges if not edge.Degenerated]
    lines = [line for line in lines if len(line) > 1]
    if not lines:
        raise ContourError(translate("FinSnap", "the plane of the fin does not cut the part"))
    return lines


def _key(point):
    return tuple(round(value, JOIN_DECIMALS) for value in point)


def loops_of(lines):
    """The lines of a cut joined end to end into loops, each a list of
    points, its last one again its first where it closes."""
    left = [list(line) for line in lines]
    loops = []
    while left:
        loop = left.pop()
        joined = True
        while joined:
            joined = False
            for i, other in enumerate(left):
                if _key(loop[-1]) == _key(other[0]):
                    loop += other[1:]
                elif _key(loop[-1]) == _key(other[-1]):
                    loop += other[-2::-1]
                elif _key(loop[0]) == _key(other[-1]):
                    loop = other[:-1] + loop
                elif _key(loop[0]) == _key(other[0]):
                    loop = other[:0:-1] + loop
                else:
                    continue
                left.pop(i)
                joined = True
                break
        loops.append(loop)
    return loops


def _mitre(first, second):
    """How far past their corner, per mm of the gap, the lines the gap away
    from two pieces running along `first` and `second` (unit directions)
    meet: tan of half the angle they turn by, at most CONTOUR_MITRE_LIMIT;
    0 where either is missing."""
    if first is None or second is None:
        return 0.0
    turn = max(-1.0, min(1.0, first[0] * second[0] + first[1] * second[1]))
    if turn <= -1.0 + d.TOLERANCE:
        return d.CONTOUR_MITRE_LIMIT
    return min(math.sqrt((1 - turn) / (1 + turn)), d.CONTOUR_MITRE_LIMIT)


def loop_pieces(loop, close=False):
    """The pieces of `loop` in its order: ((s, z), (s, z), mitre at the
    start, mitre at the end, outward normal). The normal points out of the
    part, the way round the loop runs tells which, for a loop that closes,
    or with `close`, closed where it does not; None for an open one, which
    gets no mitres either: without knowing the side of the part, a corner
    is not known to be one to run on past. The mitres let the line the gap away from a piece
    run on to where it meets that of the next, so the fin has a sharp corner
    where the part has one (_mitre())."""
    points = [loop[0]]
    for point in loop[1:]:
        if math.hypot(point[0] - points[-1][0], point[1] - points[-1][1]) > d.TOLERANCE:
            points.append(point)
    closed = _key(points[0]) == _key(points[-1])
    if close and not closed:
        points.append(points[0])
        closed = True
    area = sum(s0 * z1 - s1 * z0 for (s0, z0), (s1, z1) in zip(points, points[1:]))
    sense = 1 if area > 0 else -1
    runs = []
    for (s0, z0), (s1, z1) in zip(points, points[1:]):
        length = math.hypot(s1 - s0, z1 - z0)
        runs.append(((s1 - s0) / length, (z1 - z0) / length))
    count = len(runs)
    pieces = []
    for k, ((start, end), (us, uz)) in enumerate(zip(zip(points, points[1:]), runs)):
        # Turned a right angle against the way round: out of the part.
        if closed:
            pieces.append((start, end, _mitre(runs[k - 1], runs[k]), _mitre(runs[k], runs[(k + 1) % count]),
                           (sense * uz, -sense * us)))
        else:
            pieces.append((start, end, 0.0, 0.0, None))
    return pieces


def front_of(loops):
    """The pieces of the contour (loop_pieces()), the front way round from
    the point the part stands on to the highest point of its loop."""
    pieces = loop_pieces(min(loops, key=lambda points: min(z for _, z in points)), close=True)
    count = len(pieces)
    starts = [piece[0] for piece in pieces]
    lowest = min(z for _, z in starts)
    start = max((k for k in range(count) if starts[k][1] < lowest + d.TOLERANCE), key=lambda k: starts[k][0])
    top = max(range(count), key=lambda k: starts[k][1])
    # Of the two ways round from the start, the front one leaves it further out.
    forward = starts[(start + 1) % count][0] >= starts[(start - 1) % count][0]
    front = []
    k = start
    while k != top:
        if forward:
            front.append(pieces[k])
            k = (k + 1) % count
        else:
            k = (k - 1) % count
            front.append(pieces[k])
    return front


def _heights_of(piece, radius):
    """The lowest and highest the points within `radius` of `piece` lie,
    the line the gap away from it run on to its corners."""
    heights = [z for _, z in piece[:2]] + [z for line in _shifted(piece, radius) for _, z in line]
    return min(heights) - radius, max(heights) + radius


def _piece_reach(piece, z, radius):
    """How far out the points within `radius` of the straight `piece` reach at
    height z, None where none lies at that height: the ends as circles and
    the piece moved `radius` out along its normal."""
    return _reach_between(piece, z, z, radius)


def reach(pieces, z, radius):
    """How far out the points within `radius` of the pieces reach at height
    z, None where none does."""
    found = [r for r in (_piece_reach(piece, z, radius) for piece in pieces) if r is not None]
    return max(found) if found else None


def _over_heights(pieces, heights, radius, measure):
    """At every one of the evenly spaced `heights`, how far out the pieces
    reach within `radius`, kept with `measure`(piece) of the piece reaching
    furthest: (reach, value), or None where none reaches. Of pieces reaching
    as far, within TOLERANCE, as two do where they meet, the smallest value
    is kept, so where they meet does not hang on their order."""
    first, step = heights[0], heights[1] - heights[0]
    found = [None] * len(heights)
    for piece in pieces:
        low, high = _heights_of(piece, radius)
        start = max(0, math.ceil((low - first) / step - d.TOLERANCE))
        end = min(len(heights) - 1, math.floor((high - first) / step + d.TOLERANCE))
        value = measure(piece)
        for k in range(start, end + 1):
            r = _piece_reach(piece, heights[k], radius)
            if r is None:
                continue
            best = found[k]
            if best is None or r > best[0] + d.TOLERANCE:
                found[k] = (r, value)
            elif r >= best[0] - d.TOLERANCE:
                smaller = value if best[1] is None or (value is not None and value < best[1]) else best[1]
                found[k] = (max(r, best[0]), smaller)
    return found


def _shifted(piece, radius):
    """The lines `radius` away from the straight `piece` that bound how far
    out its gap reaches, each run on at either end by its mitre to where it
    meets that of the next piece: the one out of the part, where its loop
    tells which side that is; where it does not, the one towards larger s,
    the fin's side, both, above and below, for a piece lying level. None for
    a piece without length."""
    (s0, z0), (s1, z1), before, after, outward = piece
    length = math.hypot(s1 - s0, z1 - z0)
    if length <= 0:
        return []
    us, uz = (s1 - s0) / length, (z1 - z0) / length
    if outward is not None:
        normals = [outward]
    elif abs(uz) > d.TOLERANCE:
        normals = [(uz, -us) if uz > 0 else (-uz, us)]
    else:
        normals = [(0.0, 1.0), (0.0, -1.0)]
    return [((s0 + (ns - us * before) * radius, z0 + (nz - uz * before) * radius),
             (s1 + (ns + us * after) * radius, z1 + (nz + uz * after) * radius)) for ns, nz in normals]


def _line_between(shifted, low, high):
    """How far out the straight `shifted` reaches anywhere between the
    heights `low` and `high`, None where it lies outside them: at one end of
    where it runs between them, either end where it lies level."""
    (a_s, a_z), (b_s, b_z) = sorted(shifted, key=lambda point: point[1])
    start, end = max(low, a_z), min(high, b_z)
    if start > end + d.TOLERANCE:
        return None
    if b_z - a_z <= d.TOLERANCE:
        return max(a_s, b_s)
    return max(a_s + (b_s - a_s) * (z - a_z) / (b_z - a_z) for z in (min(start, b_z), max(end, a_z)))


def _reach_between(piece, low, high, radius):
    """How far out the points within `radius` of `piece` reach anywhere
    between the heights `low` and `high`, None where none lies there. Within
    TOLERANCE counts as there: the point the part stands on lies at the bed
    give or take a rounding."""
    found = []
    for s, z in piece[:2]:
        nearest = min(max(z, low), high)
        rise = nearest - z
        if abs(rise) <= radius + d.TOLERANCE:
            found.append(s + math.sqrt(max(0.0, radius * radius - rise * rise)))
    found += [r for r in (_line_between(line, low, high) for line in _shifted(piece, radius)) if r is not None]
    return max(found) if found else None


def _near(pieces, heights, radius):
    """For each stretch between two of the evenly spaced `heights`, the
    pieces that reach into it within `radius`: what reach() and _lifted()
    need to look at there, not every piece of the cut."""
    first, step = heights[0], heights[1] - heights[0]
    near = [[] for _ in heights[:-1]]
    for piece in pieces:
        low, high = _heights_of(piece, radius)
        start = max(0, math.floor((low - first) / step))
        end = min(len(near) - 1, math.floor((high - first) / step))
        for k in range(start, end + 1):
            near[k].append(piece)
    return near


def _stretch(heights, z):
    """The number of the stretch between two of the evenly spaced `heights`
    that holds z."""
    first, step = heights[0], heights[1] - heights[0]
    return min(len(heights) - 2, max(0, int(math.floor((z - first) / step))))


def _past_chord(piece, low, high, chord, radius):
    """How far the points within `radius` of `piece` reach past the straight
    `chord`, a function of the height, anywhere between `low` and `high`;
    None where none lies there. A circle round an end of the piece reaches
    furthest past where its slope is that of the chord, its moved line at
    one end of where it lies between."""
    slope = chord(high) - chord(low)
    slope = slope / (high - low) if high > low else 0.0
    found = []
    for s, zc in piece[:2]:
        start, end = max(low, zc - radius), min(high, zc + radius)
        if start > end:
            continue
        tangent = zc - slope * radius / math.sqrt(1 + slope * slope)
        for z in (start, end, min(max(tangent, start), end)):
            found.append(s + math.sqrt(max(0.0, radius * radius - (z - zc) ** 2)) - chord(z))
    for line in _shifted(piece, radius):
        (a_s, a_z), (b_s, b_z) = sorted(line, key=lambda point: point[1])
        start, end = max(low, a_z), min(high, b_z)
        if b_z - a_z <= d.TOLERANCE:
            if start <= end + d.TOLERANCE:
                found.append(max(a_s, b_s) - chord(min(max(a_z, low), high)))
        else:
            for z in ((start, end) if start <= end else ()):
                found.append(a_s + (b_s - a_s) * (z - a_z) / (b_z - a_z) - chord(z))
    return max(found) if found else None


def _lifted(values, near, heights, radius):
    """`values`, the reach of the pieces `near` each stretch within `radius`
    at `heights`, lifted where the straight run between two samples would
    come closer to the part than CONTOUR_MARGIN covers, a corner or the
    start of a circle between them: both raised to the most the part reaches
    between them, the run then outside it. On a smooth contour nothing is
    raised."""
    raised = [-math.inf] * len(values)
    result = list(values)
    for k, pieces in enumerate(near):
        low, high = heights[k], heights[k + 1]
        if values[k] is None or values[k + 1] is None:
            # The contour starts or ends here: the sample without a reach
            # gets the most it reaches between.
            found = [r for r in (_reach_between(piece, low, high, radius) for piece in pieces) if r is not None]
            for j in (k, k + 1):
                if found and result[j] is None:
                    result[j] = max(found)
            continue
        a, b = values[k], values[k + 1]

        def chord(z, a=a, b=b, low=low, high=high):
            return a + (b - a) * (z - low) / (high - low)

        found = [r for r in (_past_chord(piece, low, high, chord, radius) for piece in pieces) if r is not None]
        if found and max(found) > d.CONTOUR_MARGIN / 2:
            most = max(r for r in (_reach_between(piece, low, high, radius) for piece in pieces) if r is not None)
            raised[k], raised[k + 1] = max(raised[k], most), max(raised[k + 1], most)
    return [value if value is None else max(value, up) for value, up in zip(result, raised)]


def _closed(values, width):
    """`values` with every dip narrower than `width` samples spanned by a
    straight line from its one edge to the other. A dip is found as what the
    largest within half the width either way, then the smallest of those,
    lifts. None counts as lower than any value."""
    raw = [-math.inf if v is None else v for v in values]
    if width < 1:
        return raw
    half = width // 2
    count = len(raw)
    # Grown also half a width past either end, where nothing lies: without,
    # a contour rising from the first sample would count as a dip there.
    grown = [max(raw[max(0, k - half):max(0, k + half + 1)]) for k in range(-half, count + half)]
    shut = [min(grown[k:k + 2 * half + 1]) for k in range(count)]
    return _spanned(raw, [lifted <= value + d.TOLERANCE for lifted, value in zip(shut, raw)])


def _spanned(values, holds):
    """`values` with a straight line laid between every two samples that
    `holds` at either end of a stretch that does not, wherever that line
    stands further out."""
    result = list(values)
    held = [k for k, hold in enumerate(holds) if hold]
    for below, above in zip(held, held[1:]):
        if above - below < 2:
            continue
        a, b = values[below], values[above]
        for k in range(below + 1, above):
            line = a + (b - a) * (k - below) / (above - below)
            result[k] = max(result[k], line)
    return result


def _held(values, least, carries):
    """`values` where the contour carries no tine held at most as far out as
    the flank stands where such a stretch starts, never less than `least`,
    the gap where tines rest: the flank there does not step out where the
    larger gap starts, so over an upright chamfer and the end face looking
    up above it the fin keeps its edge upright, without a notch, until the
    larger gap is kept of itself."""
    result = list(values)
    entering = None
    for k, carry in enumerate(carries):
        if carry:
            entering = None
            continue
        if entering is None:
            entering = result[k - 1] if k > 0 else result[k]
        result[k] = max(least[k], min(result[k], entering))
    return result


def _on_one_line(values, heights, below, above, run):
    """Whether `values` at `above` lie where the straight run of `values`
    ending at `below` leads, within CONTOUR_SAME_LINE: the contour goes on
    on the same face after the stretch between, as past a pocket. The run
    is measured over `run` samples."""
    start = max(0, below - run)
    if start == below:
        return False
    slope = (values[below] - values[start]) / (heights[below] - heights[start])
    led = values[below] + slope * (heights[above] - heights[below])
    return abs(led - values[above]) <= d.CONTOUR_SAME_LINE


def _limited(values, inward):
    """`values` from the lowest up, each at most `inward` less than the one
    below it."""
    result = []
    for value in values:
        if result and result[-1] != -math.inf:
            value = max(value, result[-1] - inward)
        result.append(value)
    return result


def _straightened(points, tolerance):
    """`points` without those lying within `tolerance` of the straight run
    between their neighbours kept (Ramer-Douglas-Peucker), the ends kept."""
    if len(points) < 3:
        return points
    (s0, z0), (s1, z1) = points[0], points[-1]
    length = math.hypot(s1 - s0, z1 - z0)
    worst, index = 0.0, 0
    for k in range(1, len(points) - 1):
        s, z = points[k]
        if length > 0:
            off = abs((z1 - z0) * (s - s0) - (s1 - s0) * (z - z0)) / length
        else:
            off = math.hypot(s - s0, z - z0)
        if off > worst:
            worst, index = off, k
    if worst <= tolerance:
        return [points[0], points[-1]]
    return _straightened(points[:index + 1], tolerance)[:-1] + _straightened(points[index:], tolerance)


class Contour:
    """The flank of the fin under a round side along the contour of the part,
    the heights its tines rest on and how far they reach; see the module."""

    def __init__(self, cuts, p):
        """`cuts`, the lines of each cut across the thickness of the fin, the
        middle one first: that one, where the tines stand, gives the contour;
        the gap is kept from all of them, as a hole narrower than the fin
        leaves the cuts beside the middle whole."""
        mitred = [[piece for loop in loops_of(lines) for piece in loop_pieces(loop)] for lines in cuts]
        self.pieces = [piece for pieces in mitred for piece in pieces]
        front = front_of(loops_of(cuts[0]))
        self.clearance = p.clearance
        self.top = max(max(start[1], end[1]) for start, end, *_ in front)
        step = p.layer_height / d.CONTOUR_SAMPLES_PER_LAYER
        self.step = step
        self.heights = [k * step for k in range(int(math.ceil(self.top / step)) + 1)]
        distance = p.fin_offset + d.CONTOUR_MARGIN
        # Over a face looking up the fin keeps the larger gap, so it cannot
        # stick to the part there; never less than where the tines rest.
        apart = max(p.contour_gap, p.fin_offset) + d.CONTOUR_MARGIN
        width = int(round(p.contour_bridge / step))

        def envelope(pieces, gap, lifted=True):
            values = [None if found is None else found[0]
                      for found in _over_heights(pieces, self.heights, gap, lambda piece: None)]
            return _lifted(values, _near(pieces, self.heights, gap), self.heights, gap) if lifted else values

        # Where the front faces down, outermost at that height: not upright,
        # within MIN_NORMAL_COMPONENT, nor looking up.
        facing = _over_heights(front, self.heights, 0.0, lambda piece: piece[4][1])
        self.carries = [found is not None and found[1] < -d.MIN_NORMAL_COMPONENT for found in facing]
        looks_up = [found is not None and found[1] > d.MIN_NORMAL_COMPONENT for found in facing]
        # The gap kept from every cut, recesses lower than the bridge spanned,
        # then the larger gap where the contour looks up; spanned first, the
        # step back from the larger gap to the smaller is no recess.
        # At the samples themselves, and raised where the run between two
        # would cut a corner (_lifted()).
        at_samples = envelope(self.pieces, distance, lifted=False)
        kept = _lifted(at_samples, _near(self.pieces, self.heights, distance), self.heights, distance)
        bridged = _closed(kept, width)
        far = envelope(self.pieces, apart)
        spaced = [max(value, away) if up and away is not None else value
                  for value, away, up in zip(bridged, far, looks_up)]
        inward = step / math.tan(math.radians(d.FIN_FLANK_ANGLE))
        self.flank_at = _limited(_held(spaced, bridged, self.carries), inward)
        # The gap from the middle cut alone, which the tines touch, at the
        # samples themselves: raised at a corner, as for the flank, a tine
        # beside the edge of a groove would seem to rest.
        self.touched = envelope(mitred[0], distance, lifted=False)
        self.bridged = _closed(self.touched, width)
        # Where a tine rests: the contour holds it, and the flank keeps to what
        # the middle of the fin touches there, also a layer and the gap above
        # and below: the gap kept round the edge of a hole or a groove reaches
        # past it by as much, and the end of a tine stays clear of the edge.
        touching = [carry and touched is not None and flank <= touched + d.TOLERANCE
                    for carry, flank, touched in zip(self.carries, self.flank_at, self.touched)]
        clear = d.CONTOUR_SAMPLES_PER_LAYER + int(math.ceil(distance / step))
        self.resting = [all(touching[max(0, k - clear):k + clear + 1]) for k in range(len(touching))]
        # A pocket, a groove or a hole in one face, with no tine resting in
        # it: the flank runs straight past it, from where the tines rest
        # below to where they rest again on the same face above; with the
        # bridge 0 every recess is followed.
        self.spanned = [False] * len(self.heights)
        bands = self.bands() if p.contour_bridge > 0 else []
        for (_, below), (above, _) in zip(bands, bands[1:]):
            low, high = self._index(below), self._index(above)
            if _on_one_line(self.touched, self.heights, low, high, d.CONTOUR_SAMPLES_PER_LAYER * clear):
                a, b = self.flank_at[low], self.flank_at[high]
                # Only the gap where tines rest is kept across, at the samples:
                # the faces in the pocket lie further in than the run, its
                # edges on the face, which the run keeps the gap from, so no
                # corner needs a sample raised.
                for k in range(low + 1, high):
                    gap = -math.inf if at_samples[k] is None else at_samples[k]
                    self.flank_at[k] = max(gap, a + (b - a) * (k - low) / (high - low))
                    self.spanned[k] = True
        if self.flank_at[0] == -math.inf:
            raise ContourError(translate("FinSnap", "the part does not reach the bed in the plane of the fin"))
        # The pieces near each height and the corners of the cut by height,
        # for the ends of the tines.
        self.near = _near(self.pieces, self.heights, self.clearance)
        self.corners = sorted((z, s) for piece in self.pieces for s, z in piece[:2])

    def _sample(self, values, z):
        """`values` at height z, straight between the samples around it."""
        k = min(len(self.heights) - 2, max(0, int(math.floor(z / self.step))))
        a, b = values[k], values[k + 1]
        share = min(1.0, max(0.0, (z - self.heights[k]) / self.step))
        return a + (b - a) * share

    def _index(self, z):
        return min(len(self.heights) - 1, max(0, int(round(z / self.step))))

    def flank(self, z):
        """Where the flank of the fin stands at height z."""
        return self._sample(self.flank_at, z)

    def outline(self, low, high):
        """The flank from `high` down to `low`, as (s, z) points, straight
        runs joined; z from the bed."""
        inside = [k for k, z in enumerate(self.heights) if low + d.TOLERANCE < z < high - d.TOLERANCE]
        points = [(self.flank(high), high)] + [(self.flank_at[k], self.heights[k]) for k in reversed(inside)]
        points.append((self.flank(low), low))
        return _straightened(points, d.CONTOUR_MARGIN / 2)

    def tine_ends(self, bottom, top):
        """How far out the end of a tine from `bottom` to `top` lies at each:
        on the contour, or the tine clearance off it, and no corner of the cut
        between reaching past the straight end."""
        ends = [reach(self.near[_stretch(self.heights, z)], z, self.clearance) for z in (bottom, top)]
        ends = [self.flank(z) if end is None else end for end, z in zip(ends, (bottom, top))]
        past = 0.0
        low = bisect.bisect_left(self.corners, (bottom, -math.inf))
        high = bisect.bisect_right(self.corners, (top, math.inf))
        for z, s in self.corners[low:high]:
            straight = ends[0] + (ends[1] - ends[0]) * (z - bottom) / (top - bottom)
            past = max(past, s + self.clearance - straight)
        return ends[0] + past, ends[1] + past

    def bands(self):
        """The stretches of height (mm, from the bed, lowest first) on which
        tines rest, for their grid to start anew on each, right at its lower
        edge: at the bottom of a thinner part above a step, past a bridged
        hole."""
        bands, start = [], None
        for k, rest in enumerate(self.resting + [False]):
            if rest and start is None:
                start = k
            elif not rest and start is not None:
                bands.append((self.heights[start], self.heights[k - 1]))
                start = None
        return bands

    def rests(self, bottom, top):
        """Whether a tine from `bottom` to `top` rests on the part: the
        contour faces down there, and the flank keeps its distance from it,
        neither bridged nor held off."""
        return all(self.resting[self._index(bottom):self._index(top) + 1])

    def receded(self, bottom, top):
        """Whether a tine from `bottom` to `top` that does not rest would hold
        the part, facing down, but the flank cannot follow the contour there
        without overhanging itself; not a bridged recess, an upright face or
        one looking up, which need no tine."""
        for z in (bottom, top):
            k = self._index(z)
            touched = self.touched[k]
            if self.carries[k] and touched is not None and self.bridged[k] <= touched + d.TOLERANCE \
                    and not self.resting[k] and not self.spanned[k]:
                return True
        return False

def of(part, frame, p, width):
    """The contour of `part` under the round side of `frame`, through the
    middle of the side, where its one fin stands, at most `width` thick;
    kept for the same part, plane and parameters, worked out once."""
    key = (shape_key(part), tuple(frame.out), tuple(frame.along), frame.along_min, frame.along_max, frame.bed_z,
           width, p.layer_height, p.fin_offset, p.clearance, p.contour_bridge)
    return keep(_kept, key, lambda: _worked_out(part, frame, p, width))


def _worked_out(part, frame, p, width):
    """The contour of(), cut and measured."""
    middle = (frame.along_min + frame.along_max) / 2
    beside = [middle + width * (k / (d.CONTOUR_CUTS - 1) - 0.5) for k in range(d.CONTOUR_CUTS)]
    return Contour([cut_of(part, frame, middle)] + [cut_of(part, frame, t) for t in beside
                                                    if abs(t - middle) > d.TOLERANCE], p)
