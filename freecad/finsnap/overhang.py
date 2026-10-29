# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Faces of a part that overhang the bed too flatly to print without support,
and islands, where it would start printing in the air, see part_islands().

A face overhangs where its outward normal points down. The flatter it lies,
the less the layer below carries the next one; below OVERHANG_ANGLE against
the bed it needs support. Faces carried by fins, faces resting on the bed and
tiny faces do not count. A planar face has one normal; a curved one is sampled on a grid,
and it overhangs if any sample above the bed does.

INPUTS this has to withstand (overhangs()):
  box lying on the bed                  ->  []
  face at exactly the limit angle       ->  [] (not flatter than the limit)
  face flatter than the limit, above
    the bed                             ->  its number
  same face listed as supported         ->  []
  face resting on the bed (normal down) ->  [] (the bed carries it)
  face smaller than OVERHANG_MIN_AREA   ->  [] (corner facet of a chamfer)
  cylinder upright                      ->  []
  cylinder lying on its side            ->  the curved face
  pyramid on its base                   ->  []
  pyramid on its apex, flat sides       ->  the side faces
  roof under a T-shaped arm             ->  the roof faces
"""

import math
from collections import namedtuple

import FreeCAD as App
import Part

from . import defaults as d
from .shapes import bounds, middle_normal

# Turns the wires of a section into faces, holes inside their outlines.
FACE_MAKER = "Part::FaceMakerBullseye"
# Sections are compared as slabs this thick around the plane of the bed (mm):
# solids overlap reliably, faces only when they lie in one plane exactly.
SECTION_SLAB = 1.0


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


def overhangs(shape, supported=(), limit_deg=d.OVERHANG_ANGLE):
    """Numbers (1-based) of the faces of `shape` lying flatter than limit_deg over the bed."""
    bed_z = bounds(shape).ZMin
    # A face lies flatter than the limit when its normal points down more
    # steeply than the normal of a face at the limit.
    steepest = math.cos(math.radians(limit_deg))
    found = []
    for number, face in enumerate(shape.Faces, 1):
        if bounds(face).ZMax <= bed_z + d.TOLERANCE or face.Area < d.OVERHANG_MIN_AREA:
            continue
        if any(face.isSame(carried) for carried in supported):
            continue
        if any(-n.z > steepest + d.TOLERANCE for n in _normals_above(face, bed_z)):
            found.append(number)
    return found
# An island of a part alone: its lowest point, the layer (from 0, the first)
# it starts in and the section of the part there around it, for islands() to
# look under for fins.
Island = namedtuple("Island", "point layer section")


def part_islands(part, first_layer, layer):
    """The islands of `part` as it stands, without fins, as Islands: where it
    would start printing in the air, as a slicer finds it. The layers are cut
    at their middles, the first `first_layer` high on the bed, every other
    `layer` high. A section of a layer rests on the one below where the two
    overlap; one that overlaps nothing there starts in the air, at its lowest
    point. A section beside another of its layer, on a foundation of its own,
    is no island, joined to it in that layer or not.

    Only the layers holding a lowest point of the part are cut, a point of
    its mesh with no neighbour lower: an island can only start at one.

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
      a layer the kernel cannot cut         ->  no island said there
    """
    bed = bounds(part).ZMin
    cut = {}
    # Whether each section, by layer and number, rests on the layer below.
    resting = {}
    # The sections reported: one island each, at the first of its lowest points.
    reported = set()
    found = []
    for point in _lowest_points(part):
        number = _layer_holding(point.z - bed, first_layer, layer)
        if number == 0:
            continue
        for key in (number, number - 1):
            if key not in cut:
                cut[key] = _sections([part], bed + _layer_middle(key, first_layer, layer))
        if cut[number] is None or cut[number - 1] is None:
            continue
        # The sections lie in the plane of the bed, see _sections().
        middle = Part.Vertex(App.Vector(point.x, point.y, 0))
        for index, section in enumerate(cut[number]):
            if section.distToShape(middle)[0] > layer:
                continue
            if (number, index) not in resting:
                resting[number, index] = _rests_on(section, cut[number - 1])
            if not resting[number, index] and (number, index) not in reported:
                reported.add((number, index))
                found.append(Island(App.Vector(point), number, section))
    return found


def islands(part, carriers, first_layer, layer, alone=None):
    """The lowest points of the islands of `part` that the fins `carriers`,
    standing beside it on the bed, do not carry either: an island rests on
    them where its section overlaps theirs in the layer below. `alone` is
    part_islands() of the part, if worked out before; the fins change more
    often than the part.

    INPUTS this has to withstand:
      no islands                            ->  []
      an island over a fin                  ->  [] (the fin is its foundation)
      an island beside a fin                ->  its point
      no carriers                           ->  every island of the part
      a layer of the fins the kernel cannot
        cut                                 ->  the island stays
    """
    if alone is None:
        alone = part_islands(part, first_layer, layer)
    bed = bounds(part).ZMin
    shapes = [carrier for carrier in carriers if carrier is not None]
    left = []
    for island in alone:
        below = _sections(shapes, bed + _layer_middle(island.layer - 1, first_layer, layer)) if shapes else []
        if not below or not _rests_on(island.section, below):
            left.append(island.point)
    return left


def _rests_on(section, below):
    """Whether `section` of a layer overlaps one of the sections `below` of the
    layer under it."""
    return any(_overlap(section, other) for other in below)


def _layer_middle(number, first_layer, layer):
    """Height of the middle of layer `number` (from 0, the first) over the bed."""
    return first_layer / 2 if number == 0 else first_layer + (number - 0.5) * layer


def _layer_holding(height, first_layer, layer):
    """The layer (from 0) a point `height` over the bed is printed in first:
    the lowest one whose middle lies no lower than the point."""
    if height <= first_layer / 2 + d.TOLERANCE:
        return 0
    return max(1, math.ceil((height - first_layer) / layer + 0.5 - d.TOLERANCE / layer))


def _lowest_points(shape):
    """The points of the mesh of `shape` with no neighbour lower."""
    points, triangles = shape.tessellate(d.ISLAND_MESH_DEFLECTION)
    neighbours = [set() for _ in points]
    for triangle in triangles:
        for corner in triangle:
            neighbours[corner].update(triangle)
    return [point for corner, point in enumerate(points)
            if all(points[other].z >= point.z for other in neighbours[corner])]


def _sections(shapes, z):
    """Where the plane at height `z` cuts `shapes`, one slab SECTION_SLAB thick
    for each face of the cut, around the plane of the bed, z 0, so sections of
    different layers can be overlapped; None where the kernel cannot make
    them."""
    faces = []
    for shape in shapes:
        wires = shape.slice(App.Vector(0, 0, 1), z)
        if not wires:
            continue
        try:
            bottom = App.Vector(0, 0, -z - SECTION_SLAB / 2)
            faces.extend(face.translated(bottom).extrude(App.Vector(0, 0, SECTION_SLAB))
                         for face in Part.makeFace(wires, FACE_MAKER).Faces)
        except Part.OCCError:
            return None
    return faces


def _overlap(first, second):
    """Whether two sections, slabs from _sections(), overlap, more than touch."""
    if not first.BoundBox.intersect(second.BoundBox):
        return False
    return first.common(second).Volume > d.ISLAND_MIN_OVERLAP * SECTION_SLAB
