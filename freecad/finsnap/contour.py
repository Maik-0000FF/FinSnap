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
of the frame, as `s` in face_frame.Frame.

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
"""

import bisect
import math

import numpy

import Part

from . import defaults as d
from .i18n import translate
from .shapes import bounds, clear_meshes, keep, shape_key

# Places to which the ends of the pieces of a cut are compared, to join them.
JOIN_DECIMALS = 4
# Contours worked out, by part, plane and parameters (shapes.keep()): a fin
# dragged or set higher is built again and again on the same part.
_kept = {}
# The contours of fins beside the lowest line, kept apart: one build asks for
# some twenty, and fewer kept than that would never find one again.
_kept_beside = {}
BESIDE_KEPT = 256
# No reach: nothing of the pieces asked lies at a height.
NONE = -math.inf
# The pieces of a cut are asked in blocks, those reaching furthest out first,
# each block twice the size of the one before, starting with this many pairs
# of a piece and a height (_Pieces._furthest()).
FIRST_BLOCK = 256
LARGEST_BLOCK = 2 ** 16


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
    is not known to be one to run on past. The mitres let the line the gap
    away from a piece run on to where it meets that of the next, so the fin
    has a sharp corner where the part has one (_mitre())."""
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


class _Pieces:
    """The pieces of a cut (loop_pieces()) as arrays, for one `radius`: how
    far out the points within the radius of them reach, at many heights at
    once. A cut of a part with fillets has tens of thousands of pieces, and
    asked one piece and one height at a time they took most of a build.

    Within the radius of a straight piece lie a circle round either end and
    what lies between the piece and the line the radius away from it. That
    line runs on at either end by the mitre of the piece, to where it meets
    that of the next piece. It lies out of the part, where the loop of the
    piece tells which side that is; where it does not, towards larger s, the
    fin's side, for a sloping piece, and above and below, two lines, for a
    level one.

    The pieces are kept in the order of how far out any point within the
    radius of each reaches at most (`outermost`), the furthest first, pieces
    reaching as far in the order given: what the first few reach leaves most
    of the others, the back of a cut, unasked (_furthest()), and where the
    order of two pieces tells, it is this one (facing()).

    The length of a piece is taken by math.hypot and squares are written as
    products, so the values do not hang on whether numpy or Python worked
    them out: numpy's hypot differs from math.hypot in the last place for
    one pair in two hundred, Python's power from the product for one value
    in a thousand.

    INPUTS this has to withstand:
      no pieces                             ->  no height has a reach, nothing is lifted
      a piece without length                ->  its ends alone, no line
      a piece of a loop that tells its side ->  one line, out of the part
      a sloping piece of an open loop       ->  one line, towards larger s
      a level piece of an open loop         ->  two lines, above and below
      a line whose ends are as high         ->  taken from its first end to its second,
                                                as it is
      height on a sloping piece             ->  the point on its line, `radius` out along
                                                its normal
      height on a level piece               ->  its outer end, or a corner `radius` out
      height above or below every piece by
        more than `radius`                  ->  None
      radius 0                              ->  the outermost point of the cut at that
                                                height
      pieces reaching as far out at most    ->  kept in the order given
    """

    def __init__(self, pieces, radius):
        self.radius = radius
        count = len(pieces)
        flat = numpy.array([(s0, z0, s1, z1, before, after) for (s0, z0), (s1, z1), before, after, _ in pieces],
                           dtype=float).reshape(count, 6)
        s0, z0, s1, z1, before, after = flat.T
        length = numpy.array([math.hypot(run, rise) for run, rise in zip((s1 - s0).tolist(), (z1 - z0).tolist())],
                             dtype=float)
        long = length > 0
        safe = numpy.where(long, length, 1.0)
        us, uz = (s1 - s0) / safe, (z1 - z0) / safe
        told = numpy.array([piece[4] is not None for piece in pieces], dtype=bool)
        outward = numpy.array([piece[4] if piece[4] is not None else (0.0, 0.0) for piece in pieces],
                              dtype=float).reshape(count, 2)
        sloping = numpy.abs(uz) > d.TOLERANCE
        rising = uz > 0
        # The normal of the first line, and that of the second a level piece
        # of an open loop has, straight down.
        normals = ((numpy.where(told, outward[:, 0], numpy.where(sloping, numpy.where(rising, uz, -uz), 0.0)),
                    numpy.where(told, outward[:, 1], numpy.where(sloping, numpy.where(rising, -us, us), 1.0))),
                   (numpy.zeros(count), numpy.full(count, -1.0)))
        has_line = numpy.stack([long, long & ~told & ~sloping], axis=1)
        lines = numpy.zeros((count, 2, 2, 2))
        for slot, (ns, nz) in enumerate(normals):
            first = numpy.stack([s0 + (ns - us * before) * radius, z0 + (nz - uz * before) * radius], axis=1)
            second = numpy.stack([s1 + (ns + us * after) * radius, z1 + (nz + uz * after) * radius], axis=1)
            # From its lower end to its upper.
            turned = (first[:, 1] > second[:, 1])[:, None]
            lines[:, slot, 0] = numpy.where(turned, second, first)
            lines[:, slot, 1] = numpy.where(turned, first, second)
        there = numpy.repeat(has_line, 2, axis=1)
        line_s, line_z = lines[:, :, :, 0].reshape(count, 4), lines[:, :, :, 1].reshape(count, 4)
        outermost = numpy.maximum(numpy.maximum(s0, s1) + radius, numpy.where(there, line_s, NONE).max(axis=1))
        ends_z = numpy.stack([z0, z1], axis=1)
        low = numpy.minimum(ends_z.min(axis=1), numpy.where(there, line_z, math.inf).min(axis=1)) - radius
        high = numpy.maximum(ends_z.max(axis=1), numpy.where(there, line_z, NONE).max(axis=1)) + radius
        order = numpy.argsort(-outermost, kind="stable")
        self.pieces = [pieces[number] for number in order.tolist()]
        # No point within the radius of a piece reaches further out than its
        # `outermost`, or lies lower than its `low` or higher than its `high`.
        self.outermost, self.low, self.high = outermost[order], low[order], high[order]
        # The ends of each piece, (s, z), and its lines, each as its lower end and its upper.
        self.ends = numpy.stack([flat[:, 0:2], flat[:, 2:4]], axis=1)[order]
        self.lines, self.has_line = lines[order], has_line[order]

    def _between(self, numbers, low, high):
        """How far out the points within the radius of the pieces `numbers`
        reach anywhere between the heights `low` and `high`, an array each as
        long as `numbers`; NONE where none lies there. Within TOLERANCE
        counts as there: the point the part stands on lies at the bed give
        or take a rounding. A line reaches furthest at one end of where it
        runs between the heights, at either end where it lies level."""
        radius = self.radius
        found = numpy.full(len(numbers), NONE)
        ends = self.ends[numbers]
        for end in range(2):
            s, z = ends[:, end, 0], ends[:, end, 1]
            rise = numpy.minimum(numpy.maximum(z, low), high) - z
            there = numpy.abs(rise) <= radius + d.TOLERANCE
            out = s + numpy.sqrt(numpy.maximum(0.0, radius * radius - rise * rise))
            found = numpy.where(there, numpy.maximum(found, out), found)
        lines, has_line = self.lines[numbers], self.has_line[numbers]
        for slot in range(2):
            a_s, a_z = lines[:, slot, 0, 0], lines[:, slot, 0, 1]
            b_s, b_z = lines[:, slot, 1, 0], lines[:, slot, 1, 1]
            start, end = numpy.maximum(low, a_z), numpy.minimum(high, b_z)
            there = has_line[:, slot] & ~(start > end + d.TOLERANCE)
            level = b_z - a_z <= d.TOLERANCE
            rise = numpy.where(level, 1.0, b_z - a_z)
            at_start = a_s + (b_s - a_s) * (numpy.minimum(start, b_z) - a_z) / rise
            at_end = a_s + (b_s - a_s) * (numpy.maximum(end, a_z) - a_z) / rise
            out = numpy.where(level, numpy.maximum(a_s, b_s), numpy.maximum(at_start, at_end))
            found = numpy.where(there, numpy.maximum(found, out), found)
        return found

    def _past_run(self, numbers, low, high, a, b):
        """How far the points within the radius of the pieces `numbers` reach
        past the straight run from `a` at the height `low` to `b` at `high`,
        anywhere between; NONE where none lies there. A circle round an end
        of a piece reaches furthest past where its slope is that of the run,
        a line at one end of where it lies between."""
        radius = self.radius

        def run(z):
            return a + (b - a) * (z - low) / (high - low)

        slope = (run(high) - run(low)) / (high - low)
        found = numpy.full(len(numbers), NONE)
        ends = self.ends[numbers]
        for end in range(2):
            s, middle = ends[:, end, 0], ends[:, end, 1]
            start, stop = numpy.maximum(low, middle - radius), numpy.minimum(high, middle + radius)
            there = ~(start > stop)
            tangent = middle - slope * radius / numpy.sqrt(1 + slope * slope)
            for z in (start, stop, numpy.minimum(numpy.maximum(tangent, start), stop)):
                rise = z - middle
                out = s + numpy.sqrt(numpy.maximum(0.0, radius * radius - rise * rise)) - run(z)
                found = numpy.where(there, numpy.maximum(found, out), found)
        lines, has_line = self.lines[numbers], self.has_line[numbers]
        for slot in range(2):
            a_s, a_z = lines[:, slot, 0, 0], lines[:, slot, 0, 1]
            b_s, b_z = lines[:, slot, 1, 0], lines[:, slot, 1, 1]
            start, stop = numpy.maximum(low, a_z), numpy.minimum(high, b_z)
            level = b_z - a_z <= d.TOLERANCE
            flat = numpy.maximum(a_s, b_s) - run(numpy.minimum(numpy.maximum(a_z, low), high))
            lying = has_line[:, slot] & level & (start <= stop + d.TOLERANCE)
            found = numpy.where(lying, numpy.maximum(found, flat), found)
            rise = numpy.where(level, 1.0, b_z - a_z)
            sloping = has_line[:, slot] & ~level & (start <= stop)
            for z in (start, stop):
                out = a_s + (b_s - a_s) * (z - a_z) / rise - run(z)
                found = numpy.where(sloping, numpy.maximum(found, out), found)
        return found

    def stretches(self, heights):
        """The first and the last stretch between two of the evenly spaced
        `heights` each piece reaches into within the radius, an array each;
        the last before the first for a piece reaching into none."""
        first, step = heights[0], heights[1] - heights[0]
        return (numpy.maximum(0, numpy.floor((self.low - first) / step)).astype(int),
                numpy.minimum(len(heights) - 2, numpy.floor((self.high - first) / step)).astype(int))

    def _samples(self, heights):
        """The first and the last of the evenly spaced `heights` each piece
        is asked at, an array each: within TOLERANCE of a step past what it
        reaches, which is not the tolerance _between() allows in mm, so a
        height just outside is not asked though a point may lie there."""
        first, step = heights[0], heights[1] - heights[0]
        return (numpy.maximum(0, numpy.ceil((self.low - first) / step - d.TOLERANCE)).astype(int),
                numpy.minimum(len(heights) - 1, numpy.floor((self.high - first) / step + d.TOLERANCE)).astype(int))

    def _blocks(self, start, end):
        """Every piece with every place from its `start` to its `end`, in
        blocks: for each, the numbers of its pieces and the places, an array
        each, in the order of the pieces. A block is twice the size of the
        one before, up to LARGEST_BLOCK, counted in pairs of a piece and a
        place: a cut of tens of thousands of pieces has millions of pairs,
        which are never all held at once. A piece is not split between two
        blocks."""
        lengths = numpy.maximum(0, end - start + 1)
        upto = numpy.cumsum(lengths)
        piece, done, size = 0, 0, FIRST_BLOCK
        while piece < len(lengths):
            stop = max(piece + 1, int(numpy.searchsorted(upto, done + size, side="right")))
            ours = lengths[piece:stop]
            numbers = numpy.repeat(numpy.arange(piece, stop), ours)
            # Counting up from the start of each piece.
            steps = numpy.arange(ours.sum()) - numpy.repeat(numpy.cumsum(ours) - ours, ours)
            yield numbers, start[numbers] + steps
            piece, done, size = stop, int(upto[stop - 1]), min(2 * size, LARGEST_BLOCK)

    def _furthest(self, ranges, low, high):
        """The furthest out the pieces reach between `low` and `high`, the
        heights of each place, an array each, at each of those places; NONE
        where none reaches. `ranges` are the first and the last place of
        each piece. A piece that cannot reach as far as is found at a place
        by the blocks before its own, the tolerance aside, is not asked
        there, and would add nothing if it were."""
        found = numpy.full(len(low), NONE)
        for numbers, places in self._blocks(*ranges):
            asked = self.outermost[numbers] >= found[places] - d.TOLERANCE
            numbers, places = numbers[asked], places[asked]
            numpy.maximum.at(found, places, self._between(numbers, low[places], high[places]))
        return found

    def reaches(self, heights):
        """How far out the pieces reach within the radius at every one of the
        evenly spaced `heights`; None where none does."""
        z = numpy.asarray(heights, dtype=float)
        return [None if value == NONE else value for value in self._furthest(self._samples(heights), z, z).tolist()]

    def reach(self, near, stretch, z):
        """How far out the pieces reaching into the stretch `stretch` of
        heights (`near` from stretches()) reach within the radius at height
        z; None where none does."""
        start, end = near
        numbers = numpy.flatnonzero((start <= stretch) & (stretch <= end))
        if not len(numbers):
            return None
        height = numpy.full(len(numbers), float(z))
        found = self._between(numbers, height, height).max()
        return None if found == NONE else float(found)

    def facing(self, heights, measure):
        """At every one of the evenly spaced `heights`, how far out the
        pieces reach within the radius, with `measure`(piece), a number, of
        the piece reaching furthest: (reach, value), or None where none
        reaches. Of pieces reaching as far, within TOLERANCE, as two do
        where they meet, the smallest value is kept.

        The pieces reaching a height count in their order, as taken one after
        the other: which value stays hangs on it. They are not gone through
        one by one, nor laid out in a table of heights by pieces, which a
        level underside in thousands of short pieces would make a thousand
        times too large: what each piece does follows from the furthest the
        pieces before it reach, worked out for all at once.

        INPUTS this has to withstand:
          one piece at a height                 ->  its reach and its value
          a piece reaching further than those
            before it by more than TOLERANCE    ->  takes over, with its value alone
          a piece within TOLERANCE of the
            furthest so far                     ->  the further reach of the two, the smaller
                                                    value
          a piece more than TOLERANCE short of
            the furthest so far                 ->  nothing of it kept
          three pieces, each within TOLERANCE
            of the next and the last more than
            that past the first                 ->  from the furthest down, the first is
                                                    left out; from the nearest up, the last
                                                    takes over: as the order has it
          thousands of pieces at one height, as
            a level underside of a part from a
            mesh has                            ->  as taken one after the other, in no more
                                                    time or room than their number asks
          no piece at a height                  ->  None
        """
        count = len(heights)
        z = numpy.asarray(heights, dtype=float)
        blocks = list(self._blocks(*self._samples(heights)))
        if not blocks:
            return [None] * count
        numbers, places = (numpy.concatenate(each) for each in zip(*blocks))
        reach = self._between(numbers, z[places], z[places])
        there = reach != NONE
        numbers, places, reach = numbers[there], places[there], reach[there]
        if not len(numbers):
            return [None] * count
        # By height, the pieces of each still in their order: a group for
        # every height a piece reaches.
        order = numpy.argsort(places, kind="stable")
        numbers, places, reach = numbers[order], places[order], reach[order]
        values = numpy.array([measure(piece) for piece in self.pieces], dtype=float)[numbers]
        first = numpy.r_[True, places[1:] != places[:-1]]
        starts = numpy.flatnonzero(first)
        sizes = numpy.diff(numpy.r_[starts, len(places)])
        group = numpy.repeat(numpy.arange(len(starts)), sizes)
        # The furthest any piece of its height up to each one reaches: taken
        # from the one a step before, then two, then four, as far as a group is
        # long, which gives what going through them one by one would.
        furthest = reach.copy()
        step = 1
        while step < sizes.max():
            same = group[step:] == group[:-step]
            furthest[step:] = numpy.where(same, numpy.maximum(furthest[step:], furthest[:-step]), furthest[step:])
            step *= 2
        # What the pieces before each one reach, and so what each does: takes
        # over, adds its value to those kept, or is left out.
        before = numpy.r_[NONE, furthest[:-1]]
        takes = first | (reach > before + d.TOLERANCE)
        adds = takes | (reach >= before - d.TOLERANCE)
        # The values kept are those from the last piece that took over on.
        turn = numpy.arange(len(places))
        last = numpy.maximum.reduceat(numpy.where(takes, turn, -1), starts)
        kept = numpy.minimum.reduceat(numpy.where(adds & (turn >= last[group]), values, math.inf), starts)
        best = numpy.maximum.reduceat(reach, starts)
        found = [None] * count
        for place, r, value in zip(places[starts].tolist(), best.tolist(), kept.tolist()):
            found[place] = (r, value)
        return found

    def lifted(self, values, heights):
        """`values`, the reach of the pieces within the radius at `heights`
        (reaches()), lifted where the straight run between two samples would
        come closer to the part than its share of CONTOUR_TOLERANCE allows
        (CONTOUR_SHARE), a corner or the start of a circle between them: both
        raised to the most the part reaches between them, the run then
        outside it. On a smooth contour nothing is raised.

        INPUTS this has to withstand:
          a smooth contour                      ->  nothing raised
          a corner between two samples, past
            the run between them by more than
            the share                           ->  both raised to the most the pieces
                                                    reach between them
          the same by the share or less         ->  nothing raised
          a piece staying inside both samples
            by more than the share              ->  not asked: it cannot reach past the run
          a sample without a reach, where the
            contour starts or ends              ->  the most the pieces reach in the stretch
                                                    below it, or else in the one above
          a stretch nothing reaches into        ->  its samples as they are
        """
        stretches = len(heights) - 1
        z = numpy.asarray(heights, dtype=float)
        ranges = self.stretches(heights)
        low, high = z[:-1], z[1:]
        most = self._furthest(ranges, low, high)
        given = numpy.array([NONE if value is None else value for value in values], dtype=float)
        missing = numpy.array([value is None for value in values], dtype=bool)
        open_end = missing[:-1] | missing[1:]
        a, b = given[:-1], given[1:]
        lowest = numpy.minimum(a, b)
        cut = numpy.zeros(stretches, dtype=bool)
        for numbers, places in self._blocks(*ranges):
            asked = ~open_end[places] & (self.outermost[numbers] - lowest[places] > d.CONTOUR_SHARE)
            numbers, places = numbers[asked], places[asked]
            past = self._past_run(numbers, low[places], high[places], a[places], b[places])
            cut[places[past > d.CONTOUR_SHARE]] = True
        up = numpy.where(cut, most, NONE)
        raised = numpy.full(len(values), NONE)
        raised[:-1] = numpy.maximum(raised[:-1], up)
        raised[1:] = numpy.maximum(raised[1:], up)
        fills = (open_end & (most != NONE)).tolist()
        most, raised = most.tolist(), raised.tolist()
        result = []
        for k, value in enumerate(values):
            if value is None:
                if k > 0 and fills[k - 1]:
                    value = most[k - 1]
                elif k < stretches and fills[k]:
                    value = most[k]
            result.append(value if value is None else max(value, raised[k]))
        return result


