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
distances measured. The lines are not cut out of the region by the kernel
either, a cut for every direction tried: its outline and those of the
supports are taken once, in straight pieces, and the lines laid by
arithmetic on them.

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

import numpy

import FreeCAD as App
import Part

from . import defaults as d
from . import overhang

# The directions lines are laid across a free region in, over half a turn, a
# line having no sense: this far apart (degrees) first, then this far round
# the best of them. At most this many lines are laid in one direction.
BRIDGE_COARSE_STEP = 15
BRIDGE_FINE_STEP = 5
HALF_TURN = 180
LINES_MOST = 40
# Two directions covering within this many line spacings as much count as alike.
COVERAGE_ALIKE = 1.0
# The lines are laid by arithmetic on the outline of a region, its curved
# sides taken in straight pieces no farther off than the bead width by this.
OUTLINE_FINENESS = 50

# What the kernel raises where it cannot cut or clip a region.
KERNEL_ERRORS = (Part.OCCError, App.Base.CADKernelError)
# A bridge: the numbers (from 1) of the faces of the part it lies under, those
# of them it covers whole, the free region of its first layer at the height of
# the lowest of them, where it shows on the underside of the part, its span
# (mm) and its level, limits.GOOD, CRITICAL or UNPRINTABLE. A face covered in
# part reaches past the bridge, overhanging there.
Bridge = namedtuple("Bridge", "faces covered region span level")


def bridges(shape, first_layer, layer, bead, rating, supported=(), starts=None):
    """The Bridges of `shape` as it stands, printed in layers `first_layer`
    high on the bed, every other `layer` high, in beads `bead` wide, rated by
    `rating`, a limits.Limits. Faces in `supported`, carried by fins, span
    nothing. `starts`, an overhang.Starts of the shape as it stands, is what
    islands() of it took or will take, so both cut it at the same heights,
    its faces are sampled once and it is meshed once; left out, it is worked
    out here.

    INPUTS this has to withstand:
      an empty shape                        ->  [], nothing asked of it
      no face hanging flatter than the
        critical angle                      ->  [], the shape neither meshed nor cut
      faces hanging in several layers       ->  each layer and what carries it cut once
      a layer the kernel cannot cut         ->  no bridge said there
      `starts` of another copy of the
        shape as it stands                  ->  as of this one: its faces by number, its
                                                heights by layer
    """
    if shape.isNull():
        return []
    starts = starts or overhang.Starts(shape)
    hanging = [number for number, down in
               overhang.steepest_down(shape, supported, rating.overhang_min_area, starts.down)
               if overhang.flatter(down, rating.overhang_critical)]
    if not hanging:
        return []
    bed = starts.bed
    # How a layer is cut depends on all that starts in it, not on these faces alone.
    cuts = overhang.LayerCuts(starts.heights, first_layer, layer)
    starting = {}
    for number in hanging:
        at = cuts.at(starts.lowest[number])
        if at is not None:
            starting.setdefault(at, []).append(number)
    found = []
    # Each height cut once: the cut of one layer is mostly what carries the next.
    made = {}

    def cut(z):
        if z not in made:
            made[z] = _cut(shape, z)
        return made[z]

    for at, numbers in sorted(starting.items()):
        here, below = cut(bed + at.here), cut(bed + at.below)
        if not here or not below:
            continue
        for region in _free(here, below):
            bridged = _span(region, below, bead)
            if bridged is None:
                continue
            span, lines, spacing = bridged
            under = [n for n in numbers if _lies_over(shape.Faces[n - 1], region, bead)]
            if under:
                ceiling = bed + min(starts.lowest[n] for n in under)
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


def _outline(face, bead):
    """The outline of `face`, a face in the plane of the bed, its outer ring
    and its holes, as (starts, ends), an (n, 2) array each of the ends of its
    straight pieces. Curved sides are taken in pieces no farther off than
    the bead by OUTLINE_FINENESS. Each ring is closed on its first point: the
    kernel gives the last a rounding beside it, and a line through that gap
    would cross nothing there. What the kernel raises passes on.

    INPUTS this has to withstand:
      a face with straight sides            ->  its corners
      a face with curved sides              ->  points on them, no farther off than said
      a face with holes                     ->  the pieces of every ring, all in one
      a ring whose last point misses its
        first by a rounding                 ->  closed on the first
      a ring the kernel gives open, its
        ends apart                          ->  closed by a piece from the last to the first
    """
    starts, ends = [], []
    for wire in face.Wires:
        ring = numpy.array([(point.x, point.y) for point in wire.discretize(Deflection=bead / OUTLINE_FINENESS)])
        if numpy.hypot(*(ring[-1] - ring[0])) <= d.TOLERANCE:
            ring[-1] = ring[0]
        else:
            ring = numpy.vstack([ring, ring[:1]])
        starts.append(ring[:-1])
        ends.append(ring[1:])
    return numpy.concatenate(starts), numpy.concatenate(ends)


