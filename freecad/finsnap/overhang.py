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

import FreeCAD as App
import Part

from . import defaults as d
from . import limits
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


def islands(part, first_layer, layer):
    """The Islands of `part` as it stands: where it would start printing in the
    air, as a slicer finds them. The layers are cut at their middles, the first
    `first_layer` high on the bed, every other `layer` high. A section of a
    layer rests on the one below where the two overlap; one that overlaps
    nothing there starts in the air, at its lowest point. A section beside
    another of its layer, on a foundation of its own, is no island, joined to
    it in that layer or not. Fins are no foundation: they only keep the part
    from tipping over, and a layer printed in the air does not stick to them.

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
    bed = bounds(part).ZMin
    cut = {}
    # Whether each section, by layer and number, rests on the layer below;
    # one that does not is an island, reported once, at its first lowest point.
    resting = {}
    found = []
    for point in _lowest_points(part):
        number = layer_holding(point.z - bed, first_layer, layer)
        if number == 0:
            continue
        for key in (number, number - 1):
            if key not in cut:
                cut[key] = sections(part, bed + layer_middle(key, first_layer, layer), layer)
        if cut[number] is None or cut[number - 1] is None:
            continue
        # The sections lie in the plane of the bed, see sections().
        middle = Part.Vertex(App.Vector(point.x, point.y, 0))
        for index, (section, reach, outline) in enumerate(cut[number]):
            key = (number, index)
            # A section decided before is passed over, and the box around one
            # turns most points away before the distance to it is measured.
            if key in resting or not reach.isInside(middle.Point):
                continue
            try:
                if section.distToShape(middle)[0] > layer:
                    continue
                resting[key] = any(_overlap(section, other) for other, _, _ in cut[number - 1])
            except Part.OCCError:
                resting[key] = True
            if not resting[key]:
                top = bed + layer_middle(number, first_layer, layer) + layer / 2
                found.append(Island(App.Vector(point), _first_layer(part, outline, point.z, top)))
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


def layer_holding(height, first_layer, layer):
    """The layer (from 0) a point `height` over the bed is printed in first:
    the lowest one whose middle lies no lower than the point."""
    if height <= first_layer / 2 + d.TOLERANCE:
        return 0
    return max(1, math.ceil((height - first_layer) / layer + 0.5 - d.TOLERANCE / layer))


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


def sections(shape, z, reach):
    """Where the plane at height `z` cuts `shape`, one slab SECTION_SLAB thick
    for each face of the cut, around the plane of the bed, z 0, so sections of
    different layers can be overlapped, each with its bounding box grown by
    `reach` (mm) and the face of the cut where it lies; None where the kernel
    cannot make them."""
    try:
        wires = shape.slice(App.Vector(0, 0, 1), z)
        if not wires:
            return []
        bottom = App.Vector(0, 0, -z - SECTION_SLAB / 2)
        faces = Part.makeFace(wires, FACE_MAKER).Faces
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
