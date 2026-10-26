"""Fin geometry for one supported face.

The part stands tilted on the bed. A planar face of it leans outward over the
bed (its normal points down and to the side). Fins stand under that face: each
fin is a vertical wall whose inner edge, the flank, runs parallel to the face at
the gap distance, plus the tine clearance. Horizontal tines reach across the gap
and end on the face, or the tine clearance short of it. A thin foot on the bed holds the fin down.

LOCAL FRAME of a face: `out` is the horizontal direction the face leans
towards, `along` runs horizontally along the face, z is up. A point is
t * along + s * out + z * Z. The face is the plane n . P = c with
n = n_out * out + n_z * Z, so at height z it lies at
    s_face(z) = (c - n_z * z) / n_out
and a plane offset by a distance along n at
    s_flank(z, offset) = (c + offset - n_z * z) / n_out:
the flank at the gap plus the tine clearance, the end of a tine at the
tine clearance alone.
The fin occupies s >= s_flank(z); the part lies at smaller s.

INPUTS this has to withstand (build()):
  inclined planar face, part standing on the bed  ->  FinResult
  face not planar                       ->  FinError
  face vertical or flat (no lean)       ->  FinError: nothing to support
  face leaning upward (normal up)       ->  FinError: it is not an overhang
  face shorter along its edge than one
    fin plus both insets                ->  FinError
  corners: face shorter than a fin, a
    tine and FOOT_CLEARANCE             ->  FinError
  corners: each tine whole on the face,
    its outer side flush with the end   ->  FinResult, fins reach past the ends
  left or right corner                  ->  one fin, as on that end with corners
  left or right corner, face narrower
    than a tine                         ->  FinError
  tine_clearance > 0                    ->  tines end that far short of the face,
                                            measured along its normal; the fin
                                            moves out as far, so they keep their length
  no tine fits below the top of the face ->  FinError
  hand-set first tine half a layer off
    the grid, rounding two tines closer
    than a free layer                   ->  the upper one moves up a layer
  face narrower than the fin at some
    tines (side of a frustum)           ->  those tines left out, warning
  face narrower than the fin at every
    tine                                ->  FinError
  fixed tine count, some tines miss the
    face (narrow face or recess)        ->  those tines left out, warning
  face ending above the bed             ->  no tines below it
  manual fin_height below the first tine ->  FinError
  fins standing closer than they are
    thick plus FOOT_CLEARANCE           ->  FinError: they would collide
  fin collides with other geometry of
    the part (closer than the gap)      ->  FinError naming the distance
  tine wholly or partly over a recess
    or hole in the face                 ->  tine left out, warning
  upper tines of a fin over a recess,
    automatic fin height                ->  that fin ends at its highest tine left;
                                            the fin height of the result is the
                                            tallest fin
  upper tines over a recess, manual
    fin height                          ->  the fin keeps the height given
  every tine of a fin over a recess     ->  fin left out, warning
  face split by a groove into faces of
    its own in one plane                ->  one support: the fin reaches over the
                                            gap, tines over it left out, warning
  fins over the groove would run into the
    part higher up                      ->  fins under the selected face alone,
                                            warning naming why
  every tine of every fin over a recess ->  FinError
  fins removed by hand (left_out)       ->  not built, the others where they were
  every fin removed by hand             ->  FinError
  fin overlaps the part (separate mode) ->  FinError
  tine shorter than TINE_MIN_LENGTH_BEADS
    beads                               ->  warning in FinResult, no error
  face inclined outside FACE_ANGLE_MIN
    to FACE_ANGLE_MAX                    ->  warning in FinResult, no error
"""

import math
from collections import namedtuple
from dataclasses import dataclass, field, replace

import FreeCAD as App
import Part

from . import defaults as d
from . import orient
from .i18n import translate
from .shapes import bounds, middle_normal, moved

V = App.Vector
UP = V(0, 0, 1)


class FinError(ValueError):
    """The fin cannot be built on this face."""


