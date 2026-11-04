# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""The frame of a supported face: how it leans over the bed, and how a
round side is turned about its axis.

LOCAL FRAME of a face: `out` is the horizontal direction the face leans
towards, `along` runs horizontally along the face, z is up. A point is
t * along + s * out + z * Z. The face is the plane n . P = c with
n = n_out * out + n_z * Z, so at height z it lies at
    s_face(z) = (c - n_z * z) / n_out
and a plane offset by a distance along n at
    s_flank(z, offset) = (c + offset - n_z * z) / n_out:
the flank at the gap, the end of a tine at the tine clearance.
The fin occupies s >= s_flank(z); the part lies at smaller s.

ROUND SIDE: a cylinder or tube standing on its rim leans its curved side over
the bed. Its lowest line is straight, and the plane touching the side along it
stands in for the face: one fin stands in the middle under that line. A part
of a side, the round end of a slot or a fillet, takes its fin the same way
where its lowest line lies on it; that fin stays where it is, as turning the
part about the axis would carry its lowest line off the face. Across a
tine the side falls away behind the plane by a few thousandths of a millimetre,
so a tine ends on it wherever the side lies within ROUND_SIDE_MAX_DROP of the
plane. Under a whole side the fin can follow the contour of the part beyond
it instead, up to its top (contour.py).

INPUTS this has to withstand (orient.is_round_side()):
  curved side of a cylinder or tube     ->  True
  inner side of a tube                  ->  True; frame_of() refuses it
  fillet, part of a cylinder            ->  False; orient.is_curved_side() True
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
  part of a side (half round end of a
    slot, fillet), lowest line on it    ->  frame as on a whole side, not whole_side
  part of a side, lowest line off it    ->  FinError: it does not reach round to it
  part of a side curving inward (an
    inner fillet)                       ->  FinError: it curves inward
