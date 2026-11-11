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
# in the layer above (LayerCuts).
SUPPORT_CUT_DROP = 2 * d.TOLERANCE
# A point starting less than this above a middle (mm) counts as near it, with
# those starting below it: a margin, as right on a middle rounding decides
# whether a slice of the point shows in the cut there.
NEAR_MIDDLE = d.TOLERANCE
# How far below the height from which a point counts to the layer above (mm)
# a point still has what carries that layer cut lower: far more than rounding
# moves a height between two copies of a part, far less than the tolerance.
LAYER_EDGE = d.TOLERANCE / 10
# A point over the bed in layers: the layer it starts to print in and the
# heights over the bed its section and what carries it are cut at.
CutHeights = namedtuple("CutHeights", "number here below")
# The top of a cut-out faces straight up, its sides sideways and its bottom
# down: a face whose normal rises more than this is one of the top.
FACING_UP = 0.5
# A face faces down where its normal sinks more than this, the cosine of its
# angle from the bed: less is an upright wall a rounding off the vertical.
FACING_DOWN = 1e-4


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


def facing_down(shape, wanted=None):
    """(number, how steeply its normal points down) of each face of `shape`
    whose normal points down somewhere above the bed, as the cosine of the
    angle of the face from the bed at its flattest sample: 1 for a face
    lying flat over the bed, 0 for a vertical one, which is left out, as is
    one a rounding off the vertical. Faces resting on the bed are left out,
    and those `wanted`, called with the face, turns away, before they are
    sampled."""
    bed_z = bounds(shape).ZMin
    found = []
    for number, face in enumerate(shape.Faces, 1):
        if bounds(face).ZMax <= bed_z + d.TOLERANCE or (wanted is not None and not wanted(face)):
            continue
        down = max((-n.z for n in _normals_above(face, bed_z)), default=0.0)
        if down > FACING_DOWN:
            found.append((number, down))
    return found


def steepest_down(shape, supported, min_area, down=None):
    """The faces of `shape` facing down somewhere (facing_down()) without
    those carried by fins (`supported`) or smaller than `min_area` (mm2).
    `down` is facing_down() of the shape as it stands, where it was worked
    out before (Starts.down), so the faces are not sampled again."""
    def wanted(face):
        return face.Area >= min_area and not any(face.isSame(carried) for carried in supported)

    if down is None:
        return facing_down(shape, wanted)
    faces = shape.Faces
    return [(number, steep) for number, steep in down if wanted(faces[number - 1])]


def flatter(down, limit_deg):
    """Whether a face whose normal points down `down` steeply (see
    steepest_down()) lies flatter than `limit_deg` over the bed."""
    return down > math.cos(math.radians(limit_deg)) + d.TOLERANCE