def _inside(points, outline, slack):
    """Whether each of `points`, (k, 2), lies in the face outlined by
    `outline` (_outline()), or within `slack` (mm) of its outline.

    A point lies in the face where a ray from it crosses the outline an odd
    number of times, over all its rings. A piece of the outline counts as
    crossed where one of its ends lies above the ray and the other on it or
    below, so a corner the ray runs through counts once, and one it only
    touches twice or not at all.

    INPUTS this has to withstand:
      a point inside the face               ->  True
      a point outside it                    ->  False
      a point in a hole of it               ->  False
      a point on the outline, or within the
        slack of it, inside or out          ->  True
      a ray through a corner of the outline ->  the corner counted once
      a ray along a side                    ->  that side not crossed
    """
    starts, ends = outline
    px, py = points[:, 0:1], points[:, 1:2]
    ax, ay, bx, by = starts[:, 0], starts[:, 1], ends[:, 0], ends[:, 1]
    crossed = (ay > py) != (by > py)
    # Where the piece meets the height of the ray; a piece along it is not crossed.
    with numpy.errstate(divide="ignore", invalid="ignore"):
        at = ax + (py - ay) * (bx - ax) / (by - ay)
    odd = (crossed & (at > px)).sum(axis=1) % 2 == 1
    dx, dy = bx - ax, by - ay
    with numpy.errstate(divide="ignore", invalid="ignore"):
        along = numpy.nan_to_num(((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy))
    along = numpy.clip(along, 0.0, 1.0)
    near = numpy.hypot(px - (ax + along * dx), py - (ay + along * dy)).min(axis=1) <= slack
    return odd | near


def _pieces(outline, centre, reach, spacing, degrees):
    """The pieces inside the region outlined by `outline` of the lines
    `spacing` apart across it at `degrees`, laid from `reach` to one side of
    `centre`, an (x, y) pair, to as far on the other: (m, 3), a row for each
    piece of how far its line lies across, and where along it the piece
    starts and ends; with the directions along and across, a unit vector each.

    A line is inside the region between its first and second crossing of
    the outline, its third and fourth, and so on. A piece of the outline
    counts as crossed where one of its ends lies above the line and the
    other on it or below.

    INPUTS this has to withstand:
      a region with straight sides          ->  the pieces of the lines inside it
      a region with curved sides            ->  the same, a piece ending as far off as the
                                                outline is taken (_outline())
      a region with holes                   ->  a line stops at a hole and goes on past it,
                                                a piece each side
      a line through a corner of the
        outline, the outline going on
        across it                           ->  the corner one crossing
      a line touching the outline at a
        corner only                         ->  no crossing, or two at one place: a piece
                                                of no length, which no caller keeps
      a line lying along a side             ->  that side no crossing: a piece along it
                                                or none, as the rounding of the line
                                                falls, either way no longer than the
                                                pieces of the lines beside it
      a line past the region                ->  no piece of it
    """
    turn = math.radians(degrees)
    along = numpy.array((math.cos(turn), math.sin(turn)))
    across = numpy.array((-along[1], along[0]))
    count = int(2 * reach / spacing) + 1
    offsets = numpy.arange(count) * spacing - reach + numpy.dot(centre, across)
    starts, ends = outline
    above_start = starts.dot(across)[None, :] - offsets[:, None]
    above_end = ends.dot(across)[None, :] - offsets[:, None]
    crossed = (above_start > 0) != (above_end > 0)
    from_start, to_end = starts.dot(along), ends.dot(along)
    with numpy.errstate(divide="ignore", invalid="ignore"):
        at = from_start[None, :] + (to_end - from_start)[None, :] * above_start / (above_start - above_end)
    pieces = []
    for line in range(count):
        crossings = numpy.sort(at[line][crossed[line]])
        pieces.extend((offsets[line], first, last) for first, last in zip(crossings[0::2], crossings[1::2]))
    return numpy.array(pieces).reshape(-1, 3), along, across


def _span(region, below, bead):
    """(span, lines, spacing) of `region` bridged from `below`: the longest
    line across it in the direction a slicer bridges in, anchored half a bead
    past each end on the supports, all lines anchored so in that direction,
    as (m, 2, 2), the two ends of each, what the slicer bridges, and how far
    apart they lie; None where no line crossing more than a bead of it is
    anchored so at both ends, where the region is a strip narrower than a
    bead throughout, twice its area by its outline, or where the kernel
    cannot give an outline. The directions are tried in coarse steps first,
    then in fine ones round the best of them."""
    if 2 * region.Area <= bead * region.Length:
        return None
    try:
        outline = _outline(region, bead)
        supports = [_outline(face, bead) for face in below]
    except KERNEL_ERRORS:
        return None
    box = region.BoundBox
    centre = (box.Center.x, box.Center.y)
    reach = box.DiagonalLength / 2 + bead
    # A bead apart, or farther on a large region, which needs no more lines
    # to tell its directions apart.
    spacing = max(bead, 2 * reach / LINES_MOST)
    measured = {}

    def measure(degrees):
        degrees %= HALF_TURN
        if degrees not in measured:
            measured[degrees] = _anchored(outline, supports, bead, centre, reach, spacing, degrees)
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


def _anchored(outline, supports, bead, centre, reach, spacing, degrees):
    """(coverage, longest, degrees, lines) of the lines `spacing` apart
    across the region outlined by `outline` at `degrees` (_pieces()) that
    rest on `supports`, the outlines of the faces below, half a bead past
    both ends and cross more than a bead of it: their summed and their
    longest length (mm), and they, as (m, 2, 2), the two ends of each; None
    where none does.

    An end rests where the point half a bead past it lies in one of the
    supports, or within the tolerance of its outline and, as the outlines
    of region and support are taken in pieces each on its own, as much more
    as a curved one may be off.

    INPUTS this has to withstand:
      a piece no longer than a bead         ->  left out
      a piece both of whose ends, half a
        bead on, lie in a support           ->  kept
      an end, half a bead on, over nothing,
        or over a hole of a support         ->  the piece left out
      an end within the tolerance of the
        outline of a support, and as much
        more as a curved outline is off     ->  it rests
      several supports, the ends of a piece
        on two of them                      ->  kept: each end rests on any of them
      no support below                      ->  None
      no piece anchored at both ends        ->  None
    """
    pieces, along, across = _pieces(outline, centre, reach, spacing, degrees)
    pieces = pieces[pieces[:, 2] - pieces[:, 1] > bead]
    if not len(pieces) or not supports:
        return None
    foot = pieces[:, 0:1] * across[None, :]
    ends = (foot + (pieces[:, 1:2] - bead / 2) * along[None, :], foot + (pieces[:, 2:3] + bead / 2) * along[None, :])
    slack = d.TOLERANCE + bead / OUTLINE_FINENESS
    rests = [numpy.zeros(len(pieces), dtype=bool) for _ in ends]
    for support in supports:
        for at_end, points in zip(rests, ends):
            at_end |= _inside(points, support, slack)
    pieces = pieces[rests[0] & rests[1]]
    if not len(pieces):
        return None
    foot = pieces[:, 0:1] * across[None, :]
    lines = numpy.stack([foot + pieces[:, 1:2] * along[None, :], foot + pieces[:, 2:3] * along[None, :]], axis=1)
    lengths = pieces[:, 2] - pieces[:, 1]
    return float(lengths.sum()), float(lengths.max()), degrees, lines


def _covered(face, lines, spacing):
    """Whether `lines`, the lines a bridge lays across, in the plane of the
    bed, as (m, 2, 2), the two ends of each, `spacing` apart, cover `face` of
    the part whole, seen from above: its corners and every point of a grid
    on it within a spacing of a line. The rest of a free region, reaching
    past where the lines rest at both ends, hangs out unbridged: a face over
    it is covered in part only.

    INPUTS this has to withstand:
      every corner and point of the grid
        within a spacing of a line          ->  True
      one of them farther from every line   ->  False
      no line                               ->  False
    """
    if not len(lines):
        return False
    u0, u1, v0, v1 = face.ParameterRange
    steps = d.OVERHANG_SAMPLES
    points = [vertex.Point for vertex in face.Vertexes]
    for i in range(steps):
        for j in range(steps):
            u = u0 + (u1 - u0) * (i + 0.5) / steps
            v = v0 + (v1 - v0) * (j + 0.5) / steps
            if face.isPartOfDomain(u, v):
                points.append(face.valueAt(u, v))
    px = numpy.array([point.x for point in points])[:, None]
    py = numpy.array([point.y for point in points])[:, None]
    ax, ay = lines[:, 0, 0], lines[:, 0, 1]
    dx, dy = lines[:, 1, 0] - ax, lines[:, 1, 1] - ay
    # The nearest point of each line to each point, between its ends; a line is longer than a bead.
    along = numpy.clip(((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy), 0.0, 1.0)
    return bool((numpy.hypot(px - (ax + along * dx), py - (ay + along * dy)).min(axis=1) <= spacing).all())


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