@dataclass
class Frame:
    out: App.Vector
    along: App.Vector
    n_out: float
    n_z: float
    c: float
    bed_z: float
    along_min: float
    along_max: float
    face_top_z: float
    face_bottom_z: float

    def s_face(self, z):
        return (self.c - self.n_z * z) / self.n_out

    def s_flank(self, z, gap):
        return (self.c + gap - self.n_z * z) / self.n_out

    def point(self, t, s, z):
        return self.along * t + self.out * s + UP * z

    def section(self, t, points_sz, width):
        """A prism: polygon in the (s, z) plane at t, extruded `width` along the face."""
        ring = [self.point(t, s, z) for s, z in points_sz]
        face = Part.Face(Part.makePolygon(ring + ring[:1]))
        return face.extrude(self.along * width)


@dataclass
class FinResult:
    fins: Part.Shape
    bodies: list
    tines: list
    height: float
    thickness: float
    tine_z: list
    positions: list
    foot_half_width: float
    warnings: list = field(default_factory=list)
    # The faces the fins stand under: the selected one, and the pieces beyond a
    # groove across it when the fins reach over it.
    carried: list = field(default_factory=list)
    # The number of each fin built, from the left, seen from outside: what
    # left_out of build() refers to.
    numbers: list = field(default_factory=list)
    # How many fins the face was planned for, before any was removed or left out.
    planned: int = 0
    # Tines that found no face, as shapes, for the red marks while editing.
    dropped: list = field(default_factory=list)
    # Where each fin built starts along the face (mm, as frame.along), by number.
    starts: dict = field(default_factory=dict)
    # The direction along the face, to the right seen from outside.
    along: App.Vector = None
    # The height of each fin built (mm, from the bed), by number.
    heights: dict = field(default_factory=dict)


def support_of(part, face):
    """The face and the faces of `part` above and below it in its plane, as one shape.

    A groove running across a face splits it, in FreeCAD, into faces of their
    own; the fin reaches over the gap and supports them all. Only faces that
    overlap the selected one along the face count: pieces beside it, the legs
    of a U profile or the halves beside an upright slot, are faces of their own
    that the fin does not stand under.

    INPUTS this has to withstand:
      no other face in its plane            ->  the face itself
      groove across the face                ->  the pieces above and below, as one
      upright slot, U profile (pieces side
        by side along the face)             ->  the face itself
      groove across and slot beside         ->  the pieces above and below only
      face without a lean (flat or upright) ->  the face itself; frame_of() refuses it
    """
    normal = middle_normal(face)
    horizontal = V(normal.x, normal.y, 0)
    if horizontal.Length < d.MIN_NORMAL_COMPONENT:
        return face
    along = UP.cross(horizontal.normalize())

    def span(candidate):
        ts = [vertex.Point.dot(along) for vertex in candidate.Vertexes]
        return min(ts), max(ts)

    low, high = span(face)
    c = normal.dot(face.Vertexes[0].Point)
    pieces = [face]
    for other in part.Faces:
        if other.isSame(face) or other.findPlane() is None:
            continue
        in_plane = abs(normal.dot(other.Vertexes[0].Point) - c) <= d.TOLERANCE
        if middle_normal(other).dot(normal) < 1 - d.TOLERANCE or not in_plane:
            continue
        other_low, other_high = span(other)
        if other_low < high - d.TOLERANCE and other_high > low + d.TOLERANCE:
            pieces.append(other)
    return face if len(pieces) == 1 else Part.makeCompound(pieces)


def frame_of(part, face, support=None):
    """The frame of `face`; its extent along and up is that of `support`, the
    face with the faces in its plane, if given."""
    if face.findPlane() is None:
        raise FinError(translate("FinSnap", "the selected face is not planar"))
    n = middle_normal(face)
    horizontal = V(n.x, n.y, 0)
    if n.z > -d.MIN_NORMAL_COMPONENT:
        raise FinError(translate("FinSnap", "the selected face does not lean over the bed"))
    if horizontal.Length < d.MIN_NORMAL_COMPONENT:
        raise FinError(translate("FinSnap", "the selected face is flat; it rests on the bed or needs regular support"))

    out = horizontal.normalize()
    along = UP.cross(out)
    extent = face if support is None else support
    ts = [v.Point.dot(along) for v in extent.Vertexes]
    face_box = bounds(extent)
    return Frame(out=out, along=along, n_out=n.dot(out), n_z=n.z,
                 c=n.dot(face.Vertexes[0].Point), bed_z=bounds(part).ZMin,
                 along_min=min(ts), along_max=max(ts), face_top_z=face_box.ZMax,
                 face_bottom_z=face_box.ZMin)


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