"""

import math
from dataclasses import dataclass

import FreeCAD as App
import Part

from . import defaults as d
from . import orient
from .i18n import QT_TRANSLATE_NOOP, translate
from .shapes import bounds, middle_normal

V = App.Vector
UP = V(0, 0, 1)
DOWN = V(0, 0, -1)
# Degrees in a whole turn.
FULL_CIRCLE = 360.0
# How closely the points that measure a face along its edges follow a curve (mm).
SPAN_DEFLECTION = 0.01
# Said where the face selected for fins faces up or sideways, or lies level.
NOT_OVERHANGING = QT_TRANSLATE_NOOP("FinSnap", "the selected face does not overhang; it faces up or sideways")
HORIZONTAL_FACE = QT_TRANSLATE_NOOP("FinSnap", "the selected face is horizontal; it rests on the bed or needs regular "
                                               "support")
# Said where a round side lies level at its lowest line, as a cylinder lying on it.
HORIZONTAL_ROUND_SIDE = QT_TRANSLATE_NOOP("FinSnap", "the round side lies horizontal at its lowest line; it rests on "
                                                     "the bed or needs regular support")
# Said where a part of a curved side, a fillet or the round end of a slot,
# does not reach round to the line it lies lowest along, under which its fin stands.
PART_OF_SIDE_OFF_LOWEST = QT_TRANSLATE_NOOP("FinSnap", "the selected curved face does not reach round to its "
                                                       "lowest line, under which its fin would stand")


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
    # Whether that curved side goes all the way round, so the part stands on
    # one point of its rim and turns about its axis to move the fin.
    whole_side: bool = False
    # The contour of the part the fin under that side follows
    # (contour.Contour), None where it stands under the side alone.
    contour: object = None
    # Only for a fin beside the lowest line of a whole side, where the side
    # falls away across the fin: the upright planes around its tines, their
    # contours (contour.across()), on which they end, and those under the tines
    # themselves; the curve its flank follows across
    # its thickness, as (where the lowest line is, the place along the face the
    # contour is measured at, the radius of the flank); and how far out its
    # flank stands past the contour, as measured on the part.
    tine_edges: tuple = None
    flank_curve: tuple = None
    flank_out: float = 0.0

    @property
    def round_side(self):
        return self.radius > 0

    @property
    def fixed_fin(self):
        """Whether the fin stays where it is planned, under the lowest line of
        a part of a side: it has no place along the face to be moved to, and
        no turn of the part moves it."""
        return self.round_side and not self.whole_side

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


def beside_lowest(radius, degrees):
    """How far along the face of a round side of `radius` a line of it lies
    that is `degrees` round from the lowest line (mm)."""
    return radius * math.sin(math.radians(degrees))


def in_plane(radius, away, distance):
    """What `distance` off a round side of `radius` round its axis comes to in
    an upright plane `away` mm along the face from its lowest line: longer, as
    the side falls away there. Past the side, as for a thinner step of it, it
    stays `distance`.

    INPUTS this has to withstand:
      on the lowest line                    ->  `distance`
      30 degrees round                      ->  a little more
      at or past the radius                 ->  `distance`
      a distance of 0                       ->  0
    """
    if abs(away) >= radius:
        return distance
    return math.sqrt((radius + distance) ** 2 - away ** 2) - math.sqrt(radius ** 2 - away ** 2)


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


def _lowest(face):
    """The direction from the axis of the round side `face` to its lowest line,
    square to the axis and pointing down the most: the side lies lowest there,
    and its normal leans furthest over the bed. Its horizontal part is `out`."""
    axis = V(face.Surface.Axis).normalize()
    n = DOWN - axis * DOWN.dot(axis)
    if n.Length < d.MIN_NORMAL_COMPONENT:
        raise FinError(translate("FinSnap", NOT_OVERHANGING))
    n.normalize()
    if V(n.x, n.y, 0).Length < d.MIN_NORMAL_COMPONENT:
        raise FinError(translate("FinSnap", HORIZONTAL_ROUND_SIDE))
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
    whole = orient.is_round_side(face)
    line = Part.LineSegment(surface.value(u, v0), surface.value(u, v1)).toShape().common(face)
    if not line.Edges:
        raise FinError(translate("FinSnap", "the lowest line of the selected face is cut away") if whole
                       else translate("FinSnap", PART_OF_SIDE_OFF_LOWEST))

    out = V(n.x, n.y, 0).normalize()
    along = UP.cross(out)
    middle = lowest.dot(along)
    drop = min(d.ROUND_SIDE_MAX_DROP, surface.Radius)
    half_width = math.sqrt(surface.Radius ** 2 - (surface.Radius - drop) ** 2)
    line_box = bounds(line)
    return Frame(out=out, along=along, n_out=n.dot(out), n_z=n.z, c=n.dot(lowest), bed_z=bounds(part).ZMin,
                 along_min=middle - half_width, along_max=middle + half_width, face_top_z=line_box.ZMax,
                 face_bottom_z=line_box.ZMin, radius=surface.Radius, whole_side=whole)


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
    if orient.is_curved_side(face):
        return _round_frame(part, face)
    if face.findPlane() is None:
        raise FinError(translate("FinSnap", "the selected face is not planar"))
    n = middle_normal(face)
    horizontal = V(n.x, n.y, 0)
    if n.z > -d.MIN_NORMAL_COMPONENT:
        raise FinError(translate("FinSnap", NOT_OVERHANGING))
    if horizontal.Length < d.MIN_NORMAL_COMPONENT:
        raise FinError(translate("FinSnap", HORIZONTAL_FACE))

    out = horizontal.normalize()
    along = UP.cross(out)
    extent = face if support is None else support
    low, high = span_along(extent, along)
    face_box = bounds(extent)
    return Frame(out=out, along=along, n_out=n.dot(out), n_z=n.z,
                 c=n.dot(face.Vertexes[0].Point), bed_z=bounds(part).ZMin,
                 along_min=low, along_max=high, face_top_z=face_box.ZMax,
                 face_bottom_z=face_box.ZMin)