def _stretch(heights, z):
    """The number of the stretch between two of the evenly spaced `heights`
    that holds z."""
    first, step = heights[0], heights[1] - heights[0]
    return min(len(heights) - 2, max(0, int(math.floor((z - first) / step))))


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
    if start == below or None in (values[start], values[below], values[above]):
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


class _TineEnds:
    """Where the ends of tines lie along cuts of the part: what a Contour and
    CutEnds have in common. Holds `heights`, `clear`, the pieces of the cuts
    with the tine clearance round them (_Pieces), `near`, the stretches of
    heights each of them reaches into (_Pieces.stretches()), the `corners`
    of the cuts and the `clearance`; flank() stands in where nothing of the
    cut lies near."""

    def _keep_clear(self, pieces, clearance):
        """Take `pieces`, those of the cuts, for the ends of tines `clearance` off them."""
        self.clearance = clearance
        self.clear = _Pieces(pieces, clearance)
        self.near = self.clear.stretches(self.heights)
        self.corners = sorted((z, s) for piece in pieces for s, z in piece[:2])

    def tine_ends(self, bottom, top):
        """How far out the end of a tine from `bottom` to `top` lies at each:
        on the contour, or the tine clearance off it, and no corner of the cut
        between reaching past the straight end."""
        ends = [self.clear.reach(self.near, _stretch(self.heights, z), z) for z in (bottom, top)]
        ends = [self.flank(z) if end is None else end for end, z in zip(ends, (bottom, top))]
        past = 0.0
        low = bisect.bisect_left(self.corners, (bottom, -math.inf))
        high = bisect.bisect_right(self.corners, (top, math.inf))
        for z, s in self.corners[low:high]:
            straight = ends[0] + (ends[1] - ends[0]) * (z - bottom) / (top - bottom)
            past = max(past, s + self.clearance - straight)
        return ends[0] + past, ends[1] + past


