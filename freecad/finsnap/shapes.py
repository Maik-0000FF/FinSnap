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

import contextlib
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
# How many parts meshed_of() keeps a mesh of. It stays in memory until another
# part takes its place, also past the closing of a document, by decision: moving a
# fin needs it again at once, and one mesh is what that costs.
MESHES_KEPT = 1
_kept_meshes = {}
# Places to which the corners of a mesh are rounded to tell which of them the
# faces of a solid share (Enclosed): the kernel meshes each face with its own.
SAME_CORNER_DIGITS = 6
# The rays Enclosed counts the crossings of, tried in this order, each as the
# two axes it is seen across and the one it runs along.
ENCLOSED_RAYS = ((0, 1, 2), (1, 2, 0), (2, 0, 1))
# How many triangles the grid they are sorted into for a ray aims at a cell, and
# how often each may be named in it, over all the cells it reaches, before the
# grid is made coarser: more would take longer to sort than they save.
ENCLOSED_PER_CELL = 4
ENCLOSED_CELL_NAMINGS = 8


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
    """What tells a shape as it stands from another: its measures, where its
    corners lie and its centre, not its hash. FreeCAD gives a part a new hash each
    time it is recomputed, the same shape or not; the corners tell a shape whose
    measures stay apart, as with a hole moved, the centre one mirrored onto the
    same corners, its curved side now on the other side.

    INPUTS this has to withstand:
      the same shape, recomputed            ->  the same key
      a hole moved                          ->  another key, by its corners
      mirrored onto the same corners        ->  another key, by its centre
      the same, with the same centre too,
        as a shape symmetric about a point  ->  the same key, by decision: a key never
                                                proves two shapes alike, and this takes
                                                exactly such a shape, exactly mirrored
      an empty shape, which has no centre   ->  a key all the same
    """
    corners = tuple(sorted(tuple(round(c, KEY_DIGITS) for c in vertex.Point) for vertex in shape.Vertexes))
    try:
        centre = tuple(round(c, KEY_DIGITS) for c in shape.CenterOfGravity)
    except RuntimeError:
        centre = None
    return (round(shape.Volume, KEY_DIGITS), round(shape.Area, KEY_DIGITS), len(shape.Faces), len(shape.Edges),
            corners, centre)


# How many builds and checks of FinSnap are under way in the kernel, one
# within another counted each (working()).
_at_work = 0


@contextlib.contextmanager
def working():
    """While this lasts, FinSnap is at work in the kernel: building fins or
    checking a part. FreeCAD shows its progress during a long operation of
    the kernel and lets timers fire meanwhile; a build started from one of
    them, inside the operation under way, can stop in the kernel and never
    return, so FreeCAD freezes. Who would start one asks at_work() first.
    Used as a decorator as well.

    INPUTS this has to withstand:
      a build or a check under way          ->  at work
      one within another, a check in a
        build or a build tried in a build   ->  at work until the outermost is through
      what is done raising                  ->  the count taken back all the same
      nothing under way                     ->  not at work
    """
    global _at_work
    _at_work += 1
    try:
        yield
    finally:
        _at_work -= 1


def at_work():
    """Whether FinSnap is at work in the kernel, see working()."""
    return _at_work > 0


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
    """A mesh, or a distance on it, would take longer than measuring the shape, or
    does not fit in memory."""


