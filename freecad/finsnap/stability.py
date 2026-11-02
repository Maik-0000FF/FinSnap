# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Whether a part stays standing while it is printed, layer by layer.

The part grows from the bed, and with it its centre of mass moves. Each
layer, the part printed so far stands as long as the plumb line from its
centre of mass meets the bed inside its footprint: the outline round what
stands on the bed, the first layer of the part and the feet of the fins
that hold it by then. A fin holds the part only from its lowest tine up;
below, the part stands on its own. The first layer whose plumb line falls
outside tips the part over.

How safely a layer stands is its tipping angle: how far the part printed up
to it would have to lean before its plumb line left the footprint,
atan(margin / height of its centre of mass over the bed). A force from the
side tips the part once its share of the weight passes the tangent of that
angle, as the acceleration of a moving bed does: a tall part needs a wider
margin than a flat one for the same angle.

Every layer is too many to work out at once on a large part: the part is
checked every SAMPLE_STEP mm and wherever a fin starts to hold it, and
layer by layer only between the checks around where it tips or where its
tipping angle is smallest. The centres of mass are worked out on one mesh of
the part (_Below), not cut out for each layer, and kept in a dict the caller
holds for the part as it stands, so a check after the fins changed only
measures the footprints anew.

INPUTS this has to withstand (check()):
  box lying on the bed                  ->  stands, its plumb line in the middle
  box standing on an edge, no fins      ->  tips at the first layer that leans it
                                            past the edge
  the same with fins under it           ->  stands from the lowest tine of the fins
                                            up; below that, as without fins
  a part growing out over its edge high
    up                                  ->  tips at the layer that carries its
                                            centre of mass past the edge
  plumb line past an end of the edge    ->  tips, its outward direction along the edge
  plumb line just inside                ->  stands, the margin and angle small
  the same margin, the centre of mass
    higher                              ->  a smaller tipping angle
  a brim                                ->  the footprint grown by its width all round
  an empty part, or one with nothing on
    the bed                             ->  None
  a part the kernel cannot mesh         ->  None
