# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

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

ROUND SIDE: a cylinder or tube standing on its rim leans its curved side over
the bed. Its lowest line is straight, and the plane touching the side along it
stands in for the face: one fin stands in the middle under that line. Across a
tine the side falls away behind the plane by a few thousandths of a millimetre,
so a tine ends on it wherever the side lies within ROUND_SIDE_MAX_DROP of the
plane.

INPUTS this has to withstand (orient.is_round_side()):
  curved side of a cylinder or tube     ->  True
  inner side of a tube                  ->  True; frame_of() refuses it
  fillet, part of a cylinder            ->  False
  cone, planar face                     ->  False

INPUTS this has to withstand (frame_of() on a round side):
  cylinder standing on its rim          ->  frame on the plane touching its lowest
                                            line, as wide as the side stays within
                                            ROUND_SIDE_MAX_DROP of it
  cylinder upright                      ->  FinError: it does not lean
  cylinder lying on its side            ->  FinError: it rests on the bed
  inner side of a tube                  ->  FinError: it curves inward
  lowest line cut away or through a
    hole, cylinder cut at a slant       ->  the frame reaches as far as the line runs
                                            on the side; tines over a hole left out

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
  tine_clearance > 0, merged fins       ->  tines on the face, as with 0
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
  round side                            ->  one fin under its lowest line, whatever
                                            the placement; a note to give the rim
                                            more hold on the bed
"""

import itertools
import math
from collections import namedtuple
from dataclasses import dataclass, field, replace
from functools import partial

import FreeCAD as App
import Part

from . import bridge
from . import defaults as d
from . import limits
from . import orient
from . import overhang
from .i18n import QT_TRANSLATE_NOOP, translate
from .shapes import bounds, middle_normal, moved

V = App.Vector
UP = V(0, 0, 1)
DOWN = V(0, 0, -1)
# Degrees in a whole turn.
FULL_CIRCLE = 360.0
# How closely the points that measure a face along its edges follow a curve (mm).
SPAN_DEFLECTION = 0.01
# The order rims_on_axis() tries rims in: a chamfered one, then one of the
# side itself, then any other on the axis, which a part rarely stands on.
RIM_CHAMFERED, RIM_OWN, RIM_OTHER = range(3)
# Why Quick fins finds no way to stand a part: no face takes the fins, or
# the face selected takes them on no edge it can stand on.
NO_LEANING_FACE = QT_TRANSLATE_NOOP("FinSnap", "no face of the part leans over the bed and takes fins")
NO_STAND_FOR_FACE = QT_TRANSLATE_NOOP("FinSnap", "the part cannot stand so that this face takes fins")


class FinError(ValueError):
    """The fin cannot be built on this face."""


class HandEditError(FinError):
    """A change by hand the fins cannot be built with: a fin moved past or
    onto a neighbour, set above the face or below its first tine, or every fin
    removed. It is refused, and no other way of building the fins, such as
    under the selected face alone instead of over a groove, takes it back."""


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
    # The radius of the face when it is the curved side of a cylinder, its
    # plane the one touching its lowest line; 0 for a planar face.
    radius: float = 0.0

    @property
    def round_side(self):
        return self.radius > 0

    def normal(self):
        """The outward normal of the plane of the face."""
        return self.out * self.n_out + UP * self.n_z

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


# What a warning of build() is about, for the task panel to show it: the
# numbers of the fins it names, tines left out, as shapes, and whether it is
# about the face. None of them, for a warning about the part as a whole.
WarningTarget = namedtuple("WarningTarget", "fins tines on_face")


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
    # What each warning is about, a WarningTarget, in the same order.
    warning_targets: list = field(default_factory=list)
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
    # The middle of the upright outer edge of each fin built, by number.
    edges: dict = field(default_factory=dict)
    # The direction away from the part, level with the bed: the outer edges face it.
    out: App.Vector = None
    # By number, the heights of the tines of each fin built that find the face
    # (mm, from the bed), all of them, also above a height of its own.
    touching_z: dict = field(default_factory=dict)
    # Where the face starts along it (mm, as starts): fins are placed from there.
    face_start: float = 0.0
    # The radius of a round side the fin stands under, 0 under a planar face.
    # Its fin stays under the lowest line; moved by hand, the part turns instead.
    radius: float = 0.0
    # The frame the fins were built in, to draw one at another height (fin_at()).
    frame: Frame = None
    # By number, how far a fin planned over a hole was moved beside it (mm, as
    # starts); its start is planned plus its shift by hand plus this.
    moved: dict = field(default_factory=dict)


def span_along(shape, direction):
    """How far `shape` reaches along `direction` (mm), as (first, last):
    measured at points along its edges, not at its corners alone. A disc has
    one corner on its rim, half a disc two at the ends of its straight side;
    by those alone the disc would be no width at all.

    INPUTS this has to withstand:
      a face with straight edges            ->  from its corners, as they are on the edges
      a disc, one corner on its rim         ->  its diameter
      half a disc, its straight side across
        `direction`                         ->  its radius, not nothing
    """
    ts = [point.dot(direction) for edge in shape.Edges for point in edge.discretize(Deflection=SPAN_DEFLECTION)]
    return min(ts), max(ts)


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
      curved face                           ->  the face itself
    """
    if face.findPlane() is None:
        return face
    normal = middle_normal(face)
    horizontal = V(normal.x, normal.y, 0)
    if horizontal.Length < d.MIN_NORMAL_COMPONENT:
        return face
    along = UP.cross(horizontal.normalize())

    low, high = span_along(face, along)
    c = normal.dot(face.Vertexes[0].Point)
    pieces = [face]
    for other in part.Faces:
        if other.isSame(face) or other.findPlane() is None:
            continue
        in_plane = abs(normal.dot(other.Vertexes[0].Point) - c) <= d.TOLERANCE
        if middle_normal(other).dot(normal) < 1 - d.TOLERANCE or not in_plane:
            continue
        other_low, other_high = span_along(other, along)
        if other_low < high - d.TOLERANCE and other_high > low + d.TOLERANCE:
            pieces.append(other)
    return face if len(pieces) == 1 else Part.makeCompound(pieces)


