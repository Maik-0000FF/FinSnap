# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Shapes in global coordinates, wherever the object sits in the tree.

A feature inside a PartDesign Body (a Pad, a Pocket) keeps its shape in the
coordinates of the Body. Selecting a face on it in the 3D view hands over that
local shape: after the Body was tilted, the face still looks untilted. Every
command therefore works on the global shape, and moves the outermost container
when it changes a placement.

INPUTS this has to withstand:
  top-level Part feature                ->  its shape as it is
  feature inside a Body (Pad)           ->  shape placed by the Body's placement
  Body itself                           ->  its shape as it is
  object in a Part container            ->  shape placed by every parent
  object without a shape                ->  ValueError naming it

A part made in a Body is the Body: its shape is that of its last feature,
so fins follow a chamfer or a fillet added after them (part_of()). A face is
found again there by the plane it lies in (face_like()), as its name changes
with every feature.

Faces are named and measured here as well, so every module agrees on what
"Face3" and "the middle of a face" mean.

INPUTS this has to withstand (bounds()):
  planar faces only                     ->  the same box as BoundBox
  cylinder or cone turned off its axis  ->  the box touching the surface; BoundBox
                                            reaches up to millimetres beyond it
  single face or edge                   ->  its tight box
  shape carrying a display mesh         ->  the same box: measured on the surfaces,
                                            not on the mesh, which lies up to its
                                            deflection off them