def rated(shape, supported, rating, down=None):
    """(number, level), numbers from 1, of the faces of `shape` lying flatter over the bed
    than `rating`, a limits.Limits, allows: limits.UNPRINTABLE flatter than
    its overhang_unprintable, limits.CRITICAL flatter than its
    overhang_critical only. `down` as for steepest_down()."""
    found = []
    for number, steep in steepest_down(shape, supported, rating.overhang_min_area, down):
        if flatter(steep, rating.overhang_unprintable):
            found.append((number, limits.UNPRINTABLE))
        elif flatter(steep, rating.overhang_critical):
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
    cuts = LayerCuts(starts.heights, first_layer, layer)
    for point in starts.points:
        at = cuts.at(point.z - bed)
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
                                                hold (LayerCuts)
      more than the tolerance below it      ->  1
      just above it, 0.31                   ->  2
    """
    if height <= first_layer / 2 + d.TOLERANCE:
        return 0
    return max(1, math.floor((height - first_layer + d.TOLERANCE) / layer + 0.5) + 1)


class Starts:
    """Where something of a shape starts to print, for rated(), islands() and
    bridge.bridges() of the same shape to share: plain numbers and points,
    each worked out once and only when asked for. Kept with a part as it
    stands, it holds no shape: the shape is lent for a check (lend()) and
    let go of after it (let_go()), and what was worked out serves any copy
    of the part as it stands.

    INPUTS this has to withstand:
      an empty shape                        ->  no bed (None), no points, no faces, no
                                                heights; nothing raised
      a shape with lowest points            ->  its points, their heights among the heights
      a face facing down somewhere whose
        lowest line is no lowest point, as
        the ceiling of a pocket             ->  its lowest line among the heights as well
      a face facing up or sideways only,
        as a top or a wall                  ->  not among the heights: nothing starts there
      a shape the kernel cannot mesh        ->  no points, so no island is said, as
                                                before; the heights of its faces
      nothing asked for                     ->  the shape neither meshed nor its faces
                                                sampled
      the faces asked for alone             ->  the shape not meshed
      the same asked for again              ->  not worked out again, with or without a
                                                shape
      let go of, then something asked for
        that was not worked out yet         ->  ValueError: lend() it a shape first
      lent another copy of the same part
        as it stands                        ->  what is left is worked out on that one;
                                                what was worked out before serves it
      a face the kernel cannot measure      ->  the error passes on, nothing half kept:
                                                asked again, it is worked out again
      the part changed into one its key
        does not tell apart (stand_key()),
        also where its bridges are worked
        out anew, as for another bead       ->  the Starts kept serve it, as decided: the
                                                islands and bridges kept do the same
    """

    def __init__(self, shape):
        self._shape = shape
        # Height of the bed: the lowest of the shape.
        self.bed = None if shape.isNull() else bounds(shape).ZMin
        self._points = self._down = self._lowest = None

    def lend(self, shape):
        """Take `shape`, the part as it stands, for what is still to be worked out."""
        self._shape = shape

    def let_go(self):
        """Forget the shape; what was worked out stays."""
        self._shape = None

    def _asked(self):
        if self._shape is None:
            raise ValueError("these Starts hold no shape to work out what is asked of them: lend() one")
        return self._shape

    @property
    def points(self):
        """The lowest points of the shape, where an island can start."""
        if self._points is None:
            self._points = [] if self.bed is None else _lowest_points(self._asked())
        return self._points

    def _faces(self):
        if self._down is None:
            if self.bed is None:
                down, lowest = [], {}
            else:
                shape = self._asked()
                faces = shape.Faces
                down = facing_down(shape)
                lowest = {number: bounds(faces[number - 1]).ZMin - self.bed for number, _ in down}
            # Both at once, so neither is kept without the other.
            self._down, self._lowest = down, lowest

    @property
    def down(self):
        """The faces facing down somewhere, as facing_down() gives them."""
        self._faces()
        return self._down

    @property
    def lowest(self):
        """The height over the bed of the lowest line of each face facing
        down somewhere, by its number."""
        self._faces()
        return self._lowest

    @property
    def heights(self):
        """The heights over the bed at which something starts: those of the
        lowest points and of the lowest lines of the faces facing down."""
        return [point.z - self.bed for point in self.points] + list(self.lowest.values())


class LayerCuts:
    """The heights the layers of a part are cut at, by what starts in it:
    `starts`, the heights over the bed at which something of it starts
    (Starts.heights), every one of them, as what starts near the middle of a
    layer decides how the layer above is cut.

    A cut holds what lies below its plane (layer_faces()). A layer is cut at
    its middle. What carries it is the cut of the layer below, at the middle
    of that one, so one cut serves both. Only where something starts near
    that middle, the cut there could hold a slice of it and it would carry
    itself: then what carries the layer is cut SUPPORT_CUT_DROP under the
    middle, for all that starts in the layer. Near is told by the height
    alone, from LAYER_EDGE below where a height begins to count to the layer
    above up to NEAR_MIDDLE above the middle: not by the layer a height is
    counted to, so a height another copy of the part sees a rounding off,
    on the other side of where the layer changes, finds the layer cut the
    same.

    INPUTS this has to withstand (first layer 0.2, layers 0.2, middles 0.1, 0.3, 0.5):
      no starts                             ->  every layer cut at its middle, what
                                                carries it at the middle below
      a start well above a middle, 0.45     ->  layer 2 so: here 0.5, below 0.3, the cut
                                                layer 1 is cut at as well
      a start right on a middle, 0.3        ->  layer 2: below 0.3 less the drop
      a start within the tolerance below
        that middle, or less than
        NEAR_MIDDLE above it                ->  the same
      a start right at NEAR_MIDDLE above
        a middle                            ->  the layer lowered or not, as the rounding
                                                falls: both hold, the start lies that far
                                                above either cut
      a start right where the layer
        changes, the tolerance below the
        middle, seen by another copy on
        the other side                      ->  layer 2 lowered all the same: the band
                                                reaches LAYER_EDGE past that height
      a start more than that below the
        middle, in layer 1                  ->  layer 2 not lowered: its slice in the cut
                                                at 0.3 is thicker than the tolerance and
                                                carries, as it should
      two starts in one layer, one near
        the middle below, one well above    ->  one decision for the layer: lowered
      starts in neighbouring layers, none
        near a middle                       ->  below of the upper is here of the lower,
                                                the very same number, so one cut serves both
      a start near the middle of the first
        layer                               ->  layer 1 never lowered: what starts within
                                                the tolerance of that middle lies in the
                                                first layer, on the bed
    """

    def __init__(self, starts, first_layer, layer):
        self.first_layer, self.layer = first_layer, layer
        # The layers what carries them is cut lower for.
        self.lowered = set()
        for height in starts:
            number = layer_of(height, first_layer, layer)
            if number == 0:
                continue
            # Near the middle below its layer, which in layer 1 nothing is: what
            # starts that near the middle of the first layer lies in it. Or right
            # below where the next layer begins.
            if height < layer_middle(number - 1, first_layer, layer) + NEAR_MIDDLE:
                self.lowered.add(number)
            if height >= layer_middle(number, first_layer, layer) - d.TOLERANCE - LAYER_EDGE:
                self.lowered.add(number + 1)

    def at(self, height):
        """The cuts for a point `height` over the bed, as a CutHeights: the
        layer it starts to print in (layer_of()), the height over the bed its
        section is cut at, `here`, and the height the layer below is cut at
        to see what carries it, `below`. None in the first layer: the bed
        carries it.

        INPUTS this has to withstand:
          a height among the starts             ->  the cuts of its layer
          a height not among them               ->  the cuts of its layer all the same
          a height in the first layer           ->  None
          the same height from another copy,
            off by rounding                     ->  the same cuts; right where the layer
                                                    changes, those of either layer, both
                                                    lowered, so nothing carries itself
        """
        number = layer_of(height, self.first_layer, self.layer)
        if number == 0:
            return None
        support = layer_middle(number - 1, self.first_layer, self.layer)
        return CutHeights(number, layer_middle(number, self.first_layer, self.layer),
                          support - SUPPORT_CUT_DROP if number in self.lowered else support)


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
