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
"""

import Part


def global_shape(obj):
    shape = Part.getShape(obj, "", needSubElement=False, transform=False)
    if shape.isNull():
        raise ValueError("%s has no shape" % obj.Label)
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