class EdgeSet:
    """Edges to ask whether one of them is the same as a given edge, as
    isSame() says, with one lookup by hash instead of a comparison with each."""

    def __init__(self, edges):
        self.by_hash = {}
        for edge in edges:
            self.by_hash.setdefault(edge.hashCode(), []).append(edge)

    def __contains__(self, edge):
        return any(edge.isSame(mine) for mine in self.by_hash.get(edge.hashCode(), ()))


def rims_on_axis(shape, side):
    """The rims of `shape` the round side `side` can stand on, best first.

    A rim counts where a flat face ends in a whole circle on the axis of the
    side. One that a chamfer joins to the side, a cone touching it, comes
    first: the chamfer gives the part more hold on the bed. The rims of the
    side itself come next, then any other on the axis, the bore of a tube or
    a smaller step of a shaft. Larger rims come before smaller ones.

    INPUTS this has to withstand:
      plain cylinder                        ->  both rims of the side
      chamfer on one rim                    ->  the small rim of the chamfer first,
                                                then the plain rim
      chamfer on both rims                  ->  the small rims of the chamfers; the
                                                rims of the side end in no flat face
      tube                                  ->  its outer rims, then its inner ones,
                                                on which it cannot stand
      shaft with a smaller step on the axis ->  the rims of the side before those of
                                                the step
      circle off the axis (a hole in the
        end face beside it)                 ->  not a rim of the side
    """
    # Edges looked up by their hash, then confirmed with isSame(): the same
    # edge with the same placement, whichever way round. One lookup each, not
    # a loop over every pair; a hash two edges share still tells them apart.
    own = EdgeSet(side.Edges)
    chamfered = EdgeSet(edge for face in shape.Faces if isinstance(face.Surface, Part.Cone)
                        and any(mine in own for mine in face.Edges) for edge in face.Edges)
    found = []
    for edge in shape.Edges:
        if not orient.is_rim(edge):
            continue
        circle = edge.Curve
        flat = any(face.findPlane() is not None for face in shape.ancestorsOfType(edge, Part.Face))
        if not (orient.on_axis(circle.Center, circle.Axis, side.Surface) and flat):
            continue
        if edge in chamfered:
            rank = RIM_CHAMFERED
        elif edge in own:
            rank = RIM_OWN
        else:
            rank = RIM_OTHER
        found.append((rank, -edge.Length, len(found), edge))
    return [edge for *_, edge in sorted(found)]


def _lowest(face):
    """The direction from the axis of the round side `face` to its lowest line,
    square to the axis and pointing down the most: the side lies lowest there,
    and its normal leans furthest over the bed. Its horizontal part is `out`."""
    axis = V(face.Surface.Axis).normalize()
    n = DOWN - axis * DOWN.dot(axis)
    if n.Length < d.MIN_NORMAL_COMPONENT:
        raise FinError(translate("FinSnap", "the selected face does not lean over the bed"))
    n.normalize()
    if V(n.x, n.y, 0).Length < d.MIN_NORMAL_COMPONENT:
        raise FinError(translate("FinSnap", "the selected face is flat; it rests on the bed or needs regular support"))
    return n


def _round_frame(part, face):
    """The frame of the round side `face` on the plane touching its lowest line."""
    surface = face.Surface
    n = _lowest(face)
    lowest = surface.Center + n * surface.Radius
    u, v = surface.parameter(lowest)
    if face.normalAt(u, v).dot(n) < 0:
        raise FinError(translate("FinSnap", "the selected face curves inward; fins go under the outside of a "
                                            "cylinder or tube"))
    _, _, v0, v1 = face.ParameterRange
    line = Part.LineSegment(surface.value(u, v0), surface.value(u, v1)).toShape().common(face)
    if not line.Edges:
        raise FinError(translate("FinSnap", "the lowest line of the selected face is cut away"))

    out = V(n.x, n.y, 0).normalize()
    along = UP.cross(out)
    middle = lowest.dot(along)
    drop = min(d.ROUND_SIDE_MAX_DROP, surface.Radius)
    half_width = math.sqrt(surface.Radius ** 2 - (surface.Radius - drop) ** 2)
    line_box = bounds(line)
    return Frame(out=out, along=along, n_out=n.dot(out), n_z=n.z, c=n.dot(lowest), bed_z=bounds(part).ZMin,
                 along_min=middle - half_width, along_max=middle + half_width, face_top_z=line_box.ZMax,
                 face_bottom_z=line_box.ZMin, radius=surface.Radius)


def turn_of(face, mm):
    """The placement change that turns a part about the axis of its round side
    `face` so that the fin, which stays under the lowest line, comes to stand
    `mm` further along the side, to the right seen from outside, measured round
    it. The side itself stays where it is; what lies on it turns."""
    surface = face.Surface
    angle = math.degrees(_turn_sense(face) * mm / surface.Radius)
    return App.Placement(V(0, 0, 0), App.Rotation(V(surface.Axis), angle), surface.Center)