"""

from collections import namedtuple

import numpy
import Part

from . import defaults as d
from .i18n import translate

# bounds() measures the surfaces themselves, never a mesh that may hang on them.
USE_TRIANGULATION = False
# Prefix of the face names FreeCAD uses in selections and links: "Face3".
FACE_PREFIX = "Face"
# The container that holds a PartDesign part; its shape is that of its last feature.
BODY_TYPE = "PartDesign::Body"
# Two faces lie in one plane within this distance (mm) and this cosine
# between their normals; a feature that cuts a face leaves the rest of it
# exactly where it was.
SAME_PLACE = 1e-3
SAME_DIRECTION = 1.0 - 1e-6
# Places to which shape_key() rounds the measures and corners of a shape.
KEY_DIGITS = 6
# What keep() holds in one store at most, the oldest going first.
KEPT = 8
# A triangle whose cross product of two sides is no longer than this has no area (mm2).
SMALLEST_AREA = 1e-9
# How many parts meshed_of() keeps a fine mesh of, in memory for the whole session.
MESHES_KEPT = 2
_kept_meshes = {}


def face_name(number):
    """The name of face `number`, counted from 1 as FreeCAD does."""
    return "%s%d" % (FACE_PREFIX, number)


def middle_of(face):
    """The surface parameters in the middle of `face`."""
    u0, u1, v0, v1 = face.ParameterRange
    return (u0 + u1) / 2, (v0 + v1) / 2


def middle_normal(face):
    """The outward normal in the middle of `face`."""
    return face.normalAt(*middle_of(face))


def bounds(shape):
    """The box that touches `shape`. BoundBox only encloses the control points
    of curved faces, so after a turn it can stand millimetres off a fillet: a
    part would then float above the bed, and fins reach below it."""
    return shape.optimalBoundingBox(USE_TRIANGULATION)


def shape_key(shape):
    """What tells a shape as it stands from another: its measures and where
    its corners lie, not its hash. FreeCAD gives a part a new hash each time
    it is recomputed, the same shape or not; the corners tell a shape whose
    measures stay apart, as with a hole moved."""
    corners = tuple(sorted(tuple(round(c, KEY_DIGITS) for c in vertex.Point) for vertex in shape.Vertexes))
    return (round(shape.Volume, KEY_DIGITS), round(shape.Area, KEY_DIGITS), len(shape.Faces), len(shape.Edges),
            corners)


def keep(store, key, make, most=KEPT):
    """What the dict `store` keeps under `key`, made by make() where it keeps
    nothing yet; past `most` entries the oldest goes first."""
    if key not in store:
        while len(store) >= most:
            store.pop(next(iter(store)))
        store[key] = make()
    return store[key]


def _point_triangle_distances(points, a, b, c):
    """The distance of each of `points` to the triangle (a, b, c) on its row, by
    which of its corners, sides or its inside lies nearest."""
    ab, ac = b - a, c - a
    d1, d2 = (ab * (points - a)).sum(1), (ac * (points - a)).sum(1)
    d3, d4 = (ab * (points - b)).sum(1), (ac * (points - b)).sum(1)
    d5, d6 = (ab * (points - c)).sum(1), (ac * (points - c)).sum(1)
    vc, vb, va = d1 * d4 - d3 * d2, d5 * d2 - d1 * d6, d3 * d6 - d5 * d4
    with numpy.errstate(divide="ignore", invalid="ignore"):
        whole = 1.0 / (va + vb + vc)
        nearest = a + ab * (vb * whole)[:, None] + ac * (vc * whole)[:, None]
        for where, there in (((vc <= 0) & (d1 >= 0) & (d3 <= 0), a + ab * (d1 / (d1 - d3))[:, None]),
                             ((vb <= 0) & (d2 >= 0) & (d6 <= 0), a + ac * (d2 / (d2 - d6))[:, None]),
                             ((va <= 0) & (d4 >= d3) & (d5 >= d6),
                              b + (c - b) * ((d4 - d3) / ((d4 - d3) + (d5 - d6)))[:, None]),
                             ((d1 <= 0) & (d2 <= 0), a), ((d3 >= 0) & (d4 <= d3), b), ((d6 >= 0) & (d5 <= d6), c)):
            nearest = numpy.where(where[:, None], there, nearest)
    return numpy.sqrt(((points - nearest) ** 2).sum(1))


_Triangles = namedtuple("_Triangles", "a b c low high normals offsets")


def _triangles(a, b, c):
    """The triangles (a, b, c), all with an area, with what _least_distance() looks
    at first: the box round each and its plane."""
    normals = numpy.cross(b - a, c - a)
    normals /= numpy.linalg.norm(normals, axis=1, keepdims=True)
    return _Triangles(a, b, c, numpy.minimum(numpy.minimum(a, b), c), numpy.maximum(numpy.maximum(a, b), c),
                      normals, (normals * a).sum(1))


def _least_distance(points, triangles, reach):
    """The least distance of `points` to the `triangles`, `reach` where none comes
    nearer. In blocks of NEAR_PAIRS_AT_ONCE pairs, however many they are: most are
    ruled out by the box of the triangle, then by its plane, and what one block
    finds rules out more in the next."""
    if not len(points) or not len(triangles.a):
        return reach
    block = max(1, d.NEAR_PAIRS_AT_ONCE // len(triangles.a))
    for start in range(0, len(points), block):
        some = points[start:start + block]
        near = numpy.ones((len(some), len(triangles.a)), dtype=bool)
        for axis in range(3):
            along = some[:, axis:axis + 1]
            near &= (along >= triangles.low[:, axis] - reach) & (along <= triangles.high[:, axis] + reach)
        which, of = numpy.nonzero(near)
        close = numpy.abs((some[which] * triangles.normals[of]).sum(1) - triangles.offsets[of]) <= reach
        which, of = which[close], of[close]
        if len(which):
            found = _point_triangle_distances(some[which], triangles.a[of], triangles.b[of], triangles.c[of])
            reach = min(reach, float(found.min()))
    return reach


class TooManyPairs(Exception):
    """A distance on a mesh would take longer than measuring the shape."""


def mesh_arrays(shape, deflection):
    """The mesh of `shape` as arrays: its points (n, 3) and the three points of each
    triangle by number (m, 3). Empty where the kernel cannot mesh it."""
    try:
        points, triangles = shape.tessellate(deflection)
    except Part.OCCError:
        points, triangles = [], []
    return (numpy.array([(point.x, point.y, point.z) for point in points], dtype=float).reshape(-1, 3),
            numpy.array(triangles, dtype=int).reshape(-1, 3))


class Meshed:
    """A shape as triangles, to tell in a fraction of the time a solid takes how
    far from it the surface between rings of points lies. On a copy: the kernel
    keeps one mesh with a shape and would reuse this one for others asked of it.

    It measures the corners of each against the triangles of the other, and the
    rings' end faces only by their corners. It knows no inside: a caller has the
    last word measured on the shape.

    INPUTS this has to withstand (distance()):
      surface some way off a face           ->  that distance, within the deflection
      a corner of the shape near the surface ->  the distance to that corner
      all of it further than `reach`        ->  `reach`
      surface deep inside the shape, further
        than `reach` from every face        ->  `reach`, as if clear: by decision, the
                                                caller's measure on the shape says no
      rings with points alike               ->  the triangles without area left out
      a triangle of the mesh without area   ->  left out, it has no plane
      a shape the kernel cannot mesh        ->  `reach`: nothing seen, for the same caller
      too many pairs to go through          ->  TooManyPairs
    """

    def __init__(self, shape):
        self.points, triangles = mesh_arrays(shape.copy(), d.NEAR_MESH_DEFLECTION)
        a, b, c = (self.points[triangles[:, k]] for k in range(3))
        kept = numpy.linalg.norm(numpy.cross(b - a, c - a), axis=1) > SMALLEST_AREA
        self.numbers = triangles[kept]
        self.triangles = _triangles(a[kept], b[kept], c[kept])

    def distance(self, rings, reach):
        """The least distance of the surface between `rings`, lists of as many
        points, from the shape, `reach` where it is no nearer than that."""
        corners = numpy.array([tuple(point) for ring in rings for point in ring], dtype=float).reshape(-1, 3)
        faces = numpy.array([[tuple(point) for point in triangle] for triangle in between_rings(rings)],
                            dtype=float).reshape(-1, 3, 3)
        mine = self.triangles
        within = (mine.low <= corners.max(0) + reach).all(1) & (mine.high >= corners.min(0) - reach).all(1)
        near_corners = self.points[numpy.unique(self.numbers[within])]
        if max(len(corners) * int(within.sum()), len(near_corners) * len(faces)) > d.NEAR_MOST_PAIRS:
            raise TooManyPairs
        least = _least_distance(corners, _Triangles(*(field[within] for field in mine)), reach)
        return _least_distance(near_corners, _triangles(faces[:, 0], faces[:, 1], faces[:, 2]), least)


def meshed_of(shape):
    """The Meshed of `shape`, made once; the mesh of a large part is large, so only
    the last MESHES_KEPT stay."""
    return keep(_kept_meshes, shape_key(shape), lambda: Meshed(shape), MESHES_KEPT)


def clear_meshes():
    """Forget every Meshed kept."""
    _kept_meshes.clear()


def between_rings(rings):
    """The triangles from each of `rings`, polygons of as many points, to the
    next, without those of no area."""
    for one, other in zip(rings, rings[1:]):
        for k in range(len(one)):
            a, b, c, e = one[k], one[(k + 1) % len(one)], other[(k + 1) % len(one)], other[k]
            for triangle in ((a, b, c), (a, c, e)):
                if (triangle[1] - triangle[0]).cross(triangle[2] - triangle[0]).Length > SMALLEST_AREA:
                    yield triangle


def moved(shape, change):
    """A copy of `shape` with the placement change `change` applied."""
    result = shape.copy()
    result.Placement = change.multiply(result.Placement)
    return result


def global_shape(obj):
    shape = Part.getShape(obj, "", needSubElement=False, transform=False)
    if shape.isNull():
        raise ValueError(translate("FinSnap", "%s has no shape") % obj.Label)
    shape = shape.copy()
    shape.Placement = obj.getGlobalPlacement()
    return shape


def outermost(obj):
    """The container whose placement moves the whole part: the topmost parent group."""
    while True:
        parent = obj.getParentGeoFeatureGroup()
        if parent is None:
            return obj
        obj = parent


def part_of(obj):
    """The object whose shape is the part `obj` belongs to: the Body of a
    feature inside a PartDesign Body, which holds the shape with every feature
    after it, a chamfer or a fillet added later as well; else `obj` itself."""
    parent = obj.getParentGeoFeatureGroup()
    if parent is not None and parent.isDerivedFrom(BODY_TYPE):
        return parent
    return obj


def plane_of(face):
    """The plane `face` lies in, as (a point on it, its outward normal), or
    None for a face that is not planar."""
    if face.findPlane() is None:
        return None
    return face.CenterOfMass, middle_normal(face)


def face_like(shape, face):
    """The name on `shape` of the face lying where `face` lies, the same face
    on another shape of the part, or the largest of those in its plane where
    a feature cut it; None if there is none.

    INPUTS this has to withstand:
      the same face, other numbers          ->  its name on `shape`
      a planar face cut smaller by a
        chamfer, a fillet or a pocket       ->  the face left in its plane
      a planar face cut in two              ->  the larger piece
      a face of the same plane facing the
        other way (the other side of a wall) ->  passed over: its normal is reversed
      a planar face cut away whole          ->  None
      a curved face, unchanged              ->  the face with its centre of mass and area
      a curved face changed                 ->  None: it has no plane to find it by
    """
    plane = plane_of(face)
    if plane is None:
        return next((face_name(number) for number, candidate in enumerate(shape.Faces, 1)
                     if candidate.CenterOfMass.distanceToPoint(face.CenterOfMass) < SAME_PLACE
                     and abs(candidate.Area - face.Area) < SAME_PLACE), None)
    return face_in_plane(shape, *plane)


def in_plane(face, point, normal):
    """Whether `face` is planar and lies in the plane through `point` with the
    outward normal `normal`."""
    return (plane_of(face) is not None and middle_normal(face).dot(normal) > SAME_DIRECTION
            and abs((face.CenterOfMass - point).dot(normal)) < SAME_PLACE)


def face_in_plane(shape, point, normal):
    """The name of the largest face of `shape` in the plane through `point`
    with the outward normal `normal`, see in_plane(); None if there is none."""
    found = [(candidate.Area, number) for number, candidate in enumerate(shape.Faces, 1)
             if in_plane(candidate, point, normal)]
    return face_name(max(found)[1]) if found else None
