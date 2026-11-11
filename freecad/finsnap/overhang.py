# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Faces of a part that overhang the bed too flatly to print without support,
and islands, where it would start printing in the air, see islands().

A face overhangs where its outward normal points down. The flatter it lies,
the less the layer below carries the next one; flatter than the limit angle
from the bed it needs support. rated() rates by the two limits of the
preferences (limits.py): critical, or not printable. Faces carried by fins,
faces resting on the bed and faces smaller than the least area do not count.
A planar face has one normal; a curved one is sampled on a grid, and it lies
as flat as its flattest sample above the bed.

INPUTS this has to withstand (rated()):
  box lying on the bed                  ->  []
  face at exactly the critical limit    ->  [] (not flatter than the limit)
  same face listed as supported         ->  []
  face resting on the bed (normal down) ->  [] (the bed carries it)
  face smaller than the least area      ->  [] (corner facet of a chamfer)
  cylinder upright                      ->  []
  cylinder lying on its side            ->  the curved face
  pyramid on its base                   ->  []
  pyramid on its apex, flat sides       ->  the side faces
  roof under a T-shaped arm             ->  the roof faces
  face steeper than the critical limit  ->  not listed
  face between the two limits           ->  limits.CRITICAL
  face flatter than the unprintable
    limit                               ->  limits.UNPRINTABLE
  face at exactly a limit               ->  the level above it (not flatter)
  both limits equal                     ->  UNPRINTABLE or nothing, no CRITICAL
  unprintable limit 0                   ->  CRITICAL at most
