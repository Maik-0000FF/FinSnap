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

import numpy

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
# Several heights are cut in one cut of the kernel: at most this many, and on
# a shape of many faces, where a cut of several takes longer than its parts,
# no more than this many faces times heights.
CUTS_MOST = 8
CUT_FACES_MOST = 4000
# The faces of the cuts of a part are kept for its checks to share (Starts.cuts())
# as long as they hold no more edges than this between them: measured, an edge kept
# takes two to four thousand bytes, so some forty to eighty million in all.
CUT_EDGES_KEPT = 20000
# The first layers of the islands of a part are cut out of it in one cut of
# the kernel, at most this many (_first_layers()). Measured on parts of up to
# five thousand faces, the more are cut together the less it takes up to some
# two hundred; a thousand in one cut take twice as long as in four. Unlike the
# cuts of the layers (CUT_FACES_MOST), this does not turn with the faces of
# the part.
FIRST_LAYERS_MOST = 256
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

    INPUTS the search from each lowest point has to withstand:
      its layer or the one below not cut by
        the kernel (None)                   ->  the point passed over, no island said
      its layer cut, holding no section     ->  the point passed over, nothing asked
      a point outside the box of every
        section of its layer                ->  nothing measured
      a point in the box of one section     ->  the distance to that one measured alone
      a point in the boxes of several       ->  each in the order of its number
      a point right on the edge of a box    ->  in it
      the boxes compared in x and y alone   ->  the point is put at z 0 and the slabs lie
                                                around the plane of the bed: z is always
                                                within
      a point in the box of a section, yet
        further than a layer from it        ->  decides nothing: the section stays open
                                                for a later point
      a point within a layer of a section   ->  decides it: an island at this point, or
                                                resting
      a section decided before              ->  passed over, the kernel not asked
      a section whose slab meets the box of
        none below                          ->  an island, without a cut of the kernel
      boxes that only touch                 ->  asked: the overlap is none, an island
      a slab meeting the boxes of several
        below                               ->  overlapped with each in turn, until one
                                                carries it
      the layer below holding no section    ->  an island
      the kernel raising on the distance or
        the overlap                         ->  counts as resting: no island said
      the order                             ->  the points in theirs, for each the sections
                                                by number: the islands as they were found
                                                before the boxes were sorted
    """
    if part.isNull():
        return []
    starts = starts or Starts(part)
    bed = starts.bed
    # The sections of each height cut, and the boxes around them and around
    # their slabs in x and y (_flat()), for numpy to sort the points and the
    # sections below by before the kernel is asked.
    cut, reach, slabs = {}, {}, {}
    # Whether each section, by layer and number, rests on the layer below;
    # one that does not is an island, reported once, at its first lowest point.
    resting = {}
    found = []
    cuts = LayerCuts(starts.heights, first_layer, layer)
    # The points above the first layer, each with the heights its layer and
    # what carries it are cut at; all those heights cut together, and no
    # others, and none that another check of the part has cut before.
    placed = [(point, at) for point, at in ((point, cuts.at(point.z - bed)) for point in starts.points)
              if at is not None]
    faces = starts.cuts({bed + z for _, at in placed for z in (at.here, at.below)})
    for point, at in placed:
        here, below = bed + at.here, bed + at.below
        for z in (here, below):
            if z not in cut:
                cut[z] = sections(faces[z], z, layer)
                if cut[z]:
                    reach[z] = _flat(box for _, box, _ in cut[z])
                    slabs[z] = _flat(slab.BoundBox for slab, _, _ in cut[z])
        if cut[here] is None or cut[below] is None or not cut[here]:
            continue
        # The sections lie in the plane of the bed, see sections(); the point
        # is put there only once a section is found it may start on.
        middle = None
        # The boxes around the sections turn most points away before the
        # distance to one is measured, and a section decided before is
        # passed over.
        for index in _holding(reach[here], point.x, point.y):
            key = (at.number, index)
            if key in resting:
                continue
            section, _, outline = cut[here][index]
            if middle is None:
                middle = Part.Vertex(App.Vector(point.x, point.y, 0))
            try:
                # A point further off decides nothing: the section stays open
                # for a later point.
                if section.distToShape(middle)[0] > layer:
                    continue
                under = _meeting(slabs[below], slabs[here][index]) if cut[below] else ()
                resting[key] = any(_overlap(section, cut[below][other][0]) for other in under)
            except Part.OCCError:
                resting[key] = True
            if not resting[key]:
                found.append((point, outline, point.z, here + layer / 2))
    # The islands stay in the order found; their first layers are cut after
    # the last is found, several in one cut.
    firsts = _first_layers(part, [(outline, bottom, top) for _, outline, bottom, top in found])
    return [Island(App.Vector(point), first) for (point, *_), first in zip(found, firsts)]


def _flat(boxes):
    """`boxes` in x and y as an array, a row for each: XMin, XMax, YMin, YMax;
    no rows of no boxes."""
    return numpy.array([(box.XMin, box.XMax, box.YMin, box.YMax) for box in boxes], dtype=float).reshape(-1, 4)


def _holding(boxes, x, y):
    """The numbers, from 0 and rising, of the `boxes` (_flat()) the point at
    `x`, `y` lies in, their edges included, as BoundBox.isInside() has it."""
    return [int(number) for number in numpy.flatnonzero(
        (boxes[:, 0] <= x) & (x <= boxes[:, 1]) & (boxes[:, 2] <= y) & (y <= boxes[:, 3]))]


def _meeting(boxes, box):
    """The numbers, from 0 and rising, of the `boxes` (_flat()) that `box`, a
    row of such, meets or touches, as BoundBox.intersect() has it."""
    return [int(number) for number in numpy.flatnonzero(
        (boxes[:, 0] <= box[1]) & (box[0] <= boxes[:, 1]) & (boxes[:, 2] <= box[3]) & (box[2] <= boxes[:, 3]))]


def _first_layers(part, wanted):
    """The first layer of each island of `part` in `wanted`, in their order:
    for each (outline, bottom, top) the part from `bottom`, its lowest point,
    up to `top`, the top of its first layer, within `outline`, the face where
    the middle of that layer cuts it, as a compound of solids; None where
    there is none or the kernel cannot cut it out.

    The part is cut within a prism over each outline. A cut of the kernel
    takes about as long as the part has faces, whatever is cut out, so the
    prisms of several islands are cut in one (_apart(), _cut_within()).

    INPUTS this has to withstand:
      no island                             ->  [], nothing cut
      one island                            ->  cut alone
      several whose prisms keep apart       ->  one cut; each island has the solids
                                                within its prism
      prisms whose boxes overlap, meet or
        lie nearer than the tolerance, as
        of islands in neighbouring layers   ->  never in one cut: the later waits
      more islands than FIRST_LAYERS_MOST   ->  several cuts, none of more
      a prism the part lies in several
        pieces within                       ->  all of them, in one compound
      a prism holding nothing of the part,
        or no solid of it, as of a shell    ->  None, not tried again alone
      an outline the kernel cannot make a
        prism of                            ->  None for that island, the others cut
      a cut of several the kernel cannot
        make, or gives a null shape of      ->  its islands cut one by one; None for one
                                                it cannot cut alone either
    """
    prisms = [_prism(*each) for each in wanted]
    found = [None] * len(wanted)
    for batch in _apart([(index, prism) for index, prism in enumerate(prisms) if prism is not None],
                        FIRST_LAYERS_MOST):
        pieces = _cut_within(part, batch)
        if pieces is None and len(batch) > 1:
            pieces = {}
            for one in batch:
                pieces.update(_cut_within(part, [one]) or {})
        for index, solids in (pieces or {}).items():
            if sum(solid.Volume for solid in solids) > 0:
                found[index] = Part.makeCompound(solids)
    return found


def _prism(outline, bottom, top):
    """The prism over `outline`, a face of a cut, from the tolerance under
    `bottom` up to `top`; None where the kernel cannot make it, which it says
    by an OCCError, or by a ValueError of an outline that is a null shape."""
    try:
        footprint = outline.translated(App.Vector(0, 0, bottom - d.TOLERANCE - outline.BoundBox.ZMin))
        return footprint.extrude(App.Vector(0, 0, top - bottom + d.TOLERANCE))
    except (Part.OCCError, ValueError):
        return None


def _apart(prisms, most):
    """`prisms`, as (index, prism), in batches to cut together: lists of at
    most `most`, in each of which the boxes around the prisms keep more than
    the tolerance apart, so the prisms neither overlap nor touch and what is
    cut out within one lies in its box alone. A prism too near one of a
    batch waits for a later one.

    INPUTS this has to withstand:
      no prisms                             ->  no batch
      prisms far apart, no more than `most` ->  one batch, in their order
      more of them                          ->  several, none of more than `most`
      two whose boxes overlap, share a
        side, or lie less than the
        tolerance apart                     ->  in different batches
      two whose boxes are apart while the
        prisms are near, an L around a
        block                               ->  boxes overlap: different batches
    """
    waiting = []
    for index, prism in prisms:
        near = App.BoundBox(prism.BoundBox)
        near.enlarge(d.TOLERANCE)
        waiting.append((index, prism, near))
    while waiting:
        batch, later = [], []
        for each in waiting:
            if len(batch) < most and not any(each[2].intersect(other.BoundBox) for _, other, _ in batch):
                batch.append(each)
            else:
                later.append(each)
        yield [(index, prism) for index, prism, _ in batch]
        waiting = later


def _cut_within(part, batch):
    """What of `part` lies within each prism of `batch`, (index, prism) whose
    boxes keep apart (_apart()): its solids by index, in one cut of the
    kernel; an index with none is left out. None where the kernel cannot
    make the cut or gives a null shape.

    A solid cut out lies within its prism, so the middle of its box lies in
    the box of that prism and of no other of the batch.

    Whether what the kernel gives is valid is not looked at, as for the cuts
    of the layers (_cut_out()): an island whose solids are missing from a
    cut that came out wrong without being null is said without a first
    layer. Decided so."""
    try:
        cut_out = part.common(Part.makeCompound([prism for _, prism in batch]))
    except Part.OCCError:
        return None
    if cut_out.isNull():
        return None
    boxes = [(index, prism.BoundBox) for index, prism in batch]
    within = {}
    for solid in cut_out.Solids:
        middle = solid.BoundBox.Center
        for index, box in boxes:
            if box.isInside(middle):
                within.setdefault(index, []).append(solid)
                break
    return within


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

    It also keeps the faces where its layers are cut (cuts()), which are
    shapes of their own, no part of the shape lent: they stay when it is let
    go of, until drop_cuts().

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
        # How many faces the shape has, counted once; the faces of its cuts, by
        # height, and how many edges they hold between them.
        self._face_count = None
        self._cuts, self._edges_kept = {}, 0

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
                self._face_count = len(faces)
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

    def cuts(self, heights):
        """The faces where the planes at `heights` cut the shape (faces_at()),
        by height, None for a height the kernel cannot cut at. They are kept,
        so every check of the part as it stands cuts a height once between
        them, and a check asked again, as the bridges are when fins change
        which faces are carried, cuts nothing anew.

        The heights are to be bed + what LayerCuts of these Starts gives: the
        same numbers for every check that takes them from here. The faces
        given are not to be changed in place: they are kept for the next
        check.

        Kept faces hold memory, a few thousand bytes an edge: a height whose
        faces would take what is kept past CUT_EDGES_KEPT edges is given and
        not kept, cut anew each time as without a stock.

        INPUTS this has to withstand:
          heights never asked before            ->  cut together (faces_at()), kept and given
          heights asked before                  ->  given as kept, the kernel not asked
          some asked before, some not           ->  those not kept cut together, the others
                                                    given as kept
          no heights                            ->  {}, nothing asked of the shape
          a height the kernel could not cut     ->  None for it, kept so and given again:
                                                    not tried anew
          the same heights from another check
            of the part, the very same numbers  ->  as kept
          a height a rounding off one kept, as
            from another reading of the bed     ->  cut for itself: a cut more, no harm
          a height whose faces would take what
            is kept past CUT_EDGES_KEPT edges,
            be it alone                         ->  given, not kept; one after it that still
                                                    fits is kept
          the lists given changed by a caller   ->  what is kept is not: each is a list of
                                                    its own, of the same faces
          let go of, then heights asked that
            are all kept                        ->  given
          let go of, then a height asked that
            is not kept                         ->  ValueError: lend() it a shape first
          lent another copy of the part as it
            stands                              ->  what is missing cut on that one; what was
                                                    kept serves it
          drop_cuts(), then heights asked       ->  cut anew
        """
        wanted = sorted(set(heights))
        missing = [z for z in wanted if z not in self._cuts]
        found = {}
        if missing:
            shape = self._asked()
            if self._face_count is None:
                self._face_count = len(shape.Faces)
            found = faces_at(shape, missing, self._face_count)
            for z in missing:
                edges = sum(len(face.Edges) for face in found[z] or [])
                if self._edges_kept + edges <= CUT_EDGES_KEPT:
                    self._cuts[z] = found[z]
                    self._edges_kept += edges
        # Lists of their own, so no caller changes those kept.
        given = {z: self._cuts[z] if z in self._cuts else found[z] for z in wanted}
        return {z: None if faces is None else list(faces) for z, faces in given.items()}

    def drop_cuts(self):
        """Forget the cuts kept, and with them the memory they hold."""
        self._cuts, self._edges_kept = {}, 0


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


def _cutter(box, z):
    """The thin box whose top, at height `z`, cuts a shape with the bounding
    box `box`: SECTION_CUT_HEIGHT high, SECTION_CUT_MARGIN past it all round."""
    return Part.makeBox(box.XLength + 2 * SECTION_CUT_MARGIN, box.YLength + 2 * SECTION_CUT_MARGIN,
                        SECTION_CUT_HEIGHT, App.Vector(box.XMin - SECTION_CUT_MARGIN,
                                                       box.YMin - SECTION_CUT_MARGIN, z - SECTION_CUT_HEIGHT))


def _flat_up(face):
    """Whether `face`, of what cutters cut out of a shape, is flat and faces
    up, as the top of a cut does, and neither the sides nor the underside of
    a thin slice."""
    return face.BoundBox.ZLength < d.TOLERANCE and middle_normal(face).z > FACING_UP


def _on_top(face, z):
    """Whether `face`, of what a cutter cut out of a shape, is of the top of
    the cut at height `z`: in that plane within the tolerance, flat and
    facing up (_flat_up())."""
    return abs(face.BoundBox.ZMin - z) < d.TOLERANCE and _flat_up(face)


def _cut_out(shape, cutters):
    """What `cutters`, a cutter or several in one compound, cut out of
    `shape`: one cut of the kernel. None where it gives nothing at all, a
    null shape; what it raises passes on.

    Whether what it gives is valid is not looked at: that takes a fifth to a
    quarter of the time of the cut itself, and would undo most of what
    cutting several heights together saves. A cut that comes out wrong
    without being null goes unnoticed, as it did when each height was cut
    alone. Decided so."""
    cut_out = shape.common(cutters)
    return None if cut_out.isNull() else cut_out


def layer_faces(shape, z):
    """The faces where the plane at height `z` cuts `shape`, holes and all:
    the top of a thin cut-out of it ending at the plane, see
    SECTION_CUT_HEIGHT. A face of the part lying in the plane is cut whole.
    None where the kernel cannot make them. Several heights are cut faster
    together (faces_at()).

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
      a cut the kernel cannot make, or gives
        nothing of                          ->  None
    """
    try:
        cut_out = _cut_out(shape, _cutter(bounds(shape), z))
    except Part.OCCError:
        return None
    return None if cut_out is None else [face for face in cut_out.Faces if _on_top(face, z)]


def _batches(heights, most):
    """`heights`, sorted, each once, in batches to cut together: lists of at
    most `most`, in each of which a height lies at least the height of a
    cutter and the tolerance above the one before, so their cutters do not
    overlap. A height too near the last of a batch waits for a later one.

    INPUTS this has to withstand:
      no heights                            ->  no batch
      heights far enough apart, no more
        than `most`                         ->  one batch
      more of them                          ->  several, none of more than `most`
      two heights nearer than a cutter is
        high, as a middle and the cut
        lowered under it, or two a
        rounding apart                      ->  in different batches
    """
    waiting = list(heights)
    while waiting:
        batch, later = [], []
        for z in waiting:
            if len(batch) < most and (not batch or z - batch[-1] >= SECTION_CUT_HEIGHT + d.TOLERANCE):
                batch.append(z)
            else:
                later.append(z)
        yield batch
        waiting = later


def cuts_together(faces):
    """How many heights a shape of `faces` faces is cut at in one cut of the
    kernel: as many as CUTS_MOST, and fewer on a shape of many faces, where a
    cut of several takes longer than its parts, no more than CUT_FACES_MOST
    faces times heights; 1, each height alone, on a shape of more than half
    that many faces."""
    return max(1, min(CUTS_MOST, CUT_FACES_MOST // max(1, faces)))


def faces_at(shape, heights, faces=None):
    """The faces where the planes at `heights` cut `shape` (layer_faces()),
    by height; None for a height the kernel cannot cut at. Several heights
    are cut in one cut of the kernel, which takes less than a cut each:
    cuts_together() of them, by the number of faces of the shape, `faces`
    where the caller has counted them already.

    The heights are to be those a check asks for and no others: the layers
    something starts in and what carries them (LayerCuts).

    INPUTS this has to withstand:
      no heights                            ->  {}, nothing asked of the shape
      one height                            ->  cut alone, as layer_faces()
      several heights, each at least the
        height of a cutter from the next    ->  up to as many as said in one cut; the
                                                faces of each as cut alone
      more heights than that                ->  several cuts, none of more
      two heights nearer than a cutter is
        high, as a middle and the cut
        lowered under it, or two a
        rounding apart                      ->  never in one cut, their cutters would
                                                overlap: the upper in a later cut,
                                                with the others that wait
      the same height twice                 ->  cut once
      a face of a cut of several            ->  to the height whose plane it lies in,
                                                within the tolerance, facing up; the
                                                sides and undersides of what the cutters
                                                cut out, and a top of the part lying
                                                within a cutter, to none
      a face of the part lying in the plane
        of one height                       ->  cut whole, among the faces of that height
      a height above or below the part      ->  [] for it
      a cut of several the kernel cannot
        make, or gives nothing of           ->  its heights cut one by one; None for one
                                                it cannot cut alone either
    """
    heights = sorted(set(heights))
    if not heights:
        return {}
    box = bounds(shape)
    found = {}
    for batch in _batches(heights, cuts_together(len(shape.Faces) if faces is None else faces)):
        cut_out = None
        if len(batch) > 1:
            try:
                cut_out = _cut_out(shape, Part.makeCompound([_cutter(box, z) for z in batch]))
            except Part.OCCError:
                cut_out = None
        if cut_out is None:
            found.update((z, layer_faces(shape, z)) for z in batch)
            continue
        # Each face looked at once, whichever of the heights it belongs to.
        tops = [(face.BoundBox.ZMin, face) for face in cut_out.Faces if _flat_up(face)]
        found.update((z, [face for low, face in tops if abs(low - z) < d.TOLERANCE]) for z in batch)
    return found


def sections(faces, z, reach):
    """`faces`, where the plane at height `z` cuts a shape (layer_faces()),
    as one slab SECTION_SLAB thick for each, around the plane of the bed, z
    0, so sections of different layers can be overlapped, each with its
    bounding box grown by `reach` (mm) and the face of the cut where it lies;
    None where there are no faces to tell, the kernel could not cut, or
    where it cannot make the slabs."""
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
