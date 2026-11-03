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

# Said where the face is narrower than a fin, or its tine, at every tine height.
NARROW_AT_EVERY_TINE = QT_TRANSLATE_NOOP("FinSnap", "the face is narrower than the %.2f mm a fin needs at every tine")


def tine_heights(p, frame, tine_count):
    """Bottoms of the tines above the bed, on the layer grid, and the fin height."""
    room = frame.face_top_z - frame.bed_z - d.FACE_TOP_MARGIN
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


def _span_at(face, frame, height):
    """(first, last) position along the face where the level plane at
    `height` crosses the outer edges of `face`, None if it misses. Holes
    inside the face lie within, so only its outer wires are cut: much faster
    than slicing the face itself, with the same outermost points."""
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
    if p.placement == d.PLACEMENT_CORNERS or p.placement in d.PLACEMENT_ONE_CORNER:
        first = tine_start(p, t0, thickness)
        last = first + p.tine_width
    else:
        first, last = t0, t0 + thickness
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
    bore across that plane splits them."""
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
    room = frame.face_top_z - frame.bed_z - d.FACE_TOP_MARGIN
    limit = p.fin_height if p.fin_height > 0 else room
    if frame.contour is not None:
        # `restart` is off for every round side, whose one grid is kept; along
        # a contour the tine restart of the parameters starts it anew on each
        # stretch the tines rest on.
        zs = _spread(p, frame.contour.bands(), limit, tine_count) if p.tine_restart and limit <= room else []
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
    return _spread(p, bands, limit, count)


def touching_at(frame, face, p, tine_z, t0, thickness):
    """The heights in `tine_z` at which the tine of the fin starting at t0
    lies on `face`, as contact_share() finds it; along a contour, where the
    flank keeps its distance from the part (contour.Contour.rests())."""
    if frame.contour is not None:
        return {z for z in tine_z if frame.contour.rests(z, z + p.tine_height)}
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


def tine_end_points(p, frame, t0, thickness, z):
    """The corners and the middle of the end of the tine of the fin starting
    at t0 at height z over the bed, see tine_end()."""
    bottom, top, s_bottom, s_top = tine_end(p, frame, z)
    t_tine = tine_start(p, t0, thickness)
    corners = [frame.point(t, s, height)
               for t in (t_tine, t_tine + p.tine_width) for s, height in ((s_bottom, bottom), (s_top, top))]
    # The end runs straight from bottom to top: its middle lies halfway.
    middle = frame.point(t_tine + p.tine_width / 2, (s_bottom + s_top) / 2, (bottom + top) / 2)
    return corners + [middle]


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