def _extent_at(face, frame, z, p):
    """(first, last) position along the face over the height of a tine at z, None if it misses."""
    low, high = frame.along_min, frame.along_max
    for height in (frame.bed_z + z, frame.bed_z + z + p.tine_height):
        ts = [v.Point.dot(frame.along) for wire in face.slice(UP, height) for v in wire.Vertexes]
        if not ts:
            return None
        low, high = max(low, min(ts)), min(high, max(ts))
    return low, high


def room_for_one_fin(p, thickness):
    """The least stretch along the face a fin needs: inside both insets, or
    for a fin on each corner, both tines and the clearance between the fins."""
    if p.placement == d.PLACEMENT_CORNERS:
        return thickness + d.FOOT_CLEARANCE + p.tine_width
    if p.placement in d.PLACEMENT_ONE_CORNER:
        return p.tine_width
    return thickness + 2 * p.end_inset


def tines_on_face(face, frame, tine_z, p, width):
    """The longest run of consecutive tines that all meet the face over at
    least `width`, and the stretch along the face they share.

    A face that narrows, like the side of a frustum standing on a corner, is
    narrower at some tines than a fin is thick; those tines are left out. A
    height where no face lies at all, the gap between two faces in one plane,
    only leaves its own tine out; the run goes on above it.
    Returns (tine heights, first, last, heights over a gap); raises if no tine
    has room.
    """
    extents = [_extent_at(face, frame, z, p) for z in tine_z]
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
        raise FinError(translate("FinSnap", "the face is narrower than the %.2f mm a fin needs at every tine")
                       % width)
    return (*best, gaps)


def thickness_for(p, height):
    if p.fin_thickness > 0:
        return p.fin_thickness
    grown = d.FIN_THICKNESS_BASE * max(1.0, height / d.FIN_THICKNESS_BASE_HEIGHT)
    return max(grown, d.FIN_MIN_BEADS * p.bead_width)


def positions_for(p, frame, thickness):
    """Start of each fin along the face."""
    if p.placement == d.PLACEMENT_CORNERS or p.placement in d.PLACEMENT_ONE_CORNER:
        # The tine sits in the middle of the fin; its outer side ends flush
        # with the end of the face, the fin reaches past it. Along the face
        # runs to the right, seen from outside.
        overhang = (thickness - p.tine_width) / 2
        positions = [frame.along_min - overhang, frame.along_max - p.tine_width - overhang]
        if p.placement == d.PLACEMENT_CORNER_LEFT:
            return positions[:1]
        if p.placement == d.PLACEMENT_CORNER_RIGHT:
            return positions[1:]
        if positions[1] - positions[0] < thickness + d.FOOT_CLEARANCE:
            raise FinError(translate("FinSnap", "the face is too short for a fin on each corner"))
        return positions

    lo = frame.along_min + p.end_inset
    hi = frame.along_max - p.end_inset - thickness
    if hi < lo - d.TOLERANCE:
        raise FinError(translate("FinSnap", "the face is too short for a fin of %.2f mm") % thickness)
    middle = (lo + hi) / 2
    span = hi - lo

    if p.placement == d.PLACEMENT_CENTER:
        count = 1
    elif p.placement == d.PLACEMENT_ENDS:
        count = 2
    elif p.placement == d.PLACEMENT_DISTRIBUTED:
        count = p.fin_count
    else:
        length = frame.along_max - frame.along_min
        count = max(1, math.ceil(length / p.face_length_per_fin))

    if count == 1:
        return [middle]
    pitch = span / (count - 1)
    if pitch < thickness + d.FOOT_CLEARANCE:
        raise FinError(translate("FinSnap", "%d fins do not fit side by side on this face") % count)
    return [lo + i * pitch for i in range(count)]


def foot_half_width_for(p, half_length, thickness, positions):
    wanted = p.foot_half_width if p.foot_half_width > 0 else half_length * p.foot_width_ratio
    if len(positions) > 1:
        pitch = min(b - a for a, b in zip(positions, positions[1:]))
        wanted = min(wanted, (pitch - d.FOOT_CLEARANCE) / 2)
    return max(wanted, thickness / 2)


