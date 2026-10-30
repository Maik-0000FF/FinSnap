# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Bridges of a part: where a layer spans a gap between supports on the layer
below, and how far.

A region of a layer resting on nothing below it starts in the air. Resting on
the layer below at no side it is an island (overhang.islands()); at one side
it hangs out from there, an overhang; at two or more sides the slicer lays
straight lines across from support to support, a bridge. Its risk is the
length of those lines, its span, not the angle of the face under it.

The span is found as a slicer finds the direction to bridge in: lines one bead
apart, farther on a large region, are laid across the free region in coarse
steps of direction, then in fine ones round the best, and the lines whose
both ends rest on the layer below count. The direction where they
cover the most is the one bridged, the shorter one where two cover about as
much. A line counts as anchored where it reaches half a bead past each of
its ends onto the layer below, and only where it crosses more than a bead of
free region: a rim narrower than that is printed as the overhang perimeter of
the layer below and spans nothing. The longest anchored line of the direction
bridged is the span.

The region is never offset: the kernel's 2D offset can crash FreeCAD on some
outlines, in a way no exception catches. Lines are extended instead, and
distances measured.

Only the layers where a face lying flatter than the critical overhang limit
starts are cut: a bridge spans under such a face, and nowhere else.

INPUTS this has to withstand (bridges()):
  box lying on the bed                  ->  []
  slab across a gap between two
    pillars                             ->  one Bridge under the slab, the gap
                                            its span, rated by the limits
  the same, the slab longer than the
    gap is wide                         ->  the span across the gap, not along it
  the slab reaching past the piers at
    the back                            ->  the bridge across the gap, its face
                                            not covered: it overhangs past it
  an arm reaching out at one side       ->  [] (an overhang)
  a block floating above the bed        ->  [] (an island)
  a free rim narrower than a bead       ->  []
  the face under the slab carried by
    fins (`supported`)                  ->  []
  a face starting in the first layer    ->  [] (the bed carries it)
  an empty shape, or a layer the kernel
    cannot cut or clip                  ->  no bridge said there