class CutEnds(_TineEnds):
    """The ends of tines along one cut, and nothing else: a Contour works out a
    flank at every height as well, which a tine does not need and which takes
    many times as long on a tall part. Where the cut has nothing at a height,
    `beside`, the Contour of its fin, says where its flank stands."""

    def __init__(self, lines, p, beside):
        pieces = [piece for loop in loops_of(lines) for piece in loop_pieces(loop)]
        self.beside = beside
        top = max(max(start[1], end[1]) for start, end, *_ in pieces)
        self.step = p.layer_height / d.CONTOUR_SAMPLES_PER_LAYER
        self.heights = [k * self.step for k in range(int(math.ceil(top / self.step)) + 1)]
        self._keep_clear(pieces, p.clearance)

    def flank(self, z):
        return self.beside.flank(z)


class Contour(_TineEnds):
    """The flank of the fin under a round side along the contour of the part,
    the heights its tines rest on and how far they reach; see the module."""

    def __init__(self, cuts, p, above_bed=False, side_from=None):
        """`cuts`, the lines of each cut across the thickness of the fin, the
        middle one first: that one, where the tines stand, gives the contour;
        the gap is kept from all of them, as a hole narrower than the fin
        leaves the cuts beside the middle whole. With `above_bed` the cuts may
        start above the bed, as a line beside the lowest one does. `side_from` is
        (height, slope) where the round side starts above what the part stands
        on, a fillet or a chamfer, and how far out its flank goes per mm up:
        below it the fin goes on in that line, down to its foot, with no tines,
        as far off as the part asks, not along what the part stands on."""
        mitred = [[piece for loop in loops_of(lines) for piece in loop_pieces(loop)] for lines in cuts]
        self.pieces = [piece for pieces in mitred for piece in pieces]
        front = front_of(loops_of(cuts[0]))
        self.top = max(max(start[1], end[1]) for start, end, *_ in front)
        step = p.layer_height / d.CONTOUR_SAMPLES_PER_LAYER
        self.step = step
        self.heights = [k * step for k in range(int(math.ceil(self.top / step)) + 1)]
        distance = p.gap
        # Over a face looking up the fin keeps the larger gap, so it cannot
        # stick to the part there; never less than where the tines rest.
        apart = max(p.contour_gap, p.gap)
        width = int(round(p.contour_bridge / step))

        def envelope(pieces, gap):
            around = _Pieces(pieces, gap)
            return around.lifted(around.reaches(self.heights), self.heights)

        # Where the front faces down, outermost at that height: not upright,
        # within MIN_NORMAL_COMPONENT, nor looking up.
        facing = _Pieces(front, 0.0).facing(self.heights, lambda piece: piece[4][1])
        self.carries = [found is not None and found[1] < -d.MIN_NORMAL_COMPONENT for found in facing]
        looks_up = [found is not None and found[1] > d.MIN_NORMAL_COMPONENT for found in facing]
        # The gap kept from every cut, recesses lower than the bridge spanned,
        # then the larger gap where the contour looks up; spanned first, the
        # step back from the larger gap to the smaller is no recess.
        # At the samples themselves, and raised where the run between two
        # would cut a corner (_Pieces.lifted()).
        around = _Pieces(self.pieces, distance)
        at_samples = around.reaches(self.heights)
        kept = around.lifted(at_samples, self.heights)
        bridged = _closed(kept, width)
        # Worked out only where the contour looks up at all: most cuts of a
        # side beside the lowest line do so nowhere it matters, and this is
        # as much work again.
        far = envelope(self.pieces, apart) if any(looks_up) and apart != distance else bridged
        spaced = [max(value, away) if up and away is not None else value
                  for value, away, up in zip(bridged, far, looks_up)]
        inward = step / math.tan(math.radians(d.FIN_FLANK_ANGLE))
        self.flank_at = _limited(_held(spaced, bridged, self.carries), inward)
        # The gap from the middle cut alone, which the tines touch, at the
        # samples themselves: raised at a corner, as for the flank, a tine
        # beside the edge of a groove would seem to rest.
        self.touched = at_samples if len(mitred) == 1 else _Pieces(mitred[0], distance).reaches(self.heights)
        self.bridged = _closed(self.touched, width)
        # Where a tine rests: the contour holds it, and the flank keeps to what
        # the middle of the fin touches there, also a layer and the gap above
        # and below: the gap kept round the edge of a hole or a groove reaches
        # past it by as much, and the end of a tine stays clear of the edge.
        touching = [carry and touched is not None and flank <= touched + d.TOLERANCE
                    for carry, flank, touched in zip(self.carries, self.flank_at, self.touched)]
        clear = d.CONTOUR_SAMPLES_PER_LAYER + int(math.ceil(distance / step))
        self.resting = [all(touching[max(0, k - clear):k + clear + 1]) for k in range(len(touching))]
        # Only over what the part stands on: above a groove or a thicker part, the
        # contour looks up on the way, and the fin follows it as anywhere; a
        # thinner part below, where tines rest CONTOUR_OWN_PART and more,
        # carries tines of its own, and the fin follows it too.
        start = None if side_from is None else self._index(side_from[0])
        if start is not None and not any(looks_up[:start]) and not self._carries_tines(start):
            for k in range(start):
                self.flank_at[k] = max(self.flank_at[k],
                                       self.flank_at[start] - (self.heights[start] - self.heights[k]) * side_from[1])
                self.resting[k] = False
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
            start = next((k for k, value in enumerate(self.flank_at) if value != -math.inf), None)
            if not above_bed or start is None:
                raise ContourError(translate("FinSnap", "the part does not reach the bed in the plane of the fin"))
            # Nothing of the part lies in the plane below: the flank goes straight down.
            self.flank_at[:start] = [self.flank_at[start]] * start
        # The pieces near each height and the corners of the cuts by height,
        # for the ends of the tines.
        self._keep_clear(self.pieces, p.clearance)

    def _sample(self, values, z):
        """`values` at height z, straight between the samples around it."""
        k = min(len(self.heights) - 2, max(0, int(math.floor(z / self.step))))
        a, b = values[k], values[k + 1]
        share = min(1.0, max(0.0, (z - self.heights[k]) / self.step))
        return a + (b - a) * share

    def _index(self, z):
        return min(len(self.heights) - 1, max(0, int(round(z / self.step))))

    def _carries_tines(self, below):
        """Whether tines rest on a stretch at least CONTOUR_OWN_PART high
        anywhere below the sample `below`: a part of its own, not a chamfer or
        a fillet round the rim.

        INPUTS this has to withstand:
          chamfer or fillet round the rim     ->  False: no stretch that long rests
          thinner rod or step below the side  ->  True
          nothing rests below                 ->  False
          `below` at the bed                  ->  False
        """
        # A run of n resting samples spans n - 1 steps.
        run = 0
        for rest in self.resting[:below]:
            run = run + 1 if rest else 0
            if (run - 1) * self.step >= d.CONTOUR_OWN_PART - d.TOLERANCE:
                return True
        return False

    def flank(self, z):
        """Where the flank of the fin stands at height z."""
        return self._sample(self.flank_at, z)

    def outline(self, low, high):
        """The flank from `high` down to `low`, as (s, z) points, straight
        runs joined; z from the bed."""
        inside = [k for k, z in enumerate(self.heights) if low + d.TOLERANCE < z < high - d.TOLERANCE]
        points = [(self.flank(high), high)] + [(self.flank_at[k], self.heights[k]) for k in reversed(inside)]
        points.append((self.flank(low), low))
        return _straightened(points, d.CONTOUR_SHARE)

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