def _turn_sense(face):
    """1 where the part turns about the axis of its round side `face` the
    right way round as the fin moves to the right along it, seen from outside,
    -1 where the other way round."""
    axis = V(face.Surface.Axis).normalize()
    n = _lowest(face)
    along = UP.cross(V(n.x, n.y, 0).normalize())
    # The part turns the other way round than the fin moves along the side.
    return -1 if axis.cross(n).dot(along) > 0 else 1


def turn_mm(face, degrees):
    """How far round the round side `face` the fin comes to stand, as turn_of()
    takes it (mm), once the part is turned `degrees` about the axis of the
    side, the right way round."""
    return _turn_sense(face) * math.radians(degrees) * face.Surface.Radius


def side_angle(face):
    """Where round the round side `face` the fin under it stands: the angle of
    the lowest line, which the middle of its tines touches, from the zero
    direction of the side, in degrees from 0 up to 360. Turning the part the
    right way round about the axis of the side makes it smaller."""
    surface = face.Surface
    axis = V(surface.Axis).normalize()
    # Counted the right way round the axis from the zero direction, not by
    # the parameter of the side, which runs the other way round where its
    # frame is left-handed (a primitive cylinder or a pad can have one).
    zero = surface.value(0, 0) - surface.Center
    zero = zero - axis * zero.dot(axis)
    lowest = _lowest(face)
    return round_angle(math.degrees(math.atan2(axis.dot(zero.cross(lowest)), zero.dot(lowest))))


def round_angle(degrees, tolerance=d.TOLERANCE):
    """`degrees` as an angle round a circle, from 0 up to 360; closer below 360
    than `tolerance` is 0."""
    angle = degrees % FULL_CIRCLE
    return 0.0 if FULL_CIRCLE - angle < tolerance else angle


