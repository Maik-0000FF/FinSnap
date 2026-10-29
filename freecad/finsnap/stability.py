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

Every layer is too many to work out at once on a large part: the part is
checked every SAMPLE_STEP mm and wherever a fin starts to hold it, and
layer by layer only between the checks around where it tips or comes
closest to tipping. The centres of mass found are kept in a dict the caller
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
  plumb line just inside                ->  stands, the margin small
  an empty part, or one with nothing on
    the bed                             ->  None
  a layer the kernel cannot cut out     ->  passed over
"""

import math
from collections import namedtuple

import FreeCAD as App
import Part

from . import defaults as d
from .shapes import bounds

# How often the part is checked before it is checked layer by layer (mm).
SAMPLE_STEP = 1.0
# How far round and below the part the cut-out reaches (mm), so it holds the
# whole part up to the layer, whatever its size.
CUT_MARGIN = 1.0
# How closely curved edges of a footprint are followed (mm).
FOOTPRINT_DEFLECTION = 0.1

# The result of check(): whether the part tips; the layer (from 0, the first)
# it tips at or, if it stands, comes closest to tipping at, and the height of
# its top over the bed (mm); the centre of mass of the part printed up to it
# and the foot of its plumb line on the bed; the margin, how far that foot
# lies inside the footprint (mm, below 0 outside); the direction on the bed
# out of the footprint nearest the foot; and the footprint, as points round
# it on the bed.
Stability = namedtuple("Stability", "tips layer height centre foot margin outward footprint")


def check(part, supports, first_layer, layer, centres):
    """Whether `part`, as it stands, stays standing while it is printed in
    layers, the first `first_layer` high, every other `layer` high, held by
    `supports`, (shape, height) pairs: what stands beside it on the bed, the
    fins, and the height from which each holds it, its lowest tine. A
    Stability, or None for a part with nothing on the bed. `centres`, a dict
    the caller keeps for this part as it stands, holds the centres of mass
    worked out, by layer."""
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

    def measure(number):
        """The margin at layer `number`, and what goes with it; None where
        the kernel cannot cut the part out up to it."""
        centre = centres.get(number)
        if number not in centres:
            centre = centres[number] = _centre_below(part, box, top(number))
        if centre is None:
            return None
        points = own + [point for points, height in feet if height <= top(number) for point in points]
        hull = _hull(points)
        margin, outward = _margin(hull, (centre.x, centre.y))
        return Stability(margin < 0, number, top(number) - bed, centre, App.Vector(centre.x, centre.y, bed),
                         margin, outward, [App.Vector(x, y, bed) for x, y in hull])

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
        return next((result for result in between if result is not None and result.tips), first)
    closest = min(found, key=lambda result: result.margin)
    at = ordered.index(closest.layer)
    low = ordered[at - 1] if at > 0 else closest.layer
    high = ordered[at + 1] if at + 1 < len(ordered) else closest.layer
    around = [measure(number) for number in range(low + 1, high) if number != closest.layer]
    return min([closest] + [result for result in around if result is not None], key=lambda result: result.margin)


def _centre_below(part, box, height):
    """The centre of mass of `part` below `height`; None where the kernel
    cannot cut it out."""
    size = max(box.XLength, box.YLength) + 2 * CUT_MARGIN
    below = Part.makeBox(size, size, height - box.ZMin + CUT_MARGIN,
                         App.Vector(box.Center.x - size / 2, box.Center.y - size / 2, box.ZMin - CUT_MARGIN))
    try:
        solids = part.common(below).Solids
    except Part.OCCError:
        return None
    volume = sum(solid.Volume for solid in solids)
    if volume <= 0:
        return None
    moment = App.Vector()
    for solid in solids:
        moment += solid.CenterOfMass * solid.Volume
    return moment * (1 / volume)


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