def clear_kept():
    """Forget every contour kept, as if none had been worked out."""
    _kept.clear()
    _kept_beside.clear()
    clear_meshes()


def side_from(frame, away=0.0):
    """Where the round side of `frame` starts above the bed, in the upright plane
    `away` along the face from its lowest line, and how far out a flank along
    it goes per mm up, for Contour; None where it starts on the bed."""
    start = frame.face_bottom_z - frame.bed_z
    if start <= d.TOLERANCE:
        return None
    # Further round, the same place along the axis lies higher up.
    rise = (frame.radius - math.sqrt(max(0.0, frame.radius ** 2 - away ** 2))) * -frame.n_z
    return start + rise, -frame.n_z / frame.n_out


def of(part, frame, p, width):
    """The contour of `part` under the round side of `frame`, through the
    middle of the side, where its one fin stands, at most `width` thick;
    kept for the same part, plane and parameters, worked out once."""
    key = (shape_key(part), tuple(frame.out), tuple(frame.along), frame.along_min, frame.along_max, frame.bed_z,
           frame.face_bottom_z, frame.radius, width, p.layer_height, p.gap, p.clearance, p.contour_bridge,
           p.contour_gap)
    return keep(_kept, key, lambda: _worked_out(part, frame, p, width))


def _worked_out(part, frame, p, width):
    """The contour of(), cut and measured."""
    middle = (frame.along_min + frame.along_max) / 2
    beside = [middle + width * (k / (d.CONTOUR_CUTS - 1) - 0.5) for k in range(d.CONTOUR_CUTS)]
    return Contour([cut_of(part, frame, middle)] + [cut_of(part, frame, t) for t in beside
                                                    if abs(t - middle) > d.TOLERANCE], p, side_from=side_from(frame))