def mesh_arrays(shape, deflection, on_copy=False, most=None):
    """The mesh of `shape` as arrays: its points (n, 3) and the three points of each
    triangle by number (m, 3). Empty where the kernel cannot mesh it. `on_copy`
    leaves the mesh the kernel keeps with the shape as it is. With `most`,
    TooManyPairs for a mesh of more triangles, before any array is made of it."""
    try:
        points, triangles = (shape.copy() if on_copy else shape).tessellate(deflection)
    except Part.OCCError:
        points, triangles = [], []
    if most is not None and len(triangles) > most:
        raise TooManyPairs
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
      a shape with too many triangles at
        NEAR_MESH_COARSE                    ->  TooManyPairs, before the fine mesh
      exactly as many as NEAR_MESH_MOST     ->  the fine mesh
      too many pairs to go through          ->  TooManyPairs
    """

    def __init__(self, shape):
        try:
            if len(shape.copy().tessellate(d.NEAR_MESH_COARSE)[1]) > d.NEAR_MESH_MOST:
                raise TooManyPairs
        except Part.OCCError:
            pass
        self.points, triangles = mesh_arrays(shape, d.NEAR_MESH_DEFLECTION, on_copy=True)
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
    """The Meshed of `shape`, made once, also where there is none to have, as it is too
    large for it or for memory, which is not tried again: TooManyPairs then."""
    def make():
        try:
            return Meshed(shape)
        except (MemoryError, TooManyPairs):
            return None

    found = keep(_kept_meshes, shape_key(shape), make, MESHES_KEPT)
    if found is None:
        raise TooManyPairs
    return found


def clear_meshes():
    """Forget every Meshed kept."""
    _kept_meshes.clear()


def _segment_distances(points, start, end):
    """The distance, in a plane, of each of `points` to the segment from `start`
    to `end` on its row; to `start` where the two are one point."""
    along = end - start
    length = (along * along).sum(1)
    with numpy.errstate(divide="ignore", invalid="ignore"):
        share = numpy.where(length > 0, ((points - start) * along).sum(1) / length, 0.0)
    nearest = start + along * numpy.clip(share, 0.0, 1.0)[:, None]
    return numpy.sqrt(((points - nearest) ** 2).sum(1))


_Cells = namedtuple("_Cells", "corner size count starts triangles most")


def _cells(low, high, margin):
    """Triangles, seen in a plane, sorted into a square grid by the boxes round
    them, from `low` to `high` on each row and `margin` wider: what
    _candidates() needs to name, for a point, the few it can lie within the
    margin of. The grid aims at ENCLOSED_PER_CELL triangles a cell; where
    they reach over so many cells that they are named more than
    ENCLOSED_CELL_NAMINGS times each, as the long ones round a cylinder do,
    it is made coarser."""
    corner = low.min(0) - 2 * margin
    extent = high.max(0) + 2 * margin - corner
    count = max(1, int(numpy.ceil(numpy.sqrt(len(low) / ENCLOSED_PER_CELL))))
    while True:
        size = extent / count
        first = numpy.clip(((low - margin - corner) / size).astype(int), 0, count - 1)
        reach = numpy.clip(((high + margin - corner) / size).astype(int), 0, count - 1) - first + 1
        each = reach[:, 0] * reach[:, 1]
        if count == 1 or each.sum() <= ENCLOSED_CELL_NAMINGS * len(low):
            break
        count //= 2
    of = numpy.repeat(numpy.arange(len(low)), each)
    step = numpy.arange(each.sum()) - numpy.repeat(numpy.cumsum(each) - each, each)
    cell = (first[of, 0] + step // reach[of, 1]) * count + first[of, 1] + step % reach[of, 1]
    order = numpy.argsort(cell, kind="stable")
    starts = numpy.searchsorted(cell[order], numpy.arange(count * count + 1))
    return _Cells(corner, size, count, starts, of[order], int(numpy.diff(starts).max()))


def _candidates(cells, seen):
    """For the points `seen` in the plane of `cells`, the triangles of the cell
    each lies in, as pairs: the number of the point and that of the triangle.
    A point off the grid lies further than the margin from every triangle and
    has none."""
    at = numpy.floor((seen - cells.corner) / cells.size).astype(int)
    on_grid = ((at >= 0) & (at < cells.count)).all(1)
    cell = numpy.where(on_grid, at[:, 0] * cells.count + at[:, 1], 0)
    each = numpy.where(on_grid, cells.starts[cell + 1] - cells.starts[cell], 0)
    which = numpy.repeat(numpy.arange(len(seen)), each)
    step = numpy.arange(each.sum()) - numpy.repeat(numpy.cumsum(each) - each, each)
    return which, cells.triangles[cells.starts[cell][which] + step]


class Enclosed:
    """A solid as a closed mesh, to tell of many points at once which lie inside
    it, in a fraction of the time the kernel takes for one. It tells only of a
    point ENCLOSED_MARGIN or more off the mesh, where the mesh and the solid
    agree; of any other it says nothing, and the caller asks the kernel.

    A point lies inside where a ray from it goes through the mesh an odd number
    of times. A ray that passes within the margin of the rim of a triangle
    could go through it or miss it: it is not counted on, and the next of
    ENCLOSED_RAYS is tried.

    Seen along a ray the triangles lie sorted into a grid (_cells()), made as
    the first point asks along it, so that a point is held against the few of
    its cell and what it costs hardly grows with the mesh.

    INPUTS this has to withstand (told()):
      a point deep inside the solid         ->  True
      a point well outside it, or outside
        the box round it                    ->  False
      a point in a hollow of it, or in a
        bore through it, off its walls      ->  False
      a point within the margin of the
        mesh, on either side: on the
        surface, or just in a round hollow
        the triangles cut into              ->  None
      a ray passing the rim of a triangle
        or an upright one within the margin ->  the answer of the next ray
      every ray passing one so              ->  None
      a mesh that is not closed, as of a
        shell or a face, or with an edge
        more than two triangles share       ->  None for every point
      a shape the kernel cannot mesh        ->  None for every point
      long triangles reaching over the
        whole of a round side               ->  a coarser grid, the same answers
      no points                             ->  []
      a mesh of more triangles than `most`  ->  TooManyPairs, nothing made of it
    """

    def __init__(self, solid, most=None):
        points, triangles = mesh_arrays(solid, d.ENCLOSED_DEFLECTION, on_copy=True, most=most)
        self.closed = self._closed(points, triangles)
        self.a, self.b, self.c = (points[triangles[:, k]] for k in range(3))
        self.low = numpy.minimum(numpy.minimum(self.a, self.b), self.c)
        self.high = numpy.maximum(numpy.maximum(self.a, self.b), self.c)
        # By ray, the grid its triangles are sorted into.
        self._grids = {}

    @staticmethod
    def _closed(points, triangles):
        """Whether every edge of the mesh belongs to two triangles, corners at one
        place taken for one and triangles drawn together to a line left out."""
        if not len(triangles):
            return False
        _, merged = numpy.unique(points.round(SAME_CORNER_DIGITS), axis=0, return_inverse=True)
        corners = merged.reshape(-1)[triangles]
        whole = (corners[:, 0] != corners[:, 1]) & (corners[:, 1] != corners[:, 2]) & (corners[:, 2] != corners[:, 0])
        corners = corners[whole]
        edges = numpy.sort(numpy.concatenate([corners[:, [0, 1]], corners[:, [1, 2]], corners[:, [2, 0]]]), axis=1)
        counts = numpy.unique(edges, axis=0, return_counts=True)[1]
        return bool(len(counts)) and bool((counts == 2).all())

    def _grid(self, axes):
        """The grid of the triangles seen along the ray `axes`."""
        if axes not in self._grids:
            across = list(axes[:2])
            self._grids[axes] = _cells(self.low[:, across], self.high[:, across], d.ENCLOSED_MARGIN)
        return self._grids[axes]

    def told(self, points):
        """For each of `points` True where it lies inside the solid, False where
        outside, None where the mesh does not tell. In blocks of about
        NEAR_PAIRS_AT_ONCE pairs of a point and a triangle, by the first ray."""
        if not len(points):
            return []
        if not self.closed:
            return [None] * len(points)
        points = numpy.array([tuple(point) for point in points], dtype=float).reshape(-1, 3)
        block = max(1, d.NEAR_PAIRS_AT_ONCE // max(1, self._grid(ENCLOSED_RAYS[0]).most))
        return [found for start in range(0, len(points), block) for found in self._told(points[start:start + block])]

    def _told(self, points):
        found = [None] * len(points)
        left = numpy.nonzero(~self._near(points))[0]
        for axes in ENCLOSED_RAYS:
            if not len(left):
                break
            crossings, passed_rim = self._ray(points[left], axes)
            for number, odd in zip(left[~passed_rim], crossings[~passed_rim] % 2 == 1):
                found[number] = bool(odd)
            left = left[passed_rim]
        return found

    def _near(self, points):
        """Which of `points` lie within the margin of the mesh: of a triangle of
        their cell seen along the first ray, as any that near lies in it."""
        margin, axes = d.ENCLOSED_MARGIN, ENCLOSED_RAYS[0]
        which, of = _candidates(self._grid(axes), points[:, list(axes[:2])])
        boxed = ((points[which] >= self.low[of] - margin) & (points[which] <= self.high[of] + margin)).all(1)
        which, of = which[boxed], of[boxed]
        found = numpy.zeros(len(points), dtype=bool)
        if len(which):
            off = _point_triangle_distances(points[which], self.a[of], self.b[of], self.c[of])
            found[which[off <= margin]] = True
        return found

    def _ray(self, points, axes):
        """For the rays from `points` along the last of `axes`, seen along it in the
        plane of the first two: how many triangles each goes through, and whether
        it passes within the margin of the rim of one at or above its point."""
        margin = d.ENCLOSED_MARGIN
        across, along = list(axes[:2]), axes[2]
        which, of = _candidates(self._grid(axes), points[:, across])
        over = points[which, along] <= self.high[of, along]
        for axis in across:
            at = points[which, axis]
            over &= (at >= self.low[of, axis] - margin) & (at <= self.high[of, axis] + margin)
        which, of = which[over], of[over]
        crossings = numpy.zeros(len(points), dtype=int)
        passed_rim = numpy.zeros(len(points), dtype=bool)
        if not len(which):
            return crossings, passed_rim
        seen = points[which][:, across]
        heights = [corner[of][:, along] for corner in (self.a, self.b, self.c)]
        a, b, c = (corner[of][:, across] for corner in (self.a, self.b, self.c))

        def side(start, end):
            """Twice the area `seen` spans with the edge, on its left counted positive."""
            return ((end[:, 0] - start[:, 0]) * (seen[:, 1] - start[:, 1])
                    - (end[:, 1] - start[:, 1]) * (seen[:, 0] - start[:, 0]))

        # By edge: a to b, which lies opposite c, b to c opposite a, c to a opposite b.
        sides = numpy.stack([side(a, b), side(b, c), side(c, a)])
        lengths = numpy.stack([numpy.hypot(*(end - start).T) for start, end in ((a, b), (b, c), (c, a))])
        area = sides.sum(0)
        # Seen along the ray, a triangle standing along it is a line.
        upright = numpy.abs(area) <= margin * lengths.max(0)
        if upright.any():
            at, (ua, ub, uc) = seen[upright], (corner[upright] for corner in (a, b, c))
            off = numpy.minimum(numpy.minimum(_segment_distances(at, ua, ub), _segment_distances(at, ub, uc)),
                                _segment_distances(at, uc, ua))
            passed_rim[which[upright][off <= margin]] = True
        lying = ~upright
        if lying.any():
            # How far inside each edge, and from them the least: inside the triangle past the margin.
            with numpy.errstate(divide="ignore", invalid="ignore"):
                inside = numpy.nanmin(sides[:, lying] * numpy.sign(area[lying]) / lengths[:, lying], axis=0)
            shares = sides[:, lying] / area[lying]
            height = shares[1] * heights[0][lying] + shares[2] * heights[1][lying] + shares[0] * heights[2][lying]
            passed_rim[which[lying][numpy.abs(inside) <= margin]] = True
            numpy.add.at(crossings, which[lying][(inside > margin) & (height > points[which][lying][:, along])], 1)
        return crossings, passed_rim


def enclosed_of(solid):
    """The Enclosed of `solid`; None where its mesh has more triangles than
    ENCLOSED_MOST, told as soon as it is meshed, or does not fit in memory,
    and the kernel is asked instead."""
    try:
        return Enclosed(solid, d.ENCLOSED_MOST)
    except (MemoryError, TooManyPairs):
        return None


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
