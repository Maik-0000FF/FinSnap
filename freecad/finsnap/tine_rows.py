# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""The tines of a fin: their heights on the layer grid, where they reach the
face, how much of it they touch, and where their ends land (face_frame.py).
"""

import math

import FreeCAD as App
import Part

from . import defaults as d
from .face_frame import FinError
from .i18n import QT_TRANSLATE_NOOP, translate

# How near a cut a corner of a face may lie for the cut still to be worked out
# from its corners (_cut_corners()): nearer, the kernel cuts, as only it knows
# what a cut through a corner or along an edge gives (mm). Far wider than what
# the kernel takes for the same point.
CORNER_NEAR_CUT = d.TOLERANCE
# The face asked last and its corners (_outline_of()): told once, as every place
# and height tried in a build asks of the same face.
_outlined = []

# Said where the face is narrower than a fin, or its tine, at every tine height.
NARROW_AT_EVERY_TINE = QT_TRANSLATE_NOOP("FinSnap", "the face is narrower than the %.2f mm a fin needs at every tine")


def tine_heights(p, frame, tine_count):
    """Bottoms of the tines above the bed, on the layer grid, and the fin height."""
    room = frame.room
    limit = p.fin_height if p.fin_height > 0 else room
    if limit > room:
        raise FinError(translate("FinSnap", "fin_height %.2f reaches above the face (%.2f)") % (limit, room))

    # A face that ends above the bed gets no tines below it.
    floor = frame.face_bottom_z - frame.bed_z
    if floor > d.TOLERANCE:
        floor += d.FACE_BOTTOM_MARGIN
    zs = []
    k = 0
    while tine_count == 0 or len(zs) < tine_count:
        z = p.snap_to_layer(p.first_tine + k * p.tine_spacing)
        k += 1
        # Rounding to the layer grid can bring a tine closer to the one below
        # than the spacing allows (a hand-set first tine half a layer off the
        # grid); it moves up to keep a free layer between them.
        if zs and z < zs[-1] + p.least_tine_spacing - d.TOLERANCE:
            z = p.snap_to_layer(zs[-1] + p.least_tine_spacing)
        if z + p.tine_height > limit + d.TOLERANCE:
            break
        if z >= floor - d.TOLERANCE:
            zs.append(z)
    if not zs:
        raise FinError(translate("FinSnap", "no tine fits below %.2f mm") % limit)
    if tine_count and len(zs) < tine_count:
        raise FinError(translate("FinSnap", "only %d of %d tines fit below %.2f mm") % (len(zs), tine_count, limit))
    height = p.fin_height if p.fin_height > 0 else zs[-1] + p.tine_height
    return zs, height


def _straight_outline(face):
    """The corners of `face`, its outer wire first, then its holes, each a list of
    points in their order round it; None unless it is one planar face whose edges
    are all straight lines, which is what _cut_corners() can cut.

    INPUTS this has to withstand:
      one planar face, every edge a line     ->  its corners, the outer wire first
      a hole of straight edges               ->  a list of its own after the outer one
      an edge that is round                  ->  None
      a straight edge the kernel holds as a
        spline, as a STEP file brings them   ->  None: not looked into, it is not a line
      a face that is not planar              ->  None
      several faces, or none                 ->  None: the kernel joins what they share
    """
    faces = face.Faces
    if len(faces) != 1 or not isinstance(faces[0].Surface, Part.Plane):
        return None
    outer = faces[0].OuterWire
    rings = []
    for wire in [outer] + [wire for wire in faces[0].Wires if not wire.isSame(outer)]:
        if not all(isinstance(edge.Curve, Part.Line) for edge in wire.Edges):
            return None
        rings.append([vertex.Point for vertex in wire.OrderedVertexes])
    return rings


def _outline_of(face):
    """_straight_outline() of `face`, told once for the face asked last."""
    if not _outlined or not _outlined[0][0].isSame(face):
        _outlined[:] = [(face, _straight_outline(face))]
    return _outlined[0][1]


def _cut_corners(rings, at, value):
    """Where the plane on which at(point) is `value` crosses the edges between
    the corners of `rings`, as points; None where a corner lies within
    CORNER_NEAR_CUT of it, which is left to the kernel. Worked out, they are
    the points the kernel finds within what it takes for one point, about
    1e-7 mm: what is made of them is compared with d.TOLERANCE, a thousand
    times that.

    INPUTS this has to withstand:
      the plane across two edges            ->  the two points
      across a face that turns in, as an L
        or a U, or through a hole           ->  four points, or more
      past the face                         ->  none
      a corner in the plane, or an edge
        along it, within CORNER_NEAR_CUT    ->  None
    """
    found = []
    for ring in rings:
        sides = [at(point) - value for point in ring]
        if any(abs(side) <= CORNER_NEAR_CUT for side in sides):
            return None
        for a, b, side_a, side_b in zip(ring, ring[1:] + ring[:1], sides, sides[1:] + sides[:1]):
            if (side_a < 0) != (side_b < 0):
                found.append(a + (b - a) * (side_a / (side_a - side_b)))
    return found


def _span_at(face, frame, height):
    """(first, last) position along the face where the level plane at
    `height` crosses the outer edges of `face`, None if it misses. Holes
    inside the face lie within, so only its outer wires are cut: much faster
    than slicing the face itself, with the same outermost points. Worked out
    from the corners of a face _straight_outline() knows, cut by the kernel
    otherwise (_span_cut()).

    INPUTS this has to withstand:
      one planar face of straight edges     ->  worked out, no cut
      a hole in it                          ->  passed over: the outer wire alone
      the height past the face              ->  None
      a corner at the height, an edge along
        it, a round edge, a face not planar,
        several faces                       ->  cut by the kernel, as before
    """
    rings = _outline_of(face)
    points = None if rings is None else _cut_corners(rings[:1], lambda point: point.z, height)
    if points is None:
        return _span_cut(face, frame, height)
    ts = [point.dot(frame.along) for point in points]
    return (min(ts), max(ts)) if ts else None


def _span_cut(face, frame, height):
    """_span_at() by a cut of the kernel."""
    box = face.BoundBox
    # A plane larger than the face, about its middle.
    size = 2 * box.DiagonalLength
    plane = Part.makePlane(size, size, App.Vector(box.Center.x - size / 2, box.Center.y - size / 2, height))
    ts = [v.Point.dot(frame.along) for one in face.Faces for v in one.OuterWire.section(plane).Vertexes]
    return (min(ts), max(ts)) if ts else None


def extent_at(face, frame, z, p, slices=None):
    """(first, last) position along the face over the height of a tine at z,
    None if it misses. Holes inside the face are passed over: the outermost
    points at each height count, and whether a tine rests over a hole is for
    contact_share(). `slices`, a dict kept for one build, holds the span of
    the face at each height cut, so a height is cut once, whichever fin or
    plan asks for it."""
    low, high = frame.along_min, frame.along_max
    # The lowest line of a round side runs from face_bottom_z to face_top_z,
    # which bound the tines already; a hole across it is found by contact_share().
    if frame.round_side:
        return low, high
    slices = {} if slices is None else slices
    for height in (frame.bed_z + z, frame.bed_z + z + p.tine_height):
        if height not in slices:
            slices[height] = _span_at(face, frame, height)
        if slices[height] is None:
            return None
        low, high = max(low, slices[height][0]), min(high, slices[height][1])
    return low, high


def _fin_reach(p, t0, thickness):
    """The stretch along the face that has to lie on it for the fin starting
    at t0: under the whole fin, or for a fin on a corner, which reaches past
    the end of the face, under its tine."""
    if p.on_corner:
        first = tine_start(p, t0, thickness)
        return first, first + p.tine_width
    return t0, t0 + thickness


def wide_enough(extent, p, t0, thickness):
    """Whether the face, reaching over `extent` along it at the height of a
    tine (extent_at(), None where it misses), is wide enough there for the
    fin starting at t0: it reaches under the whole fin, or for a fin on a
    corner, which reaches past the end of the face, under its tine. The rule
    tines_on_face() keeps for the tines of the face as a whole, for a fin on
    its own tine grid, whose tines lie at other heights.

    INPUTS this has to withstand:
      the face wider than the fin there     ->  True
      a notch in the end of the face under
        the fin                             ->  False
      a hole inside the face under the fin  ->  True: its outermost points count
      no face at that height (None)         ->  False
      a fin on a corner, past the end       ->  True while the face reaches under its tine
      a face as wide as the fin             ->  True, within the tolerance
    """
    if extent is None:
        return False
    first, last = _fin_reach(p, t0, thickness)
    return extent[0] <= first + d.TOLERANCE and last <= extent[1] + d.TOLERANCE


def tines_on_face(face, frame, tine_z, p, width, slices=None):
    """The longest run of consecutive tines that all meet the face over at
    least `width`, and the stretch along the face they share.

    A face that narrows, like the side of a frustum standing on a corner, is
    narrower at some tines than a fin is thick; those tines are left out. A
    height where no face lies at all, the gap between two faces in one plane,
    only leaves its own tine out; the run goes on above it.
    `slices` is the dict of extent_at() kept for the build.
    Returns (tine heights, first, last, heights over a gap); raises if no tine
    has room.
    """
    extents = [extent_at(face, frame, z, p, slices) for z in tine_z]
    gaps = [z for z, extent in zip(tine_z, extents) if extent is None]
    best = None
    for start in range(len(tine_z)):
        if extents[start] is None:
            continue
        low, high = frame.along_min, frame.along_max
        for end in range(start, len(tine_z)):
            if extents[end] is None:
                continue
            low, high = max(low, extents[end][0]), min(high, extents[end][1])
            if high - low < width - d.TOLERANCE:
                break
            run = [z for z, extent in zip(tine_z[start:end + 1], extents[start:end + 1]) if extent]
            if best is None or len(run) > len(best[0]):
                best = (run, low, high)
    if best is None:
        raise FinError(translate("FinSnap", NARROW_AT_EVERY_TINE) % width)
    return (*best, gaps)


def fin_stretch(face, frame, p, width, count, low, high, slices=None):
    """The stretch along the face the fins are placed on, with the restart,
    `low` to `high` being what the tines of the face as a whole share. A face
    that starts above the bed and is narrow there, as the end of a disc or a
    slot, has them spread from that narrow edge, and sharing it would crowd
    the fins together or leave some out. Each fin gets tines of its own where
    it stands, so it needs no tine of that edge: the stretch of the one grid
    is taken where that is longer.

    INPUTS this has to withstand:
      a face from the bed up                ->  the same heights, so the same stretch
      above the bed, the grid stretch longer->  the stretch of the grid
      above the bed, the grid stretch shorter
                                            ->  `low` to `high`
      no grid tine on the face, or none
        with room                           ->  `low` to `high`
    """
    try:
        _, grid_low, grid_high, _ = tines_on_face(face, frame, tine_heights(p, frame, count)[0], p, width, slices)
    except FinError:
        return low, high
    return (grid_low, grid_high) if grid_high - grid_low > high - low else (low, high)


def tine_start(p, t0, thickness):
    """Where the tines of the fin starting at t0 begin along the face: in the middle of the fin."""
    return t0 + (thickness - p.tine_width) / 2


def _snap_down(p, z):
    """The last layer boundary at or below z (mm, from the bed), the first layer at least."""
    snapped = p.snap_to_layer(z)
    return snapped if snapped <= z + d.TOLERANCE else p.snap_to_layer(snapped - p.layer_height)


def _snap_up(p, z):
    """The first layer boundary at or above z (mm, from the bed)."""
    snapped = p.snap_to_layer(z)
    return snapped if snapped >= z - d.TOLERANCE else p.snap_to_layer(snapped + p.layer_height)


def _bands_at(frame, face, t):
    """The stretches of height (mm, from the bed) where `face` lies across
    the vertical plane at `t` along it, lowest first: a hole, a groove or a
    bore across that plane splits them. Worked out from the corners of a face
    _straight_outline() knows, cut by the kernel otherwise (_bands_cut()).

    INPUTS this has to withstand:
      one planar face of straight edges     ->  worked out: one stretch
      a hole of straight edges across the
        plane, or a face turning in there,
        as an L or a U                      ->  worked out: a stretch below and one above
      the plane past the face               ->  none
      a stretch ending on a layer boundary  ->  the same tines as by the cut: what is
                                                made of it is compared with d.TOLERANCE
      a corner in the plane, an edge along
        it, a round edge, a face not planar,
        several faces                       ->  cut by the kernel, as before
      a face lying level, two crossings at
        one height, or an odd number of
        them                                ->  cut by the kernel: no order to pair them by
    """
    rings = _outline_of(face)
    points = None if rings is None else _cut_corners(rings, lambda point: point.dot(frame.along), t)
    if points is None or len(points) % 2:
        return _bands_cut(frame, face, t)
    # Along the cut the face is entered and left in turn, from the lowest up.
    heights = sorted(point.z - frame.bed_z for point in points)
    if any(high - low <= CORNER_NEAR_CUT for low, high in zip(heights, heights[1:])):
        return _bands_cut(frame, face, t)
    return list(zip(heights[::2], heights[1::2]))


def _bands_cut(frame, face, t):
    """_bands_at() by a cut of the kernel."""
    bands = []
    for wire in face.slice(frame.along, t):
        box = wire.BoundBox
        bands.append((box.ZMin - frame.bed_z, box.ZMax - frame.bed_z))
    return sorted(bands)


def _spread(p, bands, limit, count):
    """Bottoms of tines over the stretches of height `bands` (mm, from the
    bed, lowest first): in each spread evenly from its lower edge to its top,
    no further apart than the tine spacing, at least one free layer between
    two of them. None above `limit`, `count` at most if given."""
    zs = []
    for bottom, top in bands:
        # A stretch is where the whole end of a tine lies on the face, so the
        # lowest tine goes on the first layer from its lower edge up, right
        # above a fillet or a gap below; the margin below the top of the face
        # is kept, as the one grid keeps it.
        first = _snap_up(p, max(bottom, p.first_tine))
        if zs:
            first = max(first, _snap_up(p, zs[-1] + p.least_tine_spacing))
        last = _snap_down(p, min(top, limit) - p.tine_height)
        if last < first - d.TOLERANCE:
            continue
        # From the lower edge of the stretch to its top, spread evenly, as many
        # as keep them no further apart than the tine spacing.
        steps = math.ceil((last - first) / p.tine_spacing - d.TOLERANCE)
        for step in range(max(steps, 0) + 1):
            z = first if steps <= 0 else p.snap_to_layer(first + (last - first) * step / steps)
            if zs and z < zs[-1] + p.least_tine_spacing - d.TOLERANCE:
                continue
            if count and len(zs) >= count:
                return zs
            zs.append(z)
    return zs


def _under_tine(frame):
    """The contours of a fin beside the lowest line in the planes its tines
    stand in, leaving out those further off, which only reach for where they end."""
    return frame.tine_edges[2] if frame.tine_edges else ()


def _resting_bands(frame):
    """The stretches of height a tine rests on along the contour of `frame`:
    beside the lowest line of a round side, those the contours at both its
    edges rest on too, so its grid starts where the first tine can rest whole,
    not a spacing further up.

    INPUTS this has to withstand:
      no contours at the edges of the tine  ->  the bands of the contour
      bands starting at different heights   ->  from the highest of those starts
      bands that do not overlap             ->  none from those
    """
    bands = frame.contour.bands()
    for line in _under_tine(frame):
        bands = [(max(low, other_low), min(high, other_high)) for low, high in bands
                 for other_low, other_high in line.bands() if max(low, other_low) < min(high, other_high)]
    return bands


def face_tines(p, frame, tine_count, restart):
    """Bottoms of the tines for the face as a whole (mm, from the bed) and the
    fin height: the one grid from the bed (tine_heights()). With `restart`, a
    face that starts above the bed gets them spread over it from its lower
    edge, as a fin on it would, and as many of a fixed count as fit there:
    where the one grid happens to lie on such a face is no reason to refuse it.
    Along a contour, with the tine restart on, they are spread over each
    stretch the tines rest on, from its lower edge, so the thinner part above
    a step is held from its bottom on.

    INPUTS this has to withstand:
      without restart                       ->  tine_heights(), its errors as they are
      restart, a face from the bed up       ->  tine_heights(), its errors as they are
      restart, a face above the bed         ->  spread from its lower edge to its top
      restart, no grid tine on that face    ->  spread over it, no error
      restart, fewer than a fixed count fit ->  those that fit, no error
      restart, no tine fits at all          ->  the error of tine_heights()
      restart, a fin height above the face  ->  the error of tine_heights()
      contour, tine restart on              ->  spread over each stretch it holds the
                                                tines on, lowest first
      contour, tine restart off             ->  tine_heights(): the one grid
    """
    room = frame.room
    limit = p.fin_height if p.fin_height > 0 else room
    if frame.contour is not None:
        # `restart` is off for every round side, whose one grid is kept; along
        # a contour the tine restart of the parameters starts it anew on each
        # stretch the tines rest on.
        zs = _spread(p, _resting_bands(frame), limit, tine_count) if p.tine_restart and limit <= room else []
    else:
        floor = frame.face_bottom_z - frame.bed_z
        if not restart or floor <= d.TOLERANCE:
            return tine_heights(p, frame, tine_count)
        zs = _spread(p, [(floor, frame.face_top_z - frame.bed_z)], limit, tine_count) if limit <= room else []
    if not zs:
        # The face has no room for a tine, or the fin is set above it: as the one grid says.
        return tine_heights(p, frame, tine_count)
    return zs, p.fin_height if p.fin_height > 0 else zs[-1] + p.tine_height


def restarted_tines(p, frame, face, t0, thickness, limit, count):
    """Bottoms of the tines of the fin starting at t0 (mm, from the bed), on
    a grid that starts anew at the lower edge of each stretch of `face` under
    the fin: at the bottom of the face and above every gap the fin bridges.
    Within a stretch they are spread evenly from its lower edge to its top,
    no further apart than the tine spacing, so a tine sits just above every
    gap and one at the top of the face; between two stretches at least one
    free layer is left. None above `limit`, `count` at most if given, the
    lowest first; None for a face that rises from the bed in one stretch,
    which keeps the one grid.

    INPUTS this has to withstand:
      a face from the bed up, no gap        ->  None: the one grid, as without the
                                                restart
      a face starting above the bed         ->  the first tine on the first layer from its
                                                lower edge up, right above a fillet below it
      a hole under the fin                  ->  one just below it, one just above it
      a stretch lower than a tine           ->  no tine in it
      a stretch with room for one tine      ->  that tine at its lower edge
      a gap narrower than a free layer      ->  the next tine a free layer above the
                                                one below
      no face under the fin at all          ->  no tine
      a face narrower than the fin at its
        lower or upper end                  ->  spread only where it reaches under the fin
      a fin on a corner, past the end       ->  as far as the face reaches under its tine
      a hole under the flank, clear of the
        tine                                ->  no gap: the outermost points count
      the fin past the end of the face      ->  no tine
      a notch in the end of the face under
        the flank, at mid height            ->  spread through it, wide_enough() leaves those
                                                out: only the ends of the face limit the spread
    """
    start = tine_start(p, t0, thickness)
    left, right = _bands_at(frame, face, start), _bands_at(frame, face, start + p.tine_width)
    # Where the whole width of a tine lies on the face: both its sides do.
    bands = sorted((max(a0, b0), min(a1, b1)) for a0, a1 in left for b0, b1 in right
                   if min(a1, b1) - max(a0, b0) > d.TOLERANCE)
    # A face that rises from the bed in one stretch keeps the one grid, as
    # without the restart: its fins are as they were.
    if len(bands) == 1 and bands[0][0] <= d.TOLERANCE:
        return None
    # Spread only as high as the face reaches under the fin as a whole: a tine
    # spread beyond that is left out by wide_enough() and leaves a wider gap.
    first, last = _fin_reach(p, t0, thickness)
    # A fin on a corner reaches as far as its tine: those cuts are made already.
    edges = [left, right] if (first, last) == (start, start + p.tine_width) else [
        _bands_at(frame, face, first), _bands_at(frame, face, last)]
    if not all(edges):
        return []
    bottom = max(edge[0][0] for edge in edges)
    top = min(max(band[1] for band in edge) for edge in edges)
    within = [(max(low, bottom), min(high, top)) for low, high in bands
              if min(high, top) - max(low, bottom) > d.TOLERANCE]
    return _spread(p, within, limit, count)


def touching_at(frame, face, p, tine_z, t0, thickness):
    """The heights in `tine_z` at which the tine of the fin starting at t0
    lies on `face`, as contact_share() finds it; along a contour, where the
    flank keeps its distance from the part (contour.Contour.rests()), beside
    the lowest line of a round side also at both edges of the tine, so a hole
    under it leaves it out."""
    if frame.contour is not None:
        contours = (frame.contour, *_under_tine(frame))
        return {z for z in tine_z if all(line.rests(z, z + p.tine_height) for line in contours)}
    start = tine_start(p, t0, thickness)
    return {z for z in tine_z if contact_share(frame, face, start, p, z) >= d.TINE_MIN_CONTACT - d.TOLERANCE}


def contact_share(frame, face, t, p, z):
    """Share of the end of the tine at t and height z that lies on the face:
    1 on the whole face, 0 over a recess or a hole in it.

    A round side only touches the plane of the frame along its lowest line; the
    end is pushed into the part by ROUND_SIDE_MAX_DROP instead, and the side has
    to fill it there. It is curved, so its piece inside is a little larger than
    the end it fills.
    """
    bottom, top = frame.bed_z + z, frame.bed_z + z + p.tine_height
    ring = [frame.point(t, frame.s_face(bottom), bottom), frame.point(t + p.tine_width, frame.s_face(bottom), bottom),
            frame.point(t + p.tine_width, frame.s_face(top), top), frame.point(t, frame.s_face(top), top)]
    end = Part.Face(Part.makePolygon(ring + ring[:1]))
    if not frame.round_side:
        return end.common(face).Area / end.Area
    normal = frame.normal()
    probe = end.translated(normal * d.TOLERANCE).extrude(-normal * (d.ROUND_SIDE_MAX_DROP + d.TOLERANCE))
    return min(1.0, probe.common(face).Area / end.Area)


def tine_end(p, frame, z):
    """Where the tine at height z over the bed ends, as one_fin() builds it
    and tine_end_points() measures it: the heights of its bottom and top, and
    how far out its end lies at each (s of the frame). It ends parallel to
    the face, following its slope, on it or the tine clearance short of it,
    so every tine is equally long, also where the part behind the face ends
    early. Along a contour it ends on the contour, or the clearance off it."""
    bottom = frame.bed_z + z
    top = bottom + p.tine_height
    if frame.contour is not None:
        return (bottom, top, *frame.contour.tine_ends(z, z + p.tine_height))
    return bottom, top, frame.s_flank(bottom, p.clearance), frame.s_flank(top, p.clearance)


def flank_bend(frame, t):
    """How far the flank of a fin beside the lowest line lies at place `t` from
    where the contour measures it, as it follows the radius of the side.

    INPUTS this has to withstand:
      where the contour is measured         ->  0
      further round the side                ->  less than 0, towards the part
      past the radius of the flank          ->  from the last place on it
    """
    middle, nearest, radius = frame.flank_curve

    def along_normal(place):
        return math.sqrt(max(0.0, radius ** 2 - (place - middle) ** 2))
    return (along_normal(t) - along_normal(nearest)) / frame.n_out


def round_move(frame, s, z, t):
    """How far along the normal of the frame a point of the flank at (s, z), in
    the plane the contour is measured in, comes in the plane at `t`, turned about
    the axis of the side at its own radius: so a step or a cone the flank goes
    over keeps its place along the axis in every plane, and its own curve.

    INPUTS this has to withstand:
      on the side, further round            ->  less than 0, as flank_bend()
      on a thinner step                     ->  more, by its own radius
      past its radius, or nearly            ->  no further in than ROUND_MOVE_MOST times
                                                the side itself: it stays further off
      at the height of the axis or behind   ->  0: not the side the fin stands on
    """
    middle, nearest, _ = frame.flank_curve
    along_normal = s * frame.n_out + z * frame.n_z - (frame.c - frame.radius)
    if along_normal <= 0:
        return 0.0
    radius = math.hypot(along_normal, nearest - middle)
    # A step about as thin as the plane is far from the axis falls away ever
    # steeper there; staying further off is safe, a flank plunging in twists.
    least = flank_bend(frame, t) * ROUND_MOVE_MOST * frame.n_out
    return max(least, math.sqrt(max(0.0, radius ** 2 - (t - middle) ** 2)) - along_normal)


def side_foot_start(p, frame, t0, thickness):
    """How far out the foot of the fin starting at t0 beside the lowest line
    starts: under all of its flank, which lies furthest in at the place on the fin
    furthest round the side; further out where the part leaves it no room there."""
    bend = min(flank_bend(frame, t0), flank_bend(frame, t0 + thickness))
    return frame.contour.flank(p.foot_height) + frame.flank_out + bend + frame.foot_out


def side_tine(p, frame, t0, thickness, z):
    """The tine at height z of the fin starting at t0 beside the lowest line of
    a round side: level, as every tine, but running straight at the axis of the
    side at its height, as a ray, not parallel to the fin under the lowest line.
    That is the shortest way across the gap to the side. As two rings of (t, s),
    its outline at its bottom and at its top: both corners where it starts in the
    fin, then where it ends on the part, the clearance short, right, middle, left.
    It leaves the fin in the middle of its thickness.

    Seen from above the part lies along s at the place t; where a ray along
    the tine meets it is found from the contours in the upright planes around
    the tine (frame.tine_edges), straight between them.

    INPUTS this has to withstand:
      plain side                            ->  ends the clearance off it across its width
      fin moved round the side              ->  the ray at the axis from there
      fin over the lowest line              ->  straight out along s, as the one there
      fin moved out from the part           ->  the same ray, longer
      fin thicker than the tine             ->  still leaves it in the middle
      a step of the part past its start     ->  ends just past where it starts, not back
                                                through the fin
    """
    t_fin = t0 + thickness / 2
    bottom, top = frame.bed_z + z, frame.bed_z + z + p.tine_height
    # Where it leaves the fin, in the middle of its thickness: on the flank there.
    line = frame.contour
    middle_height = (bottom + top) / 2
    leaves = line.flank(z + p.tine_height / 2) + frame.flank_out
    leaves += round_move(frame, leaves, middle_height, t_fin) / frame.n_out
    # The blade comes no further in than its foot, also above it.
    if p.foot_height > 0:
        leaves = max(leaves, side_foot_start(p, frame, t0, thickness))
    middle = (frame.along_min + frame.along_max) / 2
    towards_t = middle - t_fin
    # The axis lies a radius behind the plane of the side, along its normal.
    towards_s = frame.s_face((bottom + top) / 2) - frame.radius / frame.n_out - leaves
    length = math.hypot(towards_t, towards_s)
    along_t, along_s = towards_t / length, towards_s / length
    across_t, across_s = -along_s, along_t
    width = p.tine_width / 2
    # It starts as far back in the fin as its corners need to lie inside.
    back = d.TINE_INTO_FIN + width
    t_middle, start = t_fin - back * along_t, leaves - back * along_s
    planes, ends, _ = frame.tine_edges
    per_plane = [line_at.tine_ends(z, z + p.tine_height) for line_at in ends]

    def part_at(t, which):
        """How far out the end of the tine lies at place t, at its bottom or top."""
        if t <= planes[0]:
            k = 0
        elif t >= planes[-1]:
            k = len(planes) - 2
        else:
            k = next(k for k in range(len(planes) - 1) if planes[k] <= t <= planes[k + 1])
        share = (t - planes[k]) / (planes[k + 1] - planes[k])
        return per_plane[k][which] + (per_plane[k + 1][which] - per_plane[k][which]) * share

    def end_of(offset, which):
        """Where the ray `offset` to the side of the middle of the tine meets the part."""
        t_from, s_from = t_middle + offset * across_t, start + offset * across_s
        def still_out(run):
            return s_from + run * along_s > part_at(t_from + run * along_t, which)

        # Halved until it lands, as on a thin step the part rises steeply
        # towards the axis. Where a step lies past its start: just past that.
        short, long = d.TINE_INTO_FIN, length
        if not still_out(short):
            long = short
        for _ in range(SIDE_TINE_STEPS):
            run = (short + long) / 2
            short, long = (run, long) if still_out(run) else (short, run)
        return t_from + long * along_t, s_from + long * along_s

    rings = []
    for which in (0, 1):
        rings.append([(t_middle - width * across_t, start - width * across_s),
                      (t_middle + width * across_t, start + width * across_s),
                      end_of(width, which), end_of(0.0, which), end_of(-width, which)])
    return rings


def tine_end_points(p, frame, t0, thickness, z):
    """The corners and the middle of the end of the tine of the fin starting
    at t0 at height z over the bed, see tine_end() and side_tine()."""
    bottom, top = frame.bed_z + z, frame.bed_z + z + p.tine_height
    if frame.tine_edges is not None:
        low, high = side_tine(p, frame, t0, thickness, z)
        corners = [frame.point(t, s, height) for ring, height in ((low, bottom), (high, top))
                   for t, s in (ring[2], ring[4])]
        return corners + [frame.point((low[3][0] + high[3][0]) / 2, (low[3][1] + high[3][1]) / 2, (bottom + top) / 2)]
    _, _, s_bottom, s_top = tine_end(p, frame, z)
    t_tine = tine_start(p, t0, thickness)
    corners = [frame.point(t, s, height)
               for t in (t_tine, t_tine + p.tine_width) for s, height in ((s_bottom, bottom), (s_top, top))]
    # The end runs straight from bottom to top: its middle lies halfway.
    middle = frame.point(t_tine + p.tine_width / 2, (s_bottom + s_top) / 2, (bottom + top) / 2)
    return corners + [middle]


# How many times as far as the side itself a point of a flank beside the lowest
# line may turn in over a thinner step.
ROUND_MOVE_MOST = 2.0
# How often the way to the end of a tine beside the lowest line is halved.
SIDE_TINE_STEPS = 16
# What is wrong with the end of a tine, see tine_end_fault().
TINE_MISSES, TINE_CUTS_IN = "misses", "cuts in"


def tine_end_fault(surface, points, clearance):
    """Whether the end of a tine, its corners and middle `points`, lies on
    `surface`, the faces of the part the fins carry, or `clearance` short of
    them, within TINE_END_TOLERANCE: None if it does, TINE_CUTS_IN where a
    point reaches further into the part, else TINE_MISSES where one stays
    further off. The faces themselves are measured, not the plane the tine was
    planned on, so a round side, a face a STEP file brings in halves and a
    solid converted from a mesh are held to the same.

    Which side of a face a point lies on is told by the outward normal there,
    at the nearest point, not by classifying it in the whole part: that costs
    as much again as building the fins, at every drag of an arrow.

    INPUTS this has to withstand:
      every point on the surface, no clearance       ->  None
      every point the clearance off the surface      ->  None
      a point off by less than the tolerance, as on
        a round side falling away behind its plane    ->  None
      a point further off than clearance and tolerance ->  TINE_MISSES
      a point behind the face beyond the tolerance  ->  TINE_CUTS_IN, also where
                                                        another misses
      a point nearest an edge of the faces, past
        their end                                   ->  counted in front: it misses
                                                        where it is that far off
      a point the kernel cannot measure             ->  None: not said to be wrong
    """
    offsets = []
    for point in points:
        try:
            distance, nearest, where = surface.distToShape(Part.Vertex(point))
        except Part.OCCError:
            continue
        on_surface, kind, index, uv = nearest[0][0], where[0][0], where[0][1], where[0][2]
        behind = kind == "Face" and (point - on_surface).dot(surface.Faces[index].normalAt(*uv)) < 0
        offsets.append((-distance if behind else distance) - clearance)
    if any(offset < -d.TINE_END_TOLERANCE for offset in offsets):
        return TINE_CUTS_IN
    if any(offset > d.TINE_END_TOLERANCE for offset in offsets):
        return TINE_MISSES
    return None