def beside(part, frame, p, nearest, furthest):
    """The contour of a fin parallel to the one under the lowest line of the
    round side of `frame`, as thick as from `nearest`, its edge nearest that
    line, to `furthest` along the face: the first cut, which it rests on, is
    the one at `nearest`, where the side reaches furthest out; kept as of() is."""
    key = (shape_key(part), tuple(frame.out), tuple(frame.along), frame.bed_z, frame.face_bottom_z, frame.radius,
           nearest, furthest, p.layer_height, p.gap, p.clearance, p.contour_bridge, p.contour_gap)

    def worked_out():
        planes = [nearest + (furthest - nearest) * k / (d.CONTOUR_CUTS - 1) for k in range(d.CONTOUR_CUTS)]
        away = nearest - (frame.along_min + frame.along_max) / 2
        return Contour([cut_of(part, frame, t) for t in planes], p, above_bed=True, side_from=side_from(frame, away))
    return keep(_kept_beside, key, worked_out, BESIDE_KEPT)


def ends_at(part, frame, p, t, beside_line):
    """Where tines end in the upright plane at `t` along the face of `frame`
    (CutEnds), for one beside the lowest line; kept as of() is."""
    key = (shape_key(part), tuple(frame.out), tuple(frame.along), frame.bed_z, t,
           p.layer_height, p.clearance)
    return keep(_kept_beside, key, lambda: CutEnds(cut_of(part, frame, t), p, beside_line), BESIDE_KEPT)


def across(part, frame, p, t):
    """The contour in the one upright plane at `t` along the face of `frame`,
    for what a tine beside the lowest line rests on; kept as of() is."""
    key = (shape_key(part), tuple(frame.out), tuple(frame.along), frame.bed_z, frame.face_bottom_z, frame.radius, t,
           p.layer_height, p.gap, p.clearance, p.contour_bridge, p.contour_gap)
    away = t - (frame.along_min + frame.along_max) / 2
    return keep(_kept_beside, key,
                lambda: Contour([cut_of(part, frame, t)], p, above_bed=True, side_from=side_from(frame, away)),
                BESIDE_KEPT)