"""

import math
from collections import namedtuple
from functools import cached_property

import FreeCAD as App
import Part

from . import defaults as d
from . import limits
from .shapes import bounds, middle_normal

# A section is the top of a thin cut-out of the part, a box this high (mm)
# reaching this far past the part all round, ending at the plane: one boolean
# cut makes its faces, holes and all, in about half the time a slice and the
# faces made from its wires take on a part of many faces.
SECTION_CUT_HEIGHT = 0.05
SECTION_CUT_MARGIN = 1.0
# Sections are compared as slabs this thick around the plane of the bed (mm):
# solids overlap reliably, faces only when they lie in one plane exactly.
SECTION_SLAB = 1.0
# What carries a point is seen in a cut of the layer below its own, at the
# middle of that layer. Where a point starts near that middle, the cut is made
# this far under it (mm), more than the tolerance by which a point below the
# middle still counts to the layer above: the cut holds nothing of what starts
# in the layer above (cut_heights()).
SUPPORT_CUT_DROP = 2 * d.TOLERANCE
# A point starting less than this above a middle (mm) counts as near it, with
# those starting below it: a margin, as right on a middle rounding decides
# whether a slice of the point shows in the cut there.
NEAR_MIDDLE = d.TOLERANCE
# A point over the bed in layers: the layer it starts to print in and the
# heights over the bed its section and what carries it are cut at.
CutHeights = namedtuple("CutHeights", "number here below")
# The top of a cut-out faces straight up, its sides sideways and its bottom
# down: a face whose normal rises more than this is one of the top.
FACING_UP = 0.5


def _normals_above(face, bed_z):
    """Outward normals of `face` at points above the bed."""
    if face.findPlane() is not None:
        return [middle_normal(face)]
    u0, u1, v0, v1 = face.ParameterRange
    # Centres of a grid of cells: the edges of the parameter range are seams
    # and the line on the bed, where the normal tells nothing.
    steps = d.OVERHANG_SAMPLES
    normals = []
    for i in range(steps):
        for j in range(steps):
            u = u0 + (u1 - u0) * (i + 0.5) / steps
            v = v0 + (v1 - v0) * (j + 0.5) / steps
            if face.isPartOfDomain(u, v) and face.valueAt(u, v).z > bed_z + d.TOLERANCE:
                normals.append(face.normalAt(u, v))
    return normals


def steepest_down(shape, supported, min_area):
    """(number, how steeply its normal points down) of each face of `shape`
    whose normal points down somewhere above the bed, as the cosine of the
    angle of the face from the bed at its flattest sample: 1 for a face
    lying flat over the bed, 0 for a vertical one. Faces resting on the bed,
    carried by fins (`supported`) or smaller than `min_area` (mm2) are left out."""
    bed_z = bounds(shape).ZMin
    found = []
    for number, face in enumerate(shape.Faces, 1):
        if bounds(face).ZMax <= bed_z + d.TOLERANCE or face.Area < min_area:
            continue
        if any(face.isSame(carried) for carried in supported):
            continue
        down = max((-n.z for n in _normals_above(face, bed_z)), default=0.0)
        if down > 0:
            found.append((number, down))
    return found


def flatter(down, limit_deg):
    """Whether a face whose normal points down `down` steeply (see
    steepest_down()) lies flatter than `limit_deg` over the bed."""
    return down > math.cos(math.radians(limit_deg)) + d.TOLERANCE


def rated(shape, supported, rating):
    """(number, level), numbers from 1, of the faces of `shape` lying flatter over the bed
    than `rating`, a limits.Limits, allows: limits.UNPRINTABLE flatter than
    its overhang_unprintable, limits.CRITICAL flatter than its
    overhang_critical only."""
    found = []
    for number, down in steepest_down(shape, supported, rating.overhang_min_area):
        if flatter(down, rating.overhang_unprintable):
            found.append((number, limits.UNPRINTABLE))
        elif flatter(down, rating.overhang_critical):
            found.append((number, limits.CRITICAL))
    return found


# An island: its lowest point, and the part there up to the top of the first
# layer that would print in the air, to show how far it reaches (an edge it
# starts on, a face); None where the kernel cannot cut that out.
Island = namedtuple("Island", "point first")


def islands(part, first_layer, layer, starts=None):
    """The Islands of `part` as it stands: where it would start printing in the
    air, as a slicer finds them. The layers are cut at their middles, the first
    `first_layer` high on the bed, every other `layer` high. A section of a
    layer rests on the one below where the two overlap; one that overlaps
    nothing there starts in the air, at its lowest point. A section beside
    another of its layer, on a foundation of its own, is no island, joined to
    it in that layer or not. Fins are no foundation: they only keep the part
    from tipping over, and a layer printed in the air does not stick to them.
    `starts`, a Starts of the part, is what bridge.bridges() of the same part
    took or will take, so both cut it at the same heights and it is meshed
    once; left out, it is worked out here.

    Only the layers holding a lowest point of the part are cut, a point of
    its mesh with no neighbour lower: an island can only start at one. A
    fault in the kernel never raises: where it cannot mesh, cut or overlap,
    no island is said there, so the fins are built all the same.

    INPUTS this has to withstand:
      box lying on the bed                  ->  []
      box standing on an edge               ->  [] (the edge is on the bed)
      block hanging under a bridge, above
        the bed                             ->  its lowest point
      mushroom, the cap wider than its stem ->  [] (the cap rests on the stem)
      ridge pointing down under a bridge    ->  one point on the ridge
      box with a hole through it, lying     ->  [] (the top of the hole is no lowest point)
      lowest point in the first layer       ->  [] (the bed carries it)
      lowest points of one island           ->  one island, at the first found
      two blocks hanging side by side       ->  two islands
      an empty shape, a part the kernel
        cannot mesh, or a layer it cannot
        cut or overlap                      ->  no island said there
    """
    if part.isNull():
        return []
    starts = starts or Starts(part)
    bed = starts.bed
    cut = {}
    # Whether each section, by layer and number, rests on the layer below;
    # one that does not is an island, reported once, at its first lowest point.
    resting = {}
    found = []
    cuts = cut_heights(starts.heights, first_layer, layer)
    for point in starts.points:
        at = cuts[point.z - bed]
        if at is None:
            continue
        here, below = bed + at.here, bed + at.below
        for z in (here, below):
            if z not in cut:
                cut[z] = sections(part, z, layer)
        if cut[here] is None or cut[below] is None:
            continue
        # The sections lie in the plane of the bed, see sections().
        middle = Part.Vertex(App.Vector(point.x, point.y, 0))
        for index, (section, reach, outline) in enumerate(cut[here]):
            key = (at.number, index)
            # A section decided before is passed over, and the box around one
            # turns most points away before the distance to it is measured.
            if key in resting or not reach.isInside(middle.Point):
                continue
            try:
                if section.distToShape(middle)[0] > layer:
                    continue
                resting[key] = any(_overlap(section, other) for other, _, _ in cut[below])
            except Part.OCCError:
                resting[key] = True
            if not resting[key]:
                found.append(Island(App.Vector(point), _first_layer(part, outline, point.z, here + layer / 2)))
    return found


def _first_layer(part, outline, bottom, top):
    """The part from `bottom`, the lowest point of an island, up to `top`, the
    top of its first layer, within `outline`, the face where the middle of
    that layer cuts it; None where the kernel cannot cut it out."""
    try:
        footprint = outline.translated(App.Vector(0, 0, bottom - d.TOLERANCE - outline.BoundBox.ZMin))
        piece = part.common(footprint.extrude(App.Vector(0, 0, top - bottom + d.TOLERANCE)))
    except Part.OCCError:
        return None
    return piece if piece.Volume > 0 else None


def layer_middle(number, first_layer, layer):
    """Height of the middle of layer `number` (from 0, the first) over the bed."""
    return first_layer / 2 if number == 0 else first_layer + (number - 0.5) * layer


def layer_of(height, first_layer, layer):
    """The layer (from 0, the first) a point `height` over the bed starts to
    print in: it counts to a layer from the tolerance below the middle of the
    layer before. The first layer alone is told apart the other way: what
    starts up to its middle, the tolerance above it included, lies in it and
    on the bed, as there is no layer below to carry it.

    INPUTS this has to withstand (first layer 0.2, layers 0.2):
      on the bed, up to the middle of the
        first layer and the tolerance more  ->  0
      between two middles, 0.25             ->  1
      right on the middle of layer 1, 0.3   ->  2
      within the tolerance below it         ->  2
      right at the tolerance below it       ->  1 or 2, as the rounding falls: both
                                                hold (cut_heights())
      more than the tolerance below it      ->  1
      just above it, 0.31                   ->  2
    """
    if height <= first_layer / 2 + d.TOLERANCE:
        return 0
    return max(1, math.floor((height - first_layer + d.TOLERANCE) / layer + 0.5) + 1)


class Starts:
    """Where something of a shape starts to print: worked out once, and only
    when asked for, so islands() and bridges() of the same shape share it and
    cut its layers at the same heights.

    INPUTS this has to withstand:
      a shape with lowest points            ->  its points, and their heights among
                                                the heights
      a face whose lowest line is no lowest
        point, as the ceiling of a pocket
        open downwards                      ->  its height among the heights as well
      a shape the kernel cannot mesh        ->  no points; the heights of its faces
      heights asked for, the points never   ->  the shape is meshed all the same: what
                                                starts in a layer decides how it is cut
      nothing asked for                     ->  nothing worked out but the bed
    """

    def __init__(self, shape):
        self.shape = shape
        # Height of the bed: the lowest of the shape.
        self.bed = bounds(shape).ZMin

    @cached_property
    def points(self):
        """The lowest points of the shape, where an island can start."""
        return _lowest_points(self.shape)

    @cached_property
    def heights(self):
        """The heights over the bed at which something starts: those of the
        lowest points and of the lowest line of every face. A face that ends
        there instead, as a top, is one too many and does no harm: it may
        only have a layer cut lower than it had to be."""
        return ([point.z - self.bed for point in self.points]
                + [bounds(face).ZMin - self.bed for face in self.shape.Faces])


def cut_heights(starts, first_layer, layer):
    """The heights the layers are cut at in which the points `starts` over
    the bed start to print, by each of those heights, as a CutHeights: the
    layer (layer_of()), the height over the bed its section is cut at,
    `here`, and the height the layer below is cut at to see what carries it,
    `below`; None for a height in the first layer, which the bed carries.
    `starts` has to hold every start of the part (Starts.heights): what
    starts in a layer decides how its support is cut, and a height not among
    them is not answered.

    A cut holds what lies below its plane (layer_faces()). `here` is the
    middle of the layer. `below` is the middle of the layer below, the cut
    that layer is cut at itself, so one cut serves both. Only where a point
    of the layer starts below that middle, the cut there holds a slice of it
    and it would carry itself; so with a point starting less than NEAR_MIDDLE
    above the middle, `below` lies SUPPORT_CUT_DROP under it, for the whole
    layer: all that starts in one layer is cut at the same two heights.

    INPUTS this has to withstand (first layer 0.2, layers 0.2):
      no starts                             ->  {}
      a start in the first layer            ->  None for it
      one start well above the middle
        below it, 0.45                      ->  layer 2: here 0.5, below 0.3, the cut
                                                layer 1 is cut at as well
      right on the middle below it, 0.3     ->  layer 2: below 0.3 less the drop
      within the tolerance below that
        middle, or less than NEAR_MIDDLE
        above it                            ->  the same, below less the drop
      right at NEAR_MIDDLE above it         ->  below at the middle or the drop under it,
                                                as the rounding falls: both hold, the
                                                start lies that far above either
      right at the tolerance below it       ->  layer 1 or 2, as the rounding falls: both
                                                hold, its slice at 0.3 is as thick as the
                                                tolerance, and the drop is more
      two starts in one layer, one near
        the middle below, one well above    ->  both the same, below less the drop: one
                                                decision for the layer
      the same height twice                 ->  answered once
      starts in neighbouring layers, none
        near a middle                       ->  below of the upper is here of the lower,
                                                the very same number, so one cut serves both
      starts in layer 1                     ->  below is the middle of the first layer,
                                                never lower: what starts within the
                                                tolerance of it lies in the first layer
    """
    # Each height's layer worked out once, so a height is in one layer throughout.
    layers = {height: layer_of(height, first_layer, layer) for height in starts}
    near = {number for height, number in layers.items()
            if number and height < layer_middle(number - 1, first_layer, layer) + NEAR_MIDDLE}

    def cuts(number):
        support = layer_middle(number - 1, first_layer, layer)
        return CutHeights(number, layer_middle(number, first_layer, layer),
                          support - SUPPORT_CUT_DROP if number in near else support)

    by_layer = {number: cuts(number) for number in set(layers.values()) if number}
    return {height: by_layer.get(number) for height, number in layers.items()}


def _lowest_points(shape):
    """The points of the mesh of `shape` with no neighbour lower; none where
    the kernel cannot mesh it."""
    try:
        points, triangles = shape.tessellate(d.ISLAND_MESH_DEFLECTION)
    except Part.OCCError:
        return []
    neighbours = [set() for _ in points]
    for triangle in triangles:
        for corner in triangle:
            neighbours[corner].update(triangle)
    return [point for corner, point in enumerate(points)
            if all(points[other].z >= point.z for other in neighbours[corner])]


def layer_faces(shape, z):
    """The faces where the plane at height `z` cuts `shape`, holes and all:
    the top of a thin cut-out of it ending at the plane, see
    SECTION_CUT_HEIGHT. A face of the part lying in the plane is cut whole.
    None where the kernel cannot make them.

    INPUTS this has to withstand:
      the plane through the part            ->  the faces of the cut, holes and all
      a face of the part lying in the plane ->  cut whole
      what starts right on the plane, or
        above it                            ->  not in the cut
      what starts just below the plane,
        a slice of any thickness            ->  its top alone: the sides and the
                                                underside of a thin slice lie as near
                                                the plane, and are no part of the cut
      a part that is a shell, no solid      ->  [], as it has no inside to cut
      the plane above or below the part     ->  []
      a cut the kernel cannot make          ->  None
    """
    box = bounds(shape)

    def on_top(face):
        return (abs(face.BoundBox.ZMin - z) < d.TOLERANCE and face.BoundBox.ZLength < d.TOLERANCE
                and middle_normal(face).z > FACING_UP)

    try:
        cutter = Part.makeBox(box.XLength + 2 * SECTION_CUT_MARGIN, box.YLength + 2 * SECTION_CUT_MARGIN,
                              SECTION_CUT_HEIGHT, App.Vector(box.XMin - SECTION_CUT_MARGIN,
                                                             box.YMin - SECTION_CUT_MARGIN, z - SECTION_CUT_HEIGHT))
        return [face for face in shape.common(cutter).Faces if on_top(face)]
    except Part.OCCError:
        return None


def sections(shape, z, reach):
    """Where the plane at height `z` cuts `shape` (layer_faces()), one slab
    SECTION_SLAB thick for each face of the cut, around the plane of the bed,
    z 0, so sections of different layers can be overlapped, each with its
    bounding box grown by `reach` (mm) and the face of the cut where it lies;
    None where the kernel cannot make them."""
    faces = layer_faces(shape, z)
    if not faces:
        return faces
    try:
        bottom = App.Vector(0, 0, -z - SECTION_SLAB / 2)
        slabs = [face.translated(bottom).extrude(App.Vector(0, 0, SECTION_SLAB)) for face in faces]
    except Part.OCCError:
        return None
    found = []
    for slab, face in zip(slabs, faces):
        box = App.BoundBox(slab.BoundBox)
        box.enlarge(reach)
        found.append((slab, box, face))
    return found


def _overlap(first, second):
    """Whether two sections, slabs from sections(), overlap, more than touch."""
    if not first.BoundBox.intersect(second.BoundBox):
        return False
    return first.common(second).Volume > d.ISLAND_MIN_OVERLAP * SECTION_SLAB