def foot_span(p, frame, height):
    """Where the foot starts and ends, measured outward.

    The foot has vertical sides. It starts where the flank passes its top
    edge, so it keeps the gap to the part along its whole height; lower down
    the flank lies further in and the clearance only grows.
    """
    top = frame.bed_z + p.foot_height
    s_from = frame.s_flank(top, p.fin_offset)
    s_to = frame.s_flank(frame.bed_z + height, p.fin_offset) + p.fin_plateau + p.foot_overhang
    return s_from, s_to


def foot(p, frame, t0, thickness, s_from, s_to, half_width):
    z = frame.bed_z
    height = p.foot_height
    if p.foot_shape == d.FOOT_RECTANGLE:
        t_mid = t0 + thickness / 2
        return frame.section(t_mid - half_width, [(s_from, z), (s_to, z), (s_to, z + height),
                                                  (s_from, z + height)], 2 * half_width)

    half_length = (s_to - s_from) / 2
    centre = frame.point(t0 + thickness / 2, s_from + half_length, z)
    major, minor = (frame.out, frame.along) if half_length >= half_width else (frame.along, frame.out)
    a, b = max(half_length, half_width), min(half_length, half_width)
    ellipse = Part.Ellipse(centre + major * a, centre + minor * b, centre)
    return Part.Face(Part.Wire(ellipse.toShape())).extrude(UP * height)


def _mm_list(values):
    """Lengths for a message, smallest first: "1.0, 6.0"."""
    return ", ".join("%.1f" % value for value in sorted(values))


def tine_start(p, t0, thickness):
    """Where the tines of the fin starting at t0 begin along the face: in the middle of the fin."""
    return t0 + (thickness - p.tine_width) / 2


def contact_share(frame, face, t, p, z):
    """Share of the end of the tine at t and height z that lies on the face:
    1 on the whole face, 0 over a recess or a hole in it."""
    bottom, top = frame.bed_z + z, frame.bed_z + z + p.tine_height
    ring = [frame.point(t, frame.s_face(bottom), bottom), frame.point(t + p.tine_width, frame.s_face(bottom), bottom),
            frame.point(t + p.tine_width, frame.s_face(top), top), frame.point(t, frame.s_face(top), top)]
    end = Part.Face(Part.makePolygon(ring + ring[:1]))
    return end.common(face).Area / end.Area


def one_fin(p, frame, t0, height, thickness, half_foot, tine_z):
    """A fin without tines, and its tines, which end on the face."""
    zb = frame.bed_z
    s_bottom = frame.s_flank(zb, p.fin_offset)
    s_top = frame.s_flank(zb + height, p.fin_offset)
    s_out = s_top + p.fin_plateau

    if p.foot_shape == d.FOOT_NONE:
        body = frame.section(t0, [(s_bottom, zb), (s_out, zb), (s_out, zb + height),
                                  (s_top, zb + height)], thickness)
    else:
        # Below the top of the foot the slanted flank would only add a thin tip
        # under the part; the blade ends vertically there and the foot carries it.
        s_from, s_to = foot_span(p, frame, height)
        foot_top = zb + p.foot_height
        body = frame.section(t0, [(s_from, zb), (s_out, zb), (s_out, zb + height),
                                  (s_top, zb + height), (s_from, foot_top)], thickness)
        body = body.fuse(foot(p, frame, t0, thickness, s_from, s_to, half_foot))

    tines = []
    t_tine = tine_start(p, t0, thickness)
    for z in tine_z:
        bottom = zb + z
        top = bottom + p.tine_height
        # The fin edge furthest out along the tine: the flank at its top, or the
        # vertical inner end of the foot for a tine below the top of the foot.
        # Measured from there, a tine always reaches into the fin.
        edge = frame.s_flank(top, p.fin_offset)
        if p.foot_height > 0 and bottom < zb + p.foot_height:
            edge = max(edge, foot_span(p, frame, height)[0])
        s_into_fin = edge + d.TINE_INTO_FIN
        # The tine ends parallel to the face, following its slope, on it or the
        # tine clearance short of it, so every tine is equally long, also where
        # the part behind the face ends early.
        s_end_bottom = frame.s_flank(bottom, p.tine_clearance)
        s_end_top = frame.s_flank(top, p.tine_clearance)
        tines.append(frame.section(t_tine, [(s_end_bottom, bottom), (s_into_fin, bottom),
                                            (s_into_fin, top), (s_end_top, top)], p.tine_width))
    return body, tines


