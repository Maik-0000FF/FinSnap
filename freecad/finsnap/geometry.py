"""Fin geometry for one supported face.

The part stands tilted on the bed. A planar face of it leans outward over the
bed (its normal points down and to the side). Fins stand under that face: each
fin is a vertical wall whose inner edge, the flank, runs parallel to the face at
the gap distance. Horizontal tines reach across the gap and end exactly on the
face. A thin foot on the bed holds the fin down.

LOCAL FRAME of a face: `out` is the horizontal direction the face leans
towards, `along` runs horizontally along the face, z is up. A point is
t * along + s * out + z * Z. The face is the plane n . P = c with
n = n_out * out + n_z * Z, so at height z it lies at
    s_face(z) = (c - n_z * z) / n_out
and the flank, offset by the gap along n, at
    s_flank(z) = (c + gap - n_z * z) / n_out.
The fin occupies s >= s_flank(z); the part lies at smaller s.

INPUTS this has to withstand (build()):
  inclined planar face, part standing on the bed  ->  FinResult
  face not planar                       ->  FinError
  face vertical or flat (no lean)       ->  FinError: nothing to support
  face leaning upward (normal up)       ->  FinError: it is not an overhang
  face shorter along its edge than one
    fin plus both insets                ->  FinError
  corners: face shorter than a fin plus
    FOOT_CLEARANCE                      ->  FinError
  corners: fins centred on the face
    ends, half of each tine on the face ->  FinResult
  corners at a sharp edge               ->  tines end in the plane of the face
  corners at a chamfer                  ->  tines also touch the chamfer
  no tine fits below the top of the face ->  FinError
  face narrower than the fin at some
    tines (side of a frustum)           ->  those tines left out, warning
  face narrower than the fin at every
    tine                                ->  FinError
  fixed tine count, some tines miss     ->  FinError
  face ending above the bed             ->  no tines below it
  manual fin_height below the first tine ->  FinError
  fins standing closer than they are
    thick plus FOOT_CLEARANCE           ->  FinError: they would collide
  fin collides with other geometry of
    the part (closer than the gap)      ->  FinError naming the distance
  tine does not reach the face          ->  FinError
  fin overlaps the part (separate mode) ->  FinError
  tine shorter than TINE_MIN_LENGTH_BEADS
    beads                               ->  warning in FinResult, no error
  face inclined outside FACE_ANGLE_MIN
    to FACE_ANGLE_MAX                    ->  warning in FinResult, no error
"""

import math
from dataclasses import dataclass, field, replace

import FreeCAD as App
import Part

from . import defaults as d
from .i18n import translate

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