def frame_of(part, face, support=None):
    """The frame of `face`; its extent along and up is that of `support`, the
    face with the faces in its plane, if given."""
    if orient.is_round_side(face):
        return _round_frame(part, face)
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
    low, high = span_along(extent, along)
    face_box = bounds(extent)
    return Frame(out=out, along=along, n_out=n.dot(out), n_z=n.z,
                 c=n.dot(face.Vertexes[0].Point), bed_z=bounds(part).ZMin,
                 along_min=low, along_max=high, face_top_z=face_box.ZMax,
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


def _extent_at(face, frame, z, p, slices=None):
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
    tine (_extent_at(), None where it misses), is wide enough there for the
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


def room_for_one_fin(p, frame, thickness):
    """The least stretch along the face a fin needs: inside both insets, or
    for a fin on each corner, both tines and the clearance between the fins.
    Under a round side only the tine touches it; the fin stands clear of it."""
    if frame.round_side:
        return p.tine_width
    if p.placement == d.PLACEMENT_CORNERS:
        return thickness + d.FOOT_CLEARANCE + p.tine_width
    if p.placement in d.PLACEMENT_ONE_CORNER:
        return p.tine_width
    return thickness + 2 * p.end_inset


def tines_on_face(face, frame, tine_z, p, width, slices=None):
    """The longest run of consecutive tines that all meet the face over at
    least `width`, and the stretch along the face they share.

    A face that narrows, like the side of a frustum standing on a corner, is
    narrower at some tines than a fin is thick; those tines are left out. A
    height where no face lies at all, the gap between two faces in one plane,
    only leaves its own tine out; the run goes on above it.
    `slices` is the dict of _extent_at() kept for the build.
    Returns (tine heights, first, last, heights over a gap); raises if no tine
    has room.
    """
    extents = [_extent_at(face, frame, z, p, slices) for z in tine_z]
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
    if frame.round_side:
        # One fin, its tine in the middle under the lowest line, whatever the placement.
        return [(frame.along_min + frame.along_max - thickness) / 2]
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

    INPUTS this has to withstand:
      without restart                       ->  tine_heights(), its errors as they are
      restart, a face from the bed up       ->  tine_heights(), its errors as they are
      restart, a face above the bed         ->  spread from its lower edge to its top
      restart, no grid tine on that face    ->  spread over it, no error
      restart, fewer than a fixed count fit ->  those that fit, no error
      restart, no tine fits at all          ->  the error of tine_heights()
      restart, a fin height above the face  ->  the error of tine_heights()
    """
    floor = frame.face_bottom_z - frame.bed_z
    if not restart or floor <= d.TOLERANCE:
        return tine_heights(p, frame, tine_count)
    room = frame.face_top_z - frame.bed_z - d.FACE_TOP_MARGIN
    limit = p.fin_height if p.fin_height > 0 else room
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
    lies on `face`, as contact_share() finds it."""
    start = tine_start(p, t0, thickness)
    return {z for z in tine_z if contact_share(frame, face, start, p, z) >= d.TINE_MIN_CONTACT - d.TOLERANCE}


def beside_hole(frame, rests, t0, thickness, others):
    """Where along the face the fin planned to start at t0, whose tines find
    no face there, starts nearest where `rests` finds a tine of it on the
    face; None if nowhere. It keeps within the face and between its neighbours
    among the fins starting at `others`, clear of them, so the fins keep
    their order from the left; tried a fin thickness at a time, either way
    in turn.

    INPUTS this has to withstand:
      a hole under the middle of the fin     ->  the nearest start beside it, the
                                                 nearer side first
      a hole wider than the room between
        its neighbours                       ->  None: left out, as before
      a neighbour beside the hole            ->  not passed: the search ends clear
                                                 of it
      the end of the face reached            ->  that way given up, the other tried on
    """
    clear = thickness + d.FOOT_CLEARANCE
    before = [other for other in others if other < t0 - d.TOLERANCE]
    after = [other for other in others if other > t0 + d.TOLERANCE]
    low = max([frame.along_min] + [other + clear for other in before])
    high = min([frame.along_max - thickness] + [other - clear for other in after])
    steps = int(max(t0 - low, high - t0) / thickness) + 1
    for step in range(1, steps + 1):
        for t in (t0 - step * thickness, t0 + step * thickness):
            if low - d.TOLERANCE <= t <= high + d.TOLERANCE and rests(t):
                return t
    return None


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


def one_fin(p, frame, t0, height, thickness, half_foot, tine_z):
    """A fin without tines, its tines, which end on the face, and the middle
    of the upright outer edge of its blade, where the handles go."""
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
    outer_middle = frame.point(t0 + thickness / 2, s_out, zb + height / 2)

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
        s_end_bottom = frame.s_flank(bottom, p.clearance)
        s_end_top = frame.s_flank(top, p.clearance)
        tines.append(frame.section(t_tine, [(s_end_bottom, bottom), (s_into_fin, bottom),
                                            (s_into_fin, top), (s_end_top, top)], p.tine_width))
    return body, tines, outer_middle


def fin_at(p, result, number, height):
    """Fin `number` of `result` as it would be `height` high (mm, from the
    bed), with the tines that find the face up to that height, as a list of
    shapes: where it stands and how thick it is as built, unchecked, to show
    where a fin cannot be built.

    INPUTS this has to withstand:
      height between its tines              ->  the fin, ending above the last tine below
      height above the face                 ->  the fin as high, its flank on along the face
      height below its first tine           ->  the fin without tines
      height at or below the top of its
        foot, down to 0                     ->  the fin as high as its foot: lower, its
                                                outline would cross itself
      no foot, height above 0               ->  the fin as high
    """
    height = max(height, p.foot_height)
    index = result.numbers.index(number)
    tine_z = [z for z in result.touching_z.get(number, []) if z + p.tine_height <= height + d.TOLERANCE]
    body, tines, _ = one_fin(p, result.frame, result.positions[index], height, result.thickness,
                             result.foot_half_width, tine_z)
    return [body] + tines


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
    selected face alone, as they did before pieces were carried along. A
    change by hand that does not fit over the groove is refused instead: a
    drag never changes which faces the fins carry.
    """
    p.validate()
    shifts, heights = shifts or {}, heights or {}
    support = support_of(part, face)
    if support is face:
        return _build(part, face, face, p, tine_count, left_out, shifts, heights)
    try:
        return _build(part, face, support, p, tine_count, left_out, shifts, heights)
    except HandEditError:
        raise
    except FinError as error:
        reason = str(error)
    alone = _build(part, face, face, p, tine_count, left_out, shifts, heights)
    alone.warnings.append(translate("FinSnap", "fins under the selected face alone, not reaching over the "
                                               "groove: %s") % reason)
    alone.warning_targets.append(WarningTarget([], [], True))
    return alone


# One fin as planned: where it starts, how high it is, the heights its tines
# are tried at, which of them rest on the face, and every height at which a
# tine there would.
PlannedFin = namedtuple("PlannedFin", "number t0 height candidate_z on_face touching")
# The fins of a face as planned, before any is built.
FacePlan = namedtuple("FacePlan", "frame height thickness tine_z gap_z narrow_heights positions face_start "
                                  "starts half_foot fins moved fins_left_out")


def _plan(frame, support, p, all_z, face_height, reach, count, restart, left_out, shifts, heights, slices):
    """The fins of the face planned for a fin height of at least `reach`,
    from which their thickness and foot follow. With `restart`, each fin is
    tried on its own tine grid (restarted_tines()), at its planned place and
    at every place it might move to beside a hole; without, on `all_z`.
    `slices` is the dict of _extent_at() kept for the build."""
    height = max(face_height, reach)
    thickness = thickness_for(p, height)
    if p.tine_width > thickness:
        raise FinError(translate("FinSnap", "tines (%.2f mm) are wider than the fin (%.2f mm)")
                       % (p.tine_width, thickness))
    tine_z, low, high, gap_z = tines_on_face(support, frame, all_z, p, room_for_one_fin(p, frame, thickness),
                                             slices)
    # Also with a fixed tine count: tines the narrow face cannot take are left
    # out and named, as over a recess, rather than refusing the whole fin.
    narrow_heights = set(all_z) - set(tine_z) - set(gap_z)
    if narrow_heights:
        # Fewer tines make a lower and so a thinner fin; it still fits where the thicker one did.
        height = max(p.fin_height if p.fin_height > 0 else tine_z[-1] + p.tine_height, reach)
        thickness = thickness_for(p, height)
    # Fins left out are named by their distance from this end of the face.
    face_start = frame.along_min
    frame = replace(frame, along_min=low, along_max=high)
    positions = positions_for(p, frame, thickness)
    if frame.round_side:
        # The fin stays under the lowest line, and its shift is how far the
        # part was turned (turn_of()); measured from the middle, the place on
        # the face is that shift.
        face_start = (low + high) / 2

    def refused(message, kind=FinError):
        """A FinError, or `kind`, that says how many fins the face is planned
        for: with another count, changes by hand name other fins, and the
        caller drops them instead of refusing."""
        error = kind(message)
        error.planned = len(positions)
        return error

    s_from, s_to = foot_span(p, frame, height)
    # Fins moved along the face by hand stay clear of their neighbours and in
    # their order: the numbers count from the left, also after a move.
    starts = {number: t0 + shifts.get(number, 0.0) for number, t0 in enumerate(positions, 1)}
    standing = [(starts[number], number) for number in sorted(starts) if number not in left_out]
    for (first, one), (second, other) in zip(standing, standing[1:]):
        if second < first:
            raise refused(translate("FinSnap", "fin %d would pass fin %d; a fin stays between its neighbours")
                           % (one, other), HandEditError)
        if second - first < thickness + d.FOOT_CLEARANCE - d.TOLERANCE:
            raise refused(translate("FinSnap", "fins %d and %d stand %.2f mm apart, closer than %.2f mm")
                           % (one, other, second - first, thickness + d.FOOT_CLEARANCE), HandEditError)
    if all(number in left_out for number in range(1, len(positions) + 1)):
        raise refused(translate("FinSnap", "every fin is removed; delete the fins instead, or bring them back"),
                      HandEditError)
    half_foot = foot_half_width_for(p, (s_to - s_from) / 2, thickness, [t0 for t0, _ in standing])
    room = frame.face_top_z - frame.bed_z - d.FACE_TOP_MARGIN

    def tines_at(t, own):
        """The heights the tines of a fin starting at t are planned at, those
        of them below a height of its own, and those of its own grid left out
        where the face is narrower than the fin (wide_enough())."""
        own_z = None
        if restart:
            own_z = restarted_tines(p, frame, support, t, thickness,
                                    p.fin_height if p.fin_height > 0 else room, count)
        if own_z is None:
            planned_z, narrow = tine_z, []
        else:
            wide = [wide_enough(_extent_at(support, frame, z, p, slices), p, t, thickness) for z in own_z]
            planned_z = [z for z, fits in zip(own_z, wide) if fits]
            narrow = [z for z, fits in zip(own_z, wide) if not fits]
        return planned_z, [z for z in planned_z if own is None or z + p.tine_height <= own + d.TOLERANCE], narrow

    def rests_at(t, own):
        """Whether a tine of the fin starting at t lies on the face."""
        planned_z, candidate_z, _ = tines_at(t, own)
        return any(z in candidate_z for z in touching_at(frame, support, p, planned_z, t, thickness))

    fins = []
    # Fins planned over a hole and moved beside it, as (number, mm moved).
    moved_fins = []
    fins_left_out = []
    for number, t0 in starts.items():
        if number in left_out:
            continue
        if frame.round_side:
            t0 = positions[number - 1]
        # A fin height set by hand for this fin alone: tines above it are left out.
        own = heights.get(number)
        if own is not None and own > room + d.TOLERANCE:
            raise refused(translate("FinSnap", "fin %d is %.2f mm high, above the face (%.2f mm)")
                           % (number, own, room), HandEditError)
        planned_z, candidate_z, narrow = tines_at(t0, own)
        if own is not None and not candidate_z:
            raise refused(translate("FinSnap", "fin %d is lower than its first tine") % number, HandEditError)
        # A tine wholly or partly over a recess or a hole in the face would hang
        # free there; it is left out, and a fin without any tine left with it.
        # Tried at every height planned, also above a height of its own: those
        # are the heights the fin can be given with a tine on top.
        touching = touching_at(frame, support, p, planned_z, t0, thickness)
        if not any(z in touching for z in candidate_z) and not frame.round_side and number not in shifts:
            # Planned over a hole, the fin moves along the face to the nearest
            # place its tines rest; one moved by hand stays where it was put.
            others = [starts[n] for n in starts if n != number and n not in left_out]
            moved_to = beside_hole(frame, partial(rests_at, own=own), t0, thickness, others)
            if moved_to is not None:
                moved_fins.append((number, moved_to - t0))
                t0 = starts[number] = moved_to
                planned_z, candidate_z, narrow = tines_at(t0, own)
                touching = touching_at(frame, support, p, planned_z, t0, thickness)
        on_face = [z in touching for z in candidate_z]
        # Tines of its own grid left out where the face is too narrow are named
        # with those of the face, as far as the fin reaches up to them.
        narrow_heights.update(z for z in narrow if own is None or z + p.tine_height <= own + d.TOLERANCE)
        kept_z = [z for z, whole in zip(candidate_z, on_face) if whole]
        if not kept_z:
            fins_left_out.append(t0 + thickness / 2 - face_start)
            continue
        # An automatic fin ends at its highest tine left, so no part of it
        # stands above the last contact with the face.
        if own is not None:
            fin_height = own
        else:
            fin_height = p.fin_height if p.fin_height > 0 else kept_z[-1] + p.tine_height
        fins.append(PlannedFin(number, t0, fin_height, candidate_z, on_face, sorted(touching)))
    if not fins:
        raise refused(translate("FinSnap", "no tine finds the face; it has a recess or hole at every tine"))
    return FacePlan(frame, height, thickness, tine_z, gap_z, narrow_heights, positions, face_start,
                    starts, half_foot, fins, moved_fins, fins_left_out)


def _build(part, face, support, p, tine_count, left_out, shifts, heights):
    frame = frame_of(part, face, support)
    # The slices of the face at the height of a tine, kept for every plan of this build.
    slices = {}
    count = p.tine_count if tine_count is None else tine_count
    restart = p.tine_restart and not frame.round_side
    all_z, face_height = face_tines(p, frame, count, restart)
    plan = _plan(frame, support, p, all_z, face_height, 0.0, count, restart, left_out, shifts, heights,
                 slices)
    # With the restart a fin can reach above the tines of the face as a
    # whole, up to the top of the stretch it stands on; the fins are planned
    # again, as thick and with as large a foot as the highest of them needs.
    # The height planned for only grows, each time to that of a fin, and no
    # fin is higher than the face, so this ends. A height set by hand counts
    # too: it ends on a tine of its fin, which may lie above those of the face.
    while restart:
        reach = max(fin.height for fin in plan.fins)
        if reach <= plan.height + d.TOLERANCE:
            break
        plan = _plan(frame, support, p, all_z, face_height, reach, count, restart, left_out, shifts,
                     heights, slices)
    frame, thickness = plan.frame, plan.thickness

    bodies = []
    all_tines = []
    dropped = []
    # The fins with tines left out over a recess, by number.
    gapped = []
    pieces = []
    # Tines over the gap between two faces in one plane are named as over a recess.
    gap_heights = set(plan.gap_z)
    edges = []
    for fin in plan.fins:
        gap_heights.update(z for z, whole in zip(fin.candidate_z, fin.on_face) if not whole)
        body, tines, edge = one_fin(p, frame, fin.t0, fin.height, thickness, plan.half_foot, fin.candidate_z)
        kept = [tine for tine, whole in zip(tines, fin.on_face) if whole]
        dropped += [tine for tine, whole in zip(tines, fin.on_face) if not whole]
        if not all(fin.on_face):
            gapped.append(fin.number)
        edges.append(edge)
        bodies.append(body)
        all_tines.extend(kept)
        # One general fuse instead of one tine after the other: the lowest tine
        # sits on the top of the foot, where foot, flank and tine share an edge,
        # and fusing them pairwise fails on that edge.
        pieces.append(body.multiFuse(kept).removeSplitter())

    fins = Part.makeCompound(pieces)
    check(p, part, fins, bodies)

    # Each warning with what it is about, as a WarningTarget, in the same order.
    warnings, targets = [], []
    if gap_heights:
        warnings.append(translate("FinSnap", "tines at %s mm above the bed left out: a recess or hole in the "
                                  "face lies under them") % _mm_list(gap_heights))
        targets.append(WarningTarget(gapped, dropped, False))
    if plan.moved:
        warnings.append(translate("FinSnap", "fins moved along the face to where their tines rest, beside a "
                                  "hole or recess under their planned place: %s") % ", ".join(
            translate("FinSnap", "fin %d by %.2f mm") % (number, mm) for number, mm in plan.moved))
        targets.append(WarningTarget([number for number, _ in plan.moved], [], False))
    if plan.fins_left_out:
        warnings.append(translate("FinSnap", "fins at %s mm from the end of the face left out: none of their "
                                  "tines lies wholly on the face") % _mm_list(plan.fins_left_out))
        targets.append(WarningTarget([], [], True))
    if plan.narrow_heights:
        warnings.append(translate("FinSnap", "tines at %s mm above the bed left out: the face is narrower "
                                  "there than the fin") % _mm_list(plan.narrow_heights))
        targets.append(WarningTarget([], [], True))
    angle = math.degrees(math.acos(min(1.0, -frame.n_z)))
    if not d.FACE_ANGLE_MIN <= angle <= d.FACE_ANGLE_MAX:
        warnings.append(translate("FinSnap", "the face is inclined %.0f degrees against the bed, outside "
                                  "%.0f to %.0f") % (angle, d.FACE_ANGLE_MIN, d.FACE_ANGLE_MAX))
        targets.append(WarningTarget([], [], True))
    tine_length = p.gap / frame.n_out
    if tine_length < d.TINE_MIN_LENGTH_BEADS * p.bead_width:
        warnings.append(translate("FinSnap", "tines are %.2f mm long, shorter than %.2f beads; the slicer "
                                  "may not print them to the face") % (tine_length, d.TINE_MIN_LENGTH_BEADS))
        targets.append(WarningTarget([fin.number for fin in plan.fins], [], False))
    if frame.round_side:
        warnings.append(translate("FinSnap", "the part stands on one point of its rim: a chamfer on the rim and "
                                  "a brim in the slicer give it more hold on the bed"))
        targets.append(WarningTarget([], [], False))

    numbers = [fin.number for fin in plan.fins]
    fin_heights = [fin.height for fin in plan.fins]
    return FinResult(fins=fins, bodies=bodies, tines=all_tines, height=max(fin_heights),
                     thickness=thickness, tine_z=plan.tine_z, positions=[fin.t0 for fin in plan.fins],
                     foot_half_width=plan.half_foot, warnings=warnings, warning_targets=targets,
                     carried=support.Faces,
                     numbers=numbers, planned=len(plan.positions),
                     dropped=dropped, starts={n: plan.starts[n] for n in numbers}, along=frame.along,
                     out=frame.out, heights=dict(zip(numbers, fin_heights)), edges=dict(zip(numbers, edges)),
                     touching_z={fin.number: fin.touching for fin in plan.fins},
                     face_start=plan.face_start, radius=frame.radius, frame=frame, moved=dict(plan.moved))


def merged(part, *fin_shapes):
    """Part and fins as one body, for the connected mode."""
    result = part
    for shape in fin_shapes:
        result = result.fuse(shape)
    return result.removeSplitter()


def opposite_faces(part, face):
    """The faces of `part` that lean the other way, for a counter fin, the
    largest first: the side the part could tip towards. Whether a counter fin
    can be built under one is the caller's to try, on the face as it names
    it. The side of a cylinder or tube is passed over: its fin stays under its
    lowest line and moves only by turning the part, which the main fin does.
    """
    out = frame_of(part, face).out
    leaning = []
    for number, candidate in enumerate(part.Faces):
        if orient.is_round_side(candidate):
            continue
        try:
            other = frame_of(part, candidate)
        except FinError:
            continue
        if other.out.dot(out) < -d.OPPOSITE_DIRECTION:
            leaning.append((candidate.Area, number))
    return [part.Faces[number] for _, number in sorted(leaning, reverse=True)]


def best_face(shape, p, tried=()):
    """Number (from 0) of the face of `shape` that takes fins best: of the planar
    faces leaning over the bed, the largest one the fins can be built under.
    Faces numbered in `tried` were tried before and are passed over.

    INPUTS this has to withstand:
      part standing on an edge              ->  its largest leaning face that takes fins
      largest leaning face refuses fins
        (fins would run into the part)      ->  the next largest that takes them
      no face leans, or none takes fins     ->  FinError
    """
    return next(_or_refused(faces_taking_fins(shape, p, tried), NO_LEANING_FACE))


def faces_taking_fins(shape, p, tried=()):
    """The numbers (from 0) of the planar faces of `shape` leaning over the bed
    that the fins can be built under, the largest first, passing over those
    numbered in `tried`. Each is built to see that the fins fit, one at a
    time: best_face() takes the first and builds no further, Quick fins takes
    them all, to offer each."""
    leaning = []
    for number, face in enumerate(shape.Faces):
        try:
            frame_of(shape, face)
        except FinError:
            continue
        leaning.append((face.Area, number))
    for _, number in sorted(leaning, reverse=True):
        if number not in tried and first_taking_fins(shape, [number], p) is not None:
            yield number


def _or_refused(found, why):
    """What the iterator `found` yields, one at a time; FinError with `why`,
    translated, if it yields nothing at all."""
    empty = True
    for item in found:
        empty = False
        yield item
    if empty:
        raise FinError(translate("FinSnap", why))


def first_taking_fins(shape, numbers, p, errors=(FinError,)):
    """Of the faces of `shape` numbered `numbers`, in that order, the first
    the fins can be built under; None if none takes them. A build failing
    with one of `errors` passes to the next face; any other error is raised,
    so a fault in the kernel is not taken for a face without fins."""
    for number in numbers:
        try:
            build(shape, shape.Faces[number], p)
        except errors:
            continue
        return number
    return None


def stand_for_face(shape, number, p, angle_deg):
    """Stand `shape` so that face `number` leans over the bed by angle_deg and
    takes fins: (placement change, edge it stands on), the first of
    stands_for_face(), so it stands on the longest edge it can.

    INPUTS this has to withstand:
      planar face with straight edges       ->  stood on its longest edge that works
      longest edge does not carry the part
        or the fins do not fit there        ->  the next longest edge
      the kernel fails at one edge or rim   ->  the next one, as where fins do not fit
      round side                            ->  stood on the first rim of rims_on_axis()
                                                that works
      face without a straight edge, or none
        works                               ->  FinError
    """
    return next(_or_refused(stands_for_face(shape, number, p, angle_deg), NO_STAND_FOR_FACE))


def stands_for_face(shape, number, p, angle_deg):
    """Every way to stand `shape` so that face `number` leans over the bed by
    angle_deg and takes fins, as (placement change, edge it stands on), one at
    a time.

    The face is laid onto the bed and the part turned about one of its straight
    edges, the longest first. A round side stands the part on a rim on its axis
    instead, see rims_on_axis().
    """
    face = shape.Faces[number]
    if orient.is_round_side(face):
        tries = [(edge, partial(orient.stand_on_rim, shape, edge, orient.side_tilt(angle_deg), face))
                 for edge in rims_on_axis(shape, face)]
    else:
        straight = [edge for edge in face.Edges
                    if abs(edge.Length - (edge.Vertexes[-1].Point - edge.Vertexes[0].Point).Length) < d.TOLERANCE]
        tries = [(edge, partial(orient.stand, shape, edge, angle_deg, face))
                 for edge in sorted(straight, key=lambda candidate: -candidate.Length)]
    # A fault in the kernel at one edge or rim passes to the next, as a face
    # without room for fins does: the next is there to fall back on.
    for edge, stand in tries:
        try:
            change = stand()
            standing = moved(shape, change)
            build(standing, standing.Faces[number], p)
        except (orient.OrientError, FinError, Part.OCCError):
            continue
        yield change, edge


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
      one rim                               ->  stood on it, its side leaning angle_deg
                                                as with the side selected; fins under it,
                                                larger flat faces passed over
      one rim, fins do not fit under its
        side, or it has no whole side       ->  fins under the largest leaning face
      one planar face                       ->  it leans angle_deg over the bed, on its
                                                longest edge that works; fins under it
      one round side (cylinder, tube)       ->  stood on a rim, the side leaning
                                                angle_deg; one fin under it
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
    return next(quick_plans(shape, edges, faces, p, angle_deg))


def quick_plans(shape, edges, faces, p, angle_deg):
    """Every way Quick fins can stand `shape` for the elements selected, as
    QuickPlans, one at a time: first the one quick_plan() takes, then the
    others the task panel can step to. A face selected alone stands on each
    of its edges that works; an edge, a rim or a part laid on a face or
    resting between two takes the fins under each face that takes them; a
    face with its edge, chamfer or fillet stands just one way. Raises what
    quick_plan() raises, before the first plan.
    """
    if len(edges) == 1 and not faces:
        edge = edges[0][0]
        if orient.is_rim(edge):
            # The fins go under its side, which leans angle_deg as any face under
            # fins does; under the largest leaning face only where they do not fit
            # under the side, or it has none.
            side = orient.side_of_rim(shape, edge)
            change = orient.stand_on_rim(shape, edge, orient.side_tilt(angle_deg), side)
            stood = moved(shape, change)
            sides = [] if side is None else [i for i, face in enumerate(shape.Faces) if face.isSame(side)]
            # A kernel fault under the side passes to the other faces as well:
            # they are there to fall back on.
            under_side = first_taking_fins(stood, sides, p, (FinError, Part.OCCError))
            numbers = itertools.chain([] if under_side is None else [under_side],
                                      faces_taking_fins(stood, p, sides))
            for number in _or_refused(numbers, NO_LEANING_FACE):
                yield QuickPlan(change, number, edge, ())
            return
        if not orient.on_bed(shape, edge) and orient.right_angle_faces(shape, edge) is None:
            raise FinError(translate("FinSnap", "This edge does not lie on the bed, and its faces do not meet at a "
                                                "right angle. Use Stand on edge with the edge and the face that "
                                                "is to lie on the bed, then Add fins."))
        angle = angle_deg if orient.on_bed(shape, edge) else orient.RIGHT_ANGLE_TILT
        yield from _under_each_face(shape, orient.stand(shape, edge, angle), edge, (), p)
        return
    if not edges and len(faces) == 1:
        face, number = faces[0]
        if not orient.is_round_side(face) and (face.findPlane() is None or is_chamfer(shape, face)):
            yield from _under_each_face(shape, orient.lay_flat(shape, face), None, (), p)
            return
        for change, edge in _or_refused(stands_for_face(shape, number, p, angle_deg), NO_STAND_FOR_FACE):
            yield QuickPlan(change, number, edge, ())
        return
    if len(edges) == 1 and len(faces) == 1:
        (edge, _), (face, number) = edges[0], faces[0]
        # stand() refuses an edge of another face itself.
        change = orient.stand(shape, edge, angle_deg, face)
        yield _checked(shape, QuickPlan(change, number, edge, ()), p)
        return
    if not edges and len(faces) == 2:
        (first, number), (second, _) = faces
        beside = any(edge.isSame(other) for edge in first.Edges for other in second.Edges)
        if beside or second.findPlane() is None:
            change = orient.lay_flat(shape, second)
            yield _checked(shape, QuickPlan(change, number, None, ()), p)
            return
        yield from _under_each_face(shape, orient.rest_between(shape, first, second), None, (first, second), p)
        return
    raise FinError(translate("FinSnap", "Select an edge or a face, a face and the edge or the chamfer or fillet "
                                        "it is to stand on, or the two faces beside a fillet."))


# A QuickPlan rated for Quick fins (printable_plans()): its Islands, the
# levels of the faces overhanging without fins, limits.CRITICAL or
# UNPRINTABLE, and its bridge.Bridges; None each where it was not checked.
RatedPlan = namedtuple("RatedPlan", "plan islands overhangs bridges")


def printable_plans(shape, plans, p):
    """The QuickPlans `plans` for `shape` as RatedPlans, rated by the limits of
    the preferences: those that print, with no island, no face too flat and
    no bridge too long to print, in the order given; where none does, all of
    them, the fewest islands first, then the fewest faces and bridges that do
    not print. The islands are those of the part stood by the plan, see
    overhang.islands(); the fins do not count, they carry no layer. The
    overhangs and bridges leave out the face the fins go under, and a face a
    bridge covers whole is no overhang. Plans standing the part alike, differing
    only by the face for the fins, are checked for islands and bridges once.

    INPUTS this has to withstand:
      plans that print and plans that do not
                                            ->  those that print, in the order given
      every plan with islands               ->  all of them, the fewest first, the
                                                order given among as many
      as many islands, faces or bridges
        that do not print                   ->  the fewest of those first
      critical faces and bridges only       ->  the plan prints: kept, rated
      plans standing the part alike         ->  checked for islands and bridges once,
                                                the bridges of the face under the fins
                                                left out
      one plan                              ->  it, with None for each: unchecked,
                                                as there is no choice, and the fins
                                                warn of them
    """
    if len(plans) == 1:
        return [RatedPlan(plans[0], None, None, None)]
    rating = limits.current()
    checked = {}
    rated = []
    for plan in plans:
        stood = moved(shape, plan.change)
        key = tuple(plan.change.toMatrix().A)
        if key not in checked:
            checked[key] = (overhang.islands(stood, p.first_layer_height, p.layer_height),
                            bridge.bridges(stood, p.first_layer_height, p.layer_height, p.bead_width, rating))
        islands, every = checked[key]
        # The face under the fins spans nothing: it leaves the bridges it
        # alone lies under, the others lie under it no longer.
        carried = plan.number + 1
        spans = [found._replace(faces=[n for n in found.faces if n != carried],
                                covered=[n for n in found.covered if n != carried])
                 for found in every if any(n != carried for n in found.faces)]
        spanned = {number for found in spans for number in found.covered}
        levels = [level for number, level in overhang.rated(stood, (stood.Faces[plan.number],), rating)
                  if number not in spanned]
        rated.append(RatedPlan(plan, islands, levels, spans))

    def unprintable(entry):
        return (entry.overhangs.count(limits.UNPRINTABLE)
                + sum(1 for found in entry.bridges if found.level == limits.UNPRINTABLE))

    clean = [entry for entry in rated if not entry.islands and not unprintable(entry)]
    return clean or sorted(rated, key=lambda entry: (len(entry.islands), unprintable(entry)))


def _under_each_face(shape, change, edge, beside, p):
    """A QuickPlan for `shape` stood by `change` with the fins under each face
    that takes them, the largest first; FinError if none does."""
    for number in _or_refused(faces_taking_fins(moved(shape, change), p), NO_LEANING_FACE):
        yield QuickPlan(change, number, edge, beside)


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