"""

import math
from collections import namedtuple

import numpy

import FreeCAD as App
import Part

from . import defaults as d
from . import overhang
from .shapes import bounds

# How often the part is checked before it is checked layer by layer (mm).
SAMPLE_STEP = 1.0
# How closely curved edges of a footprint are followed (mm).
FOOTPRINT_DEFLECTION = 0.1
# Points round each corner of a footprint grown by a brim, for its outline.
BRIM_CORNER_POINTS = 16
# What each triangle of the mesh adds to the centres of mass, see _Below: its
# volume and its moments along x, y and z.
INTEGRALS = 4

# The result of check(): whether the part tips; the layer (from 0, the first)
# it tips at or, if it stands, has its smallest tipping angle at, and the height of
# its top over the bed (mm); the centre of mass of the part printed up to it
# and the foot of its plumb line on the bed; the margin, how far that foot
# lies inside the footprint (mm, below 0 outside); the direction on the bed
# out of the footprint nearest the foot; the footprint, as points round it on
# the bed; the tipping angle (degrees, below 0 where it tips); and the margins
# and angles found on the way, as (height over the bed, margin, angle) from
# the bed up, the layers checked only.
Stability = namedtuple("Stability", "tips layer height centre foot margin outward footprint angle profile")


def check(part, supports, first_layer, layer, centres, brim=0.0):
    """Whether `part`, as it stands, stays standing while it is printed in
    layers, the first `first_layer` high, every other `layer` high, held by
    `supports`, (shape, height) pairs: what stands beside it on the bed, the
    fins, and the height from which each holds it, its lowest tine. A brim
    `brim` mm wide round it all on the bed holds it as well: the footprint
    grows by that much all round. A Stability, or None for a part with
    nothing on the bed. `centres`, a dict the caller keeps for this part as
    it stands, holds the centres of mass worked out, by layer."""
    if part.isNull():
        return None
    box = bounds(part)
    bed = box.ZMin
    count = max(1, math.ceil((box.ZMax - bed - first_layer) / layer) + 1)

    def top(number):
        return bed + first_layer + number * layer

    foot_z = bed + first_layer / 2
    own = _foot_points(part, foot_z)
    if not own:
        return None
    feet = [(_foot_points(shape, foot_z), height) for shape, height in supports]
    # The mesh the centres are worked out on, made once the first is asked.
    below = None

    def measure(number):
        """The margin at layer `number`, and what goes with it; None where
        nothing of the part lies below its top."""
        nonlocal below
        if number not in centres:
            below = below or _Below(part)
            centres[number] = below.centre(top(number))
        centre = centres[number]
        if centre is None:
            return None
        points = own + [point for points, height in feet if height <= top(number) for point in points]
        hull = _hull(points)
        margin, outward = _margin(hull, (centre.x, centre.y))
        # The hull grown by the brim all round: every point inside it lies that
        # much deeper, every point outside that much nearer.
        margin += brim
        shown = _hull([(x + brim * math.cos(turn), y + brim * math.sin(turn)) for x, y in hull for turn in
                       (2 * math.pi * k / BRIM_CORNER_POINTS for k in range(BRIM_CORNER_POINTS))]) if brim > 0 else hull
        angle = math.degrees(math.atan2(margin, centre.z - bed))
        result = Stability(margin < 0, number, top(number) - bed, centre, App.Vector(centre.x, centre.y, bed),
                           margin, outward, [App.Vector(x, y, bed) for x, y in shown], angle, None)
        seen[number] = result
        return result

    # Every layer checked, for the profile of the result.
    seen = {}
    step = max(1, round(SAMPLE_STEP / layer))
    samples = set(range(0, count, step)) | {count - 1}
    # Where a fin starts to hold the part, and the layer below.
    for _, height in supports:
        holding = max(0, min(count - 1, math.ceil((height - bed - first_layer) / layer)))
        samples |= {holding, max(0, holding - 1)}
    measured = {}
    for number in sorted(samples):
        measured[number] = measure(number)
    found = [result for result in measured.values() if result is not None]
    if not found:
        return None
    ordered = sorted(measured)
    tipping = [result for result in found if result.tips]
    if tipping:
        first = min(tipping, key=lambda result: result.layer)
        before = max([number for number in ordered if number < first.layer] or [first.layer])
        between = [measure(number) for number in range(before + 1, first.layer)]
        return _with_profile(next((result for result in between if result is not None and result.tips), first),
                             seen)
    closest = min(found, key=lambda result: result.angle)
    at = ordered.index(closest.layer)
    low = ordered[at - 1] if at > 0 else closest.layer
    high = ordered[at + 1] if at + 1 < len(ordered) else closest.layer
    around = [measure(number) for number in range(low + 1, high) if number != closest.layer]
    return _with_profile(min([closest] + [result for result in around if result is not None],
                             key=lambda result: result.angle), seen)


def _with_profile(result, seen):
    """`result` with the margins and angles of every layer checked, from the bed up."""
    return result._replace(profile=[(found.height, found.margin, found.angle) for _, found in sorted(seen.items())])


def section(part, z):
    """Where the plane at height `z` cuts `part`, as a shape of faces, to show
    a layer in the part; None where nothing is there or the kernel cannot
    make it. Cut as islands and bridges cut their layers (overhang.layer_faces())."""
    faces = overhang.layer_faces(part, z)
    return Part.makeCompound(faces) if faces else None


class _Below:
    """The volume and centre of mass of a part below any height, worked out
    on one mesh of its surface instead of a boolean cut for each height.

    By the divergence theorem, the volume and moments of the part below a
    plane are integrals over its surface below the plane, of fields with no
    z part, so the open cut at the plane adds nothing:
        volume  x nx    moment along x  x²/2 nx
        along y  xy nx  along z         xz nx
    Each is of the second degree over a triangle and so summed exactly from
    the middles of its edges. Triangles lying wholly below a height are summed
    once, in the order of their tops; those crossing it are clipped at it.
    The mesh is held in numpy arrays: a fine one has hundreds of thousands of
    triangles, and summing them one by one in Python took most of the check.

    INPUTS this has to withstand (centre()):
      a height above the part              ->  the centre of the whole part
      a height through a triangle          ->  that triangle clipped at it
      a height at the top of a triangle    ->  summed whole, not clipped
      a height below the part              ->  None
      a part the kernel cannot mesh        ->  None for every height
    """

    def __init__(self, part):
        try:
            points, triangles = part.tessellate(d.CENTRE_MESH_DEFLECTION)
        except Part.OCCError:
            points, triangles = [], []
        corners = numpy.array([(point.x, point.y, point.z) for point in points], dtype=float).reshape(-1, 3)
        # Each triangle as its three corners, in the order of their tops.
        triangles = corners[numpy.array(triangles, dtype=int).reshape(-1, 3)]
        tops = triangles[:, :, 2].max(axis=1)
        order = numpy.argsort(tops, kind="stable")
        self.triangles, self.tops = triangles[order], tops[order]
        self.bottoms = self.triangles[:, :, 2].min(axis=1)
        # The sums of the triangles up to each, in the order of their tops.
        self.summed = numpy.vstack([numpy.zeros(INTEGRALS), numpy.cumsum(_integrals(self.triangles), axis=0)])

    def centre(self, height):
        """The centre of mass of the part below `height`, as an App.Vector;
        None where nothing of it lies below."""
        whole = int(numpy.searchsorted(self.tops, height, side="right"))
        sums = self.summed[whole].copy()
        # Of the triangles not summed whole, those reaching below the height.
        crossing = whole + numpy.flatnonzero(self.bottoms[whole:] < height)
        pieces = [piece for number in crossing for piece in _clipped(self.triangles[number].tolist(), height)]
        if pieces:
            sums += _integrals(numpy.array(pieces)).sum(axis=0)
        volume = sums[0]
        if volume <= 0:
            return None
        return App.Vector(*(float(value) for value in sums[1:] / volume))


def _integrals(triangles):
    """The volume and the moments along x, y and z each of `triangles`, an
    array of triangles of three (x, y, z) corners counterclockwise seen from
    outside, adds, see _Below: one row of INTEGRALS for each."""
    a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    # Twice the area of each triangle times the x part of its normal.
    normal_x = (b[:, 1] - a[:, 1]) * (c[:, 2] - a[:, 2]) - (b[:, 2] - a[:, 2]) * (c[:, 1] - a[:, 1])
    middles = ((a + b) / 2, (b + c) / 2, (c + a) / 2)
    sums = numpy.stack([sum(m[:, 0] for m in middles), sum(m[:, 0] * m[:, 0] / 2 for m in middles),
                        sum(m[:, 0] * m[:, 1] for m in middles), sum(m[:, 0] * m[:, 2] for m in middles)], axis=1)
    # The area times the mean of the three middles.
    return sums * (normal_x / 6)[:, None]


def _clipped(triangle, height):
    """The part of `triangle`, three (x, y, z) corners, below `height`, as
    triangles, turning as it does."""
    outline = []
    for start, end in zip(triangle, triangle[1:] + triangle[:1]):
        if start[2] <= height:
            outline.append(start)
        if (start[2] <= height) != (end[2] <= height):
            share = (height - start[2]) / (end[2] - start[2])
            outline.append([s + share * (e - s) for s, e in zip(start, end)])
    return [(outline[0], outline[k], outline[k + 1]) for k in range(1, len(outline) - 1)]


def _foot_points(shape, z):
    """Points round where the plane at height `z` cuts `shape`, as (x, y):
    what stands on the bed in the first layer."""
    try:
        wires = shape.slice(App.Vector(0, 0, 1), z)
    except Part.OCCError:
        return []
    return [(point.x, point.y) for wire in wires for edge in wire.Edges
            for point in edge.discretize(Deflection=FOOTPRINT_DEFLECTION)]


def _hull(points):
    """The convex hull of `points`, (x, y), counterclockwise, without repeats."""
    unique = sorted(set((round(x, 6), round(y, 6)) for x, y in points))
    if len(unique) < 3:
        return unique

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _margin(hull, point):
    """How far `point` lies inside the polygon `hull`, counterclockwise (mm,
    below 0 outside), and the outward direction, as an App.Vector on the bed,
    of its edge nearest to the point."""
    if len(hull) < 3:
        # A footprint without area, a line or a point: nothing stands on it.
        ends = hull if len(hull) == 2 else hull * 2
        (ax, ay), (bx, by) = ends
        px, py = point
        dx, dy = bx - ax, by - ay
        share = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        nx, ny = px - (ax + share * dx), py - (ay + share * dy)
        away = math.hypot(nx, ny)
        outward = App.Vector(nx, ny, 0).normalize() if away > d.TOLERANCE else App.Vector(-dy, dx, 0).normalize()
        return -away, outward
    inside = True
    best, outward = None, None
    for (ax, ay), (bx, by) in zip(hull, hull[1:] + hull[:1]):
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy)
        # Counterclockwise, the inside lies to the left of every edge.
        side = (dx * (point[1] - ay) - dy * (point[0] - ax)) / length
        if side < 0:
            inside = False
        share = max(0.0, min(1.0, ((point[0] - ax) * dx + (point[1] - ay) * dy) / (length * length)))
        distance = math.hypot(point[0] - (ax + share * dx), point[1] - (ay + share * dy))
        if best is None or distance < best:
            best, outward = distance, App.Vector(dy / length, -dx / length, 0)
    return (best if inside else -best), outward