def check(p, part, fins, bodies):
    """Fins clear of the part. That every tine reaches the face is settled when
    the tines are chosen, by contact_share()."""
    if p.connection == d.CONNECTION_SEPARATE:
        overlap = fins.common(part).Volume
        if overlap > d.TOLERANCE:
            raise FinError(translate("FinSnap", "the fins overlap the part by %.4f mm3") % overlap)

    for body in bodies:
        distance = body.distToShape(part)[0]
        if distance < p.fin_offset - d.TOLERANCE:
            raise FinError(translate("FinSnap", "a fin comes within %.3f mm of the part, closer than the %.3f mm it "
                                                  "keeps from the face")
                           % (distance, p.fin_offset))


def build(part, face, p, tine_count=None, left_out=(), shifts=None, heights=None):
    """Fins under `face` of `part`, reaching over a groove to the pieces beyond
    it. tine_count overrides p.tine_count (counter fin). Fins are named by their
    number from the left, seen from outside, looking at the face, counting from
    1: left_out are removed by hand, shifts moves fins along the face (mm, to
    the right is positive), heights sets the height of single fins (mm).

    The fins over a groove are taller, and where the part reaches out in front
    of the face higher up they would run into it. Then they stand under the
    selected face alone, as they did before pieces were carried along.
    """
    p.validate()
    shifts, heights = shifts or {}, heights or {}
    support = support_of(part, face)
    if support is face:
        return _build(part, face, face, p, tine_count, left_out, shifts, heights)
    try:
        return _build(part, face, support, p, tine_count, left_out, shifts, heights)
    except FinError as error:
        reason = str(error)
    alone = _build(part, face, face, p, tine_count, left_out, shifts, heights)
    alone.warnings.append(translate("FinSnap", "fins under the selected face alone, not reaching over the "
                                               "groove: %s") % reason)
    return alone


