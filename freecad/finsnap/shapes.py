"""Shapes in global coordinates, wherever the object sits in the tree.

A feature inside a PartDesign Body (a Pad, a Pocket) keeps its shape in the
coordinates of the Body. Selecting a face on it in the 3D view hands over that
local shape: after the Body was tilted, the face still looks untilted. Every
command therefore works on the global shape, and moves the outermost container
when it changes a placement.

INPUTS this has to withstand:
  top-level Part feature                ->  its shape as it is
  feature inside a Body (Pad)           ->  shape placed by the Body's placement
  Body itself                           ->  its shape as it is
  object in a Part container            ->  shape placed by every parent
  object without a shape                ->  ValueError naming it

Faces are named and measured here as well, so every module agrees on what
"Face3" and "the middle of a face" mean.

INPUTS this has to withstand (bounds()):
  planar faces only                     ->  the same box as BoundBox
  cylinder or cone turned off its axis  ->  the box touching the surface; BoundBox
                                            reaches up to millimetres beyond it
  single face or edge                   ->  its tight box
"""

import Part

from .i18n import translate

# Prefix of the face names FreeCAD uses in selections and links: "Face3".
FACE_PREFIX = "Face"


def face_name(number):
    """The name of face `number`, counted from 1 as FreeCAD does."""
    return "%s%d" % (FACE_PREFIX, number)


def middle_of(face):
    """The surface parameters in the middle of `face`."""
    u0, u1, v0, v1 = face.ParameterRange
    return (u0 + u1) / 2, (v0 + v1) / 2


def middle_normal(face):
    """The outward normal in the middle of `face`."""
    return face.normalAt(*middle_of(face))


def bounds(shape):
    """The box that touches `shape`. BoundBox only encloses the control points
    of curved faces, so after a turn it can stand millimetres off a fillet: a
    part would then float above the bed, and fins reach below it."""
    return shape.optimalBoundingBox()


def global_shape(obj):
    shape = Part.getShape(obj, "", needSubElement=False, transform=False)
    if shape.isNull():
        raise ValueError(translate("FinSnap", "%s has no shape") % obj.Label)
    shape = shape.copy()
    shape.Placement = obj.getGlobalPlacement()
    return shape


def outermost(obj):
    """The container whose placement moves the whole part: the topmost parent group."""
    while True:
        parent = obj.getParentGeoFeatureGroup()
        if parent is None:
            return obj
        obj = parent
