"""Faces of a part that overhang the bed too flatly to print without support.

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

from . import defaults as d
from .shapes import bounds, middle_normal


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