def _build(part, face, support, p, tine_count, left_out, shifts, heights):
    frame = frame_of(part, face, support)
    count = p.tine_count if tine_count is None else tine_count
    all_z, height = tine_heights(p, frame, count)
    thickness = thickness_for(p, height)
    if p.tine_width > thickness:
        raise FinError(translate("FinSnap", "tines (%.2f mm) are wider than the fin (%.2f mm)")
                       % (p.tine_width, thickness))
    tine_z, low, high, gap_z = tines_on_face(support, frame, all_z, p, room_for_one_fin(p, thickness))
    # Also with a fixed tine count: tines the narrow face cannot take are left
    # out and named, as over a recess, rather than refusing the whole fin.
    narrow_heights = set(all_z) - set(tine_z) - set(gap_z)
    if narrow_heights:
        # Fewer tines make a lower and so a thinner fin; it still fits where the thicker one did.
        height = p.fin_height if p.fin_height > 0 else tine_z[-1] + p.tine_height
        thickness = thickness_for(p, height)
    # Fins left out are named by their distance from this end of the face.
    face_start = frame.along_min
    frame = replace(frame, along_min=low, along_max=high)
    positions = positions_for(p, frame, thickness)

    s_from, s_to = foot_span(p, frame, height)
    # Fins moved along the face by hand; the neighbours have to stay clear.
    starts = {number: t0 + shifts.get(number, 0.0) for number, t0 in enumerate(positions, 1)}
    standing = sorted((t0, number) for number, t0 in starts.items() if number not in left_out)
    for (first, one), (second, other) in zip(standing, standing[1:]):
        if second - first < thickness + d.FOOT_CLEARANCE - d.TOLERANCE:
            raise FinError(translate("FinSnap", "fins %d and %d stand %.2f mm apart, closer than %.2f mm")
                           % (one, other, second - first, thickness + d.FOOT_CLEARANCE))
    half_foot = foot_half_width_for(p, (s_to - s_from) / 2, thickness, [t0 for t0, _ in standing])
    room = frame.face_top_z - frame.bed_z - d.FACE_TOP_MARGIN

    bodies = []
    all_tines = []
    dropped = []
    pieces = []
    built = []
    # Tines over the gap between two faces in one plane are named as over a recess.
    gap_heights = set(gap_z)
    fins_left_out = []
    fin_heights = []
    numbers = []
    for number, t0 in starts.items():
        if number in left_out:
            continue
        # A fin height set by hand for this fin alone: tines above it are left out.
        own = heights.get(number)
        if own is not None and own > room + d.TOLERANCE:
            raise FinError(translate("FinSnap", "fin %d is %.2f mm high, above the face (%.2f mm)")
                           % (number, own, room))
        candidate_z = [z for z in tine_z if own is None or z + p.tine_height <= own + d.TOLERANCE]
        if not candidate_z:
            raise FinError(translate("FinSnap", "fin %d is lower than its first tine") % number)
        start = tine_start(p, t0, thickness)
        # A tine wholly or partly over a recess or a hole in the face would hang
        # free there; it is left out, and a fin without any tine left with it.
        on_face = [contact_share(frame, support, start, p, z) >= d.TINE_MIN_CONTACT - d.TOLERANCE
                   for z in candidate_z]
        kept_z = [z for z, whole in zip(candidate_z, on_face) if whole]
        if not kept_z:
            fins_left_out.append(t0 + thickness / 2 - face_start)
            continue
        gap_heights.update(z for z, whole in zip(candidate_z, on_face) if not whole)
        # An automatic fin ends at its highest tine left, so no part of it
        # stands above the last contact with the face.
        if own is not None:
            fin_height = own
        else:
            fin_height = p.fin_height if p.fin_height > 0 else kept_z[-1] + p.tine_height
        body, tines = one_fin(p, frame, t0, fin_height, thickness, half_foot, candidate_z)
        kept = [tine for tine, whole in zip(tines, on_face) if whole]
        dropped += [tine for tine, whole in zip(tines, on_face) if not whole]
        fin_heights.append(fin_height)
        built.append(t0)
        numbers.append(number)
        bodies.append(body)
        all_tines.extend(kept)
        # One general fuse instead of one tine after the other: the lowest tine
        # sits on the top of the foot, where foot, flank and tine share an edge,
        # and fusing them pairwise fails on that edge.
        pieces.append(body.multiFuse(kept).removeSplitter())
    if all(number in left_out for number in range(1, len(positions) + 1)):
        error = FinError(translate("FinSnap", "every fin is removed; delete the fins instead, or bring them back"))
        # The caller compares it with the count the fins were removed from.
        error.planned = len(positions)
        raise error
    if not built:
        raise FinError(translate("FinSnap", "no tine finds the face; it has a recess or hole at every tine"))

    fins = Part.makeCompound(pieces)
    check(p, part, fins, bodies)

    warnings = []
    if gap_heights:
        warnings.append(translate("FinSnap", "tines at %s mm above the bed left out: a recess or hole in the "
                                  "face lies under them") % _mm_list(gap_heights))
    if fins_left_out:
        warnings.append(translate("FinSnap", "fins at %s mm from the end of the face left out: none of their "
                                  "tines lies wholly on the face") % _mm_list(fins_left_out))
    if narrow_heights:
        warnings.append(translate("FinSnap", "tines at %s mm above the bed left out: the face is narrower "
                                  "there than the fin") % _mm_list(narrow_heights))
    angle = math.degrees(math.acos(min(1.0, -frame.n_z)))
    if not d.FACE_ANGLE_MIN <= angle <= d.FACE_ANGLE_MAX:
        warnings.append(translate("FinSnap", "the face is inclined %.0f degrees against the bed, outside "
                                  "%.0f to %.0f") % (angle, d.FACE_ANGLE_MIN, d.FACE_ANGLE_MAX))
    tine_length = p.gap / frame.n_out
    if tine_length < d.TINE_MIN_LENGTH_BEADS * p.bead_width:
        warnings.append(translate("FinSnap", "tines are %.2f mm long, shorter than %.2f beads; the slicer "
                                  "may not print them to the face") % (tine_length, d.TINE_MIN_LENGTH_BEADS))

    return FinResult(fins=fins, bodies=bodies, tines=all_tines, height=max(fin_heights),
                     thickness=thickness, tine_z=tine_z, positions=built,
                     foot_half_width=half_foot, warnings=warnings, carried=support.Faces,
                     numbers=numbers, planned=len(positions),
                     dropped=dropped, starts={n: starts[n] for n in numbers}, along=frame.along,
                     heights=dict(zip(numbers, fin_heights)))