"""

import math
from collections import namedtuple

import FreeCAD as App
import Part

from . import defaults as d
from . import overhang
from .shapes import bounds

# The directions lines are laid across a free region in, over half a turn, a
# line having no sense: this far apart (degrees) first, then this far round
# the best of them. At most this many lines are laid in one direction.
BRIDGE_COARSE_STEP = 15
BRIDGE_FINE_STEP = 5
HALF_TURN = 180
LINES_MOST = 40
# Two directions covering within this many line spacings as much count as alike.
COVERAGE_ALIKE = 1.0

# What the kernel raises where it cannot cut or clip a region.
KERNEL_ERRORS = (Part.OCCError, App.Base.CADKernelError)
# A bridge: the numbers (from 1) of the faces of the part it lies under, those
# of them it covers whole, the free region of its first layer at the height of
# the lowest of them, where it shows on the underside of the part, its span
# (mm) and its level, limits.GOOD, CRITICAL or UNPRINTABLE. A face covered in
# part reaches past the bridge, overhanging there.
Bridge = namedtuple("Bridge", "faces covered region span level")


def bridges(shape, first_layer, layer, bead, rating, supported=()):
    """The Bridges of `shape` as it stands, printed in layers `first_layer`
    high on the bed, every other `layer` high, in beads `bead` wide, rated by
    `rating`, a limits.Limits. Faces in `supported`, carried by fins, span
    nothing."""
    if shape.isNull():
        return []
    bed = bounds(shape).ZMin
    starting = {}
    for number, down in overhang.steepest_down(shape, supported, rating.overhang_min_area):
        if not overhang.flatter(down, rating.overhang_critical):
            continue
        number_of_layer = overhang.layer_holding(bounds(shape.Faces[number - 1]).ZMin - bed, first_layer, layer)
        if number_of_layer > 0:
            starting.setdefault(number_of_layer, []).append(number)
    found = []
    # Each layer cut once: one layer's cut is often the next one's below.
    cuts = {}

    def cut(number_of_layer):
        if number_of_layer not in cuts:
            cuts[number_of_layer] = _cut(shape, bed + overhang.layer_middle(number_of_layer, first_layer, layer))
        return cuts[number_of_layer]

    for number_of_layer, numbers in sorted(starting.items()):
        here, below = cut(number_of_layer), cut(number_of_layer - 1)
        if not here or not below:
            continue
        for region in _free(here, below):
            bridged = _span(region, below, bead)
            if bridged is None:
                continue
            span, lines, spacing = bridged
            under = [n for n in numbers if _lies_over(shape.Faces[n - 1], region, bead)]
            if under:
                ceiling = min(bounds(shape.Faces[n - 1]).ZMin for n in under)
                covered = [n for n in under if _covered(shape.Faces[n - 1], lines, spacing)]
                found.append(Bridge(under, covered, region.translated(App.Vector(0, 0, ceiling)), span,
                                    rating.bridge_level(span)))
    return found


def _cut(shape, z):
    """The faces where the plane at height `z` cuts `shape`, moved down into
    the plane of the bed, z 0, so faces of different layers can be compared;
    None where the kernel cannot make them."""
    cut = overhang.sections(shape, z, 0.0)
    if cut is None:
        return None
    return [face.translated(App.Vector(0, 0, -z)) for _, _, face in cut]


def _free(here, below):
    """The regions of the faces `here` that rest on none of the faces `below`;
    none where the kernel cannot cut them."""
    try:
        support = Part.makeCompound(below)
        return [region for face in here for region in face.cut(support).Faces]
    except KERNEL_ERRORS:
        return []


def _rests_on(point, below):
    return any(face.isInside(point, d.TOLERANCE, True) for face in below)


def _span(region, below, bead):
    """(span, lines, spacing) of `region` bridged from `below`: the longest
    line across it in the direction a slicer bridges in, anchored half a bead
    past each end on the supports, all lines anchored so in that direction,
    as one shape, what the slicer bridges, and how far apart they lie; None
    where no line crossing more than a bead of it is anchored so at both
    ends, or where the region is a strip narrower than a bead throughout,
    twice its area by its outline. The directions are tried in coarse steps
    first, then in fine ones round the best of them."""
    if 2 * region.Area <= bead * region.Length:
        return None
    box = region.BoundBox
    centre = box.Center
    reach = box.DiagonalLength / 2 + bead
    # A bead apart, or farther on a large region, which needs no more lines
    # to tell its directions apart.
    spacing = max(bead, 2 * reach / LINES_MOST)
    measured = {}

    def measure(degrees):
        degrees %= HALF_TURN
        if degrees not in measured:
            measured[degrees] = _anchored(region, below, bead, centre, reach, spacing, degrees)
        return measured[degrees]

    def best():
        found = [entry for entry in measured.values() if entry is not None]
        if not found:
            return None
        most = max(entry[0] for entry in found)
        return min((entry for entry in found if entry[0] >= most - COVERAGE_ALIKE * spacing), key=lambda e: e[1])

    for degrees in range(0, HALF_TURN, BRIDGE_COARSE_STEP):
        measure(degrees)
    coarse = best()
    if coarse is None:
        return None
    for offset in range(BRIDGE_FINE_STEP, BRIDGE_COARSE_STEP, BRIDGE_FINE_STEP):
        measure(coarse[2] + offset)
        measure(coarse[2] - offset)
    _, longest, _, lines = best()
    return longest, lines, spacing


def _anchored(region, below, bead, centre, reach, spacing, degrees):
    """(coverage, longest, degrees, lines) of the lines `spacing` apart
    across `region` at `degrees` that rest on `below` half a bead past both
    ends and cross more than a bead of it: their summed and their longest
    length (mm), and they, as one shape; None where none does, or the kernel
    cannot clip them."""
    turn = math.radians(degrees)
    along = App.Vector(math.cos(turn), math.sin(turn), 0)
    across = App.Vector(-along.y, along.x, 0)
    count = int(2 * reach / spacing) + 1
    lines = [Part.LineSegment(centre + across * (k * spacing - reach) - along * reach,
                              centre + across * (k * spacing - reach) + along * reach).toShape()
             for k in range(count)]
    try:
        clipped = Part.makeCompound(lines).common(region)
    except KERNEL_ERRORS:
        return None
    anchored = []
    for edge in clipped.Edges:
        if edge.Length <= bead:
            continue
        start, end = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
        outward = (end - start).normalize() * (bead / 2)
        if _rests_on(start - outward, below) and _rests_on(end + outward, below):
            anchored.append(edge)
    if not anchored:
        return None
    lengths = [edge.Length for edge in anchored]
    return sum(lengths), max(lengths), degrees, Part.makeCompound(anchored)


def _covered(face, lines, spacing):
    """Whether `lines`, the lines a bridge lays across, in the plane of the
    bed, `spacing` apart, cover `face` of the part whole, seen from above:
    its corners and every point of a grid on it within a spacing of a line.
    The rest of a free region, reaching past where the lines rest at both
    ends, hangs out unbridged: a face over it is covered in part only."""
    u0, u1, v0, v1 = face.ParameterRange
    steps = d.OVERHANG_SAMPLES
    points = [vertex.Point for vertex in face.Vertexes]
    for i in range(steps):
        for j in range(steps):
            u = u0 + (u1 - u0) * (i + 0.5) / steps
            v = v0 + (v1 - v0) * (j + 0.5) / steps
            if face.isPartOfDomain(u, v):
                points.append(face.valueAt(u, v))
    try:
        return all(lines.distToShape(Part.Vertex(App.Vector(p.x, p.y, 0)))[0] <= spacing for p in points)
    except KERNEL_ERRORS:
        return False


def _lies_over(face, region, bead):
    """Whether `face` of the part lies over `region`, a free region in the
    plane of the bed: one of its corners or its middle, seen from above,
    within half a bead of it."""
    u0, u1, v0, v1 = face.ParameterRange
    points = [vertex.Point for vertex in face.Vertexes] + [face.valueAt((u0 + u1) / 2, (v0 + v1) / 2)]
    try:
        return any(region.distToShape(Part.Vertex(App.Vector(p.x, p.y, 0)))[0] <= bead / 2 for p in points)
    except KERNEL_ERRORS:
        return False