def frame_of(part, face):
    if face.findPlane() is None:
        raise FinError(translate("FinSnap", "the selected face is not planar"))
    u0, u1, v0, v1 = face.ParameterRange
    n = face.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
    horizontal = V(n.x, n.y, 0)
    if n.z > -d.MIN_NORMAL_COMPONENT:
        raise FinError(translate("FinSnap", "the selected face does not lean over the bed"))
    if horizontal.Length < d.MIN_NORMAL_COMPONENT:
        raise FinError(translate("FinSnap", "the selected face is flat; it rests on the bed or needs regular support"))

    out = horizontal.normalize()
    along = UP.cross(out)
    ts = [v.Point.dot(along) for v in face.Vertexes]
    return Frame(out=out, along=along, n_out=n.dot(out), n_z=n.z,
                 c=n.dot(face.Vertexes[0].Point), bed_z=part.BoundBox.ZMin,
                 along_min=min(ts), along_max=max(ts), face_top_z=face.BoundBox.ZMax,
                 face_bottom_z=face.BoundBox.ZMin)


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
    centred on both corners."""
    if p.placement == d.PLACEMENT_CORNERS:
        return thickness + d.FOOT_CLEARANCE
    return thickness + 2 * p.end_inset


def tines_on_face(face, frame, tine_z, p, width):
    """The longest run of consecutive tines that all meet the face over at
    least `width`, and the stretch along the face they share.

    A face that narrows, like the side of a frustum standing on a corner, is
    narrower at some tines than a fin is thick; those tines are left out.
    Returns (tine heights, first, last); raises if no tine has room.
    """
    extents = [_extent_at(face, frame, z, p) for z in tine_z]
    best = None
    for start in range(len(tine_z)):
        low, high = frame.along_min, frame.along_max
        for end in range(start, len(tine_z)):
            if extents[end] is None:
                break
            low, high = max(low, extents[end][0]), min(high, extents[end][1])
            if high - low < width - d.TOLERANCE:
                break
            if best is None or end + 1 - start > len(best[0]):
                best = (tine_z[start:end + 1], low, high)
    if best is None:
        raise FinError(translate("FinSnap", "the face is narrower than the %.2f mm a fin needs at every tine")
                       % width)
    return best


def thickness_for(p, height):
    if p.fin_thickness > 0:
        return p.fin_thickness
    beads = max(d.FIN_MIN_BEADS, math.ceil(height * d.FIN_THICKNESS_RATIO / p.bead_width))
    return beads * p.bead_width


def positions_for(p, frame, thickness):
    """Start of each fin along the face."""
    if p.placement == d.PLACEMENT_CORNERS:
        positions = [frame.along_min - thickness / 2, frame.along_max - thickness / 2]
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
    s_from = frame.s_flank(top, p.gap)
    s_to = frame.s_flank(frame.bed_z + height, p.gap) + p.fin_plateau + p.foot_overhang
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


def one_fin(p, frame, t0, height, thickness, half_foot, tine_z):
    """A fin without tines, and its tines, still untrimmed by the part."""
    zb = frame.bed_z
    s_bottom = frame.s_flank(zb, p.gap)
    s_top = frame.s_flank(zb + height, p.gap)
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
    t_tine = t0 + (thickness - p.tine_width) / 2
    for z in tine_z:
        bottom = zb + z
        top = bottom + p.tine_height
        s_into_part = frame.s_face(bottom) - d.TINE_INTO_PART
        # The fin edge furthest out along the tine: the flank at its top, or the
        # vertical inner end of the foot for a tine below the top of the foot.
        # Measured from there, a tine always reaches into the fin.
        edge = frame.s_flank(top, p.gap)
        if p.foot_height > 0 and bottom < zb + p.foot_height:
            edge = max(edge, foot_span(p, frame, height)[0])
        s_into_fin = edge + d.TINE_INTO_FIN
        tines.append(frame.section(t_tine, [(s_into_part, bottom), (s_into_fin, bottom),
                                            (s_into_fin, top), (s_into_part, top)], p.tine_width))
    return body, tines


def _behind_face(frame, tine):
    """The space behind the plane of the face, around `tine`."""
    ts = [v.Point.dot(frame.along) for v in tine.Vertexes]
    ss = [v.Point.dot(frame.out) for v in tine.Vertexes]
    zs = [v.Point.z for v in tine.Vertexes]
    low, high = min(zs), max(zs)
    far = min(ss) - d.TINE_INTO_PART
    return frame.section(min(ts) - d.TINE_INTO_PART,
                         [(far, low), (frame.s_face(low), low), (frame.s_face(high), high), (far, high)],
                         max(ts) - min(ts) + 2 * d.TINE_INTO_PART)


def trim_tine(tine, part, frame):
    """The tine cut back to the part, and behind the plane of the face only
    where it goes on to touch the part.

    A tine is drawn into the part and trimmed by it. Where the face ends below
    the tine, at a corner, nothing trims it: there it would stick out past the
    face into the air. A piece behind the plane stays only if moving it a
    little further in touches the part, as over a chamfer.
    """
    cut = tine.cut(part)
    behind = _behind_face(frame, tine)
    front = cut.cut(behind)
    probe = frame.out * -d.TINE_PROBE
    reaching = [piece for piece in cut.common(behind).Solids
                if piece.translated(probe).common(part).Volume > d.TINE_PROBE * d.TOLERANCE]
    return front.multiFuse(reaching).removeSplitter() if reaching else front


def check(p, part, fins, bodies, tines):
    if p.connection == d.CONNECTION_SEPARATE:
        overlap = fins.common(part).Volume
        if overlap > d.TOLERANCE:
            raise FinError(translate("FinSnap", "the fins overlap the part by %.4f mm3") % overlap)

    # distToShape fails on bodies that share a face, so the tines are checked
    # by their corners lying on the surface of the part.
    for number, tine in enumerate(tines, 1):
        on_surface = [v for v in tine.Vertexes if part.isInside(v.Point, d.TOLERANCE, True)]
        if len(on_surface) < 3:
            raise FinError(translate("FinSnap", "tine %d does not reach the face") % number)

    for body in bodies:
        distance = body.distToShape(part)[0]
        if distance < p.gap - d.TOLERANCE:
            raise FinError(translate("FinSnap", "a fin comes within %.3f mm of the part, closer than the gap %.3f mm")
                           % (distance, p.gap))


def build(part, face, p, tine_count=None):
    """Fins under `face` of `part`. tine_count overrides p.tine_count (counter fin)."""
    p.validate()
    frame = frame_of(part, face)
    count = p.tine_count if tine_count is None else tine_count
    all_z, height = tine_heights(p, frame, count)
    thickness = thickness_for(p, height)
    if p.tine_width > thickness:
        raise FinError(translate("FinSnap", "tines (%.2f mm) are wider than the fin (%.2f mm)")
                       % (p.tine_width, thickness))
    tine_z, low, high = tines_on_face(face, frame, all_z, p, room_for_one_fin(p, thickness))
    left_out = len(all_z) - len(tine_z)
    if left_out and count:
        raise FinError(translate("FinSnap", "only %d of %d tines meet the face") % (len(tine_z), count))
    if left_out:
        # Fewer tines make a lower and so a thinner fin; it still fits where the thicker one did.
        height = p.fin_height if p.fin_height > 0 else tine_z[-1] + p.tine_height
        thickness = thickness_for(p, height)
    frame = replace(frame, along_min=low, along_max=high)
    positions = positions_for(p, frame, thickness)

    s_from, s_to = foot_span(p, frame, height)
    half_foot = foot_half_width_for(p, (s_to - s_from) / 2, thickness, positions)

    bodies = []
    all_tines = []
    pieces = []
    for t0 in positions:
        body, tines = one_fin(p, frame, t0, height, thickness, half_foot, tine_z)
        trimmed = [trim_tine(tine, part, frame) for tine in tines]
        bodies.append(body)
        all_tines.extend(trimmed)
        # One general fuse instead of one tine after the other: the lowest tine
        # sits on the top of the foot, where foot, flank and tine share an edge,
        # and fusing them pairwise fails on that edge.
        pieces.append(body.multiFuse(trimmed).removeSplitter())

    fins = Part.makeCompound(pieces)
    check(p, part, fins, bodies, all_tines)

    warnings = []
    if left_out:
        warnings.append(translate("FinSnap", "%d tines left out where the face is narrower than the fin")
                        % left_out)
    angle = math.degrees(math.acos(min(1.0, -frame.n_z)))
    if not d.FACE_ANGLE_MIN <= angle <= d.FACE_ANGLE_MAX:
        warnings.append(translate("FinSnap", "the face is inclined %.0f degrees against the bed, outside "
                                  "%.0f to %.0f") % (angle, d.FACE_ANGLE_MIN, d.FACE_ANGLE_MAX))
    tine_length = p.gap / frame.n_out
    if tine_length < d.TINE_MIN_LENGTH_BEADS * p.bead_width:
        warnings.append(translate("FinSnap", "tines are %.2f mm long, shorter than %.2f beads; the slicer "
                                  "may not print them to the face") % (tine_length, d.TINE_MIN_LENGTH_BEADS))

    return FinResult(fins=fins, bodies=bodies, tines=all_tines, height=height,
                     thickness=thickness, tine_z=tine_z, positions=positions,
                     foot_half_width=half_foot, warnings=warnings)


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