def merged(part, *fin_shapes):
    """Part and fins as one body, for the connected mode."""
    result = part
    for shape in fin_shapes:
        result = result.fuse(shape)
    return result.removeSplitter()


def opposite_face(part, face):
    """The face of `part` that leans the other way, for a counter fin, or None.

    Of the faces that lean over the bed in the opposite direction to `face`,
    the largest one is taken: that is the side the part could tip towards.
    """
    out = frame_of(part, face).out
    best = None
    for candidate in part.Faces:
        try:
            other = frame_of(part, candidate)
        except FinError:
            continue
        if other.out.dot(out) < -d.OPPOSITE_DIRECTION and (best is None or candidate.Area > best.Area):
            best = candidate
    return best


def best_face(shape, p):
    """Number (from 0) of the face of `shape` that takes fins best: of the planar
    faces leaning over the bed, the largest one the fins can be built under.

    INPUTS this has to withstand:
      part standing on an edge              ->  its largest leaning face that takes fins
      largest leaning face refuses fins
        (fins would run into the part)      ->  the next largest that takes them
      no face leans, or none takes fins     ->  FinError
    """
    leaning = []
    for number, face in enumerate(shape.Faces):
        try:
            frame_of(shape, face)
        except FinError:
            continue
        leaning.append((face.Area, number))
    for _, number in sorted(leaning, reverse=True):
        try:
            build(shape, shape.Faces[number], p)
        except FinError:
            continue
        return number
    raise FinError(translate("FinSnap", "no face of the part leans over the bed and takes fins"))


def stand_for_face(shape, number, p, angle_deg):
    """Stand `shape` so that face `number` leans over the bed by angle_deg and
    takes fins: (placement change, edge it stands on).

    The face is laid onto the bed and the part turned about one of its straight
    edges, the longest first, so it stands on the longest edge it can.

    INPUTS this has to withstand:
      planar face with straight edges       ->  stood on its longest edge that works
      longest edge does not carry the part
        or the fins do not fit there        ->  the next longest edge
      face without a straight edge, or none
        works                               ->  FinError
    """
    face = shape.Faces[number]
    straight = [edge for edge in face.Edges
                if abs(edge.Length - (edge.Vertexes[-1].Point - edge.Vertexes[0].Point).Length) < d.TOLERANCE]
    for edge in sorted(straight, key=lambda candidate: -candidate.Length):
        try:
            change = orient.stand(shape, edge, angle_deg, face)
            standing = moved(shape, change)
            build(standing, standing.Faces[number], p)
        except (orient.OrientError, FinError):
            continue
        return change, edge
    raise FinError(translate("FinSnap", "the part cannot stand so that this face takes fins"))


# How Quick fins stands a part: the placement change, the face (number from 0)
# the fins go under, and the edge or the two faces the part stands on, for the
# side view.
QuickPlan = namedtuple("QuickPlan", "change number edge beside")


def quick_plan(shape, edges, faces, p, angle_deg):
    """How to stand `shape` for Quick fins and which face takes the fins.

    edges and faces are the selected elements of `shape` as (element, number
    from 0), faces in the order selected: the first face takes the fins, a
    second one is what the part rests on.

    SELECTIONS this has to withstand:
      one edge                              ->  stood on it: angle_deg on the bed, or the
                                                right angle of its faces; fins under the
                                                largest leaning face that takes them
      one edge off the bed, faces not at a
        right angle                         ->  FinError pointing to Stand on edge
      one planar face                       ->  it leans angle_deg over the bed, on its
                                                longest edge that works; fins under it
      one rounded face (fillet)             ->  the part rests on it; fins under the
                                                largest leaning face
      one chamfer, wide or narrow           ->  as a rounded face: the part rests on it
      a face and one of its edges           ->  stood on that edge, the face leaning
                                                angle_deg; fins under it
      a face and an edge of another face    ->  OrientError from stand()
      a face, then a chamfer or fillet
        beside it, or any rounded face      ->  the part rests on the second; fins under
                                                the first
      two faces apart (beside a fillet)     ->  the part rests on what joins them; fins
                                                under the largest leaning face
      fins that do not fit under the face
        chosen                              ->  FinError
      anything else                         ->  FinError
    """
    if len(edges) == 1 and not faces:
        edge = edges[0][0]
        if not orient.on_bed(shape, edge) and orient.right_angle_faces(shape, edge) is None:
            raise FinError(translate("FinSnap", "This edge does not lie on the bed, and its faces do not meet at a "
                                                "right angle. Use Stand on edge with the edge and the face that "
                                                "is to lie on the bed, then Add fins."))
        angle = angle_deg if orient.on_bed(shape, edge) else orient.RIGHT_ANGLE_TILT
        change = orient.stand(shape, edge, angle)
        return QuickPlan(change, best_face(moved(shape, change), p), edge, ())
    if not edges and len(faces) == 1:
        face, number = faces[0]
        if face.findPlane() is None or is_chamfer(shape, face):
            change = orient.lay_flat(shape, face)
            return QuickPlan(change, best_face(moved(shape, change), p), None, ())
        change, edge = stand_for_face(shape, number, p, angle_deg)
        return QuickPlan(change, number, edge, ())
    if len(edges) == 1 and len(faces) == 1:
        (edge, _), (face, number) = edges[0], faces[0]
        # stand() refuses an edge of another face itself.
        change = orient.stand(shape, edge, angle_deg, face)
        return _checked(shape, QuickPlan(change, number, edge, ()), p)
    if not edges and len(faces) == 2:
        (first, number), (second, _) = faces
        beside = any(edge.isSame(other) for edge in first.Edges for other in second.Edges)
        if beside or second.findPlane() is None:
            change = orient.lay_flat(shape, second)
            return _checked(shape, QuickPlan(change, number, None, ()), p)
        change = orient.rest_between(shape, first, second)
        return QuickPlan(change, best_face(moved(shape, change), p), None, (first, second))
    raise FinError(translate("FinSnap", "Select an edge or a face, a face and the edge or the chamfer or fillet "
                                        "it is to stand on, or the two faces beside a fillet."))


def is_chamfer(shape, face):
    """Whether planar `face` sits between two planar faces of `shape` like a
    chamfer: its normal turned part of the way from one neighbour's normal to
    the other's, whatever the angle or the two widths of the chamfer.

    INPUTS this has to withstand:
      chamfer on the edge of a box, equal or
        unequal widths, wide or narrow      ->  True
      chamfer at another angle than 45      ->  True
      side of a box                         ->  False: no two neighbours with its
                                                normal between theirs
      side of an octagon prism              ->  True: it lies between its neighbours
                                                too; to put fins under it, select it
                                                with one of its edges
      rounded face                          ->  False
    """
    if face.findPlane() is None:
        return False
    normal = middle_normal(face)
    beside = [middle_normal(other) for other in shape.Faces
              if not other.isSame(face) and other.findPlane() is not None
              and any(edge.isSame(mine) for edge in other.Edges for mine in face.Edges)]
    for i, first in enumerate(beside):
        for second in beside[i + 1:]:
            apart = first.getAngle(second)
            # Between them: in their plane, and the two angles to it adding up
            # to the angle between them, neither of them zero.
            in_between = abs(first.getAngle(normal) + normal.getAngle(second) - apart) < d.TOLERANCE
            if d.TOLERANCE < apart < math.pi - d.TOLERANCE and in_between \
                    and min(first.getAngle(normal), second.getAngle(normal)) > d.TOLERANCE:
                return True
    return False


def _checked(shape, plan, p):
    """The plan, once the fins fit under its face; FinError naming why if not."""
    standing = moved(shape, plan.change)
    try:
        build(standing, standing.Faces[plan.number], p)
    except FinError as error:
        raise FinError(translate("FinSnap", "the fins do not fit under the selected face standing this way: %s")
                       % error)
    return plan
