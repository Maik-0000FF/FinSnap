# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

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

A part made in a Body is the Body: its shape is that of its last feature,
so fins follow a chamfer or a fillet added after them (part_of()). A face is
found again there by the plane it lies in (face_like()), as its name changes
with every feature.

Faces are named and measured here as well, so every module agrees on what
"Face3" and "the middle of a face" mean.

INPUTS this has to withstand (bounds()):
  planar faces only                     ->  the same box as BoundBox
  cylinder or cone turned off its axis  ->  the box touching the surface; BoundBox
                                            reaches up to millimetres beyond it
  single face or edge                   ->  its tight box
  shape carrying a display mesh         ->  the same box: measured on the surfaces,
                                            not on the mesh, which lies up to its
                                            deflection off them
"""

import Part

from .i18n import translate

# bounds() measures the surfaces themselves, never a mesh that may hang on them.
USE_TRIANGULATION = False
# Prefix of the face names FreeCAD uses in selections and links: "Face3".
FACE_PREFIX = "Face"
# The container that holds a PartDesign part; its shape is that of its last feature.
BODY_TYPE = "PartDesign::Body"
# Two faces lie in one plane within this distance (mm) and this cosine
# between their normals; a feature that cuts a face leaves the rest of it
# exactly where it was.
SAME_PLACE = 1e-3
SAME_DIRECTION = 1.0 - 1e-6


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
    return shape.optimalBoundingBox(USE_TRIANGULATION)


def moved(shape, change):
    """A copy of `shape` with the placement change `change` applied."""
    result = shape.copy()
    result.Placement = change.multiply(result.Placement)
    return result


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


def part_of(obj):
    """The object whose shape is the part `obj` belongs to: the Body of a
    feature inside a PartDesign Body, which holds the shape with every feature
    after it, a chamfer or a fillet added later as well; else `obj` itself."""
    parent = obj.getParentGeoFeatureGroup()
    if parent is not None and parent.isDerivedFrom(BODY_TYPE):
        return parent
    return obj


def plane_of(face):
    """The plane `face` lies in, as (a point on it, its outward normal), or
    None for a face that is not planar."""
    if face.findPlane() is None:
        return None
    return face.CenterOfMass, middle_normal(face)


def face_like(shape, face):
    """The name on `shape` of the face lying where `face` lies, the same face
    on another shape of the part, or the largest of those in its plane where
    a feature cut it; None if there is none.

    INPUTS this has to withstand:
      the same face, other numbers          ->  its name on `shape`
      a planar face cut smaller by a
        chamfer, a fillet or a pocket       ->  the face left in its plane
      a planar face cut in two              ->  the larger piece
      a face of the same plane facing the
        other way (the other side of a wall) ->  passed over: its normal is reversed
      a planar face cut away whole          ->  None
      a curved face, unchanged              ->  the face with its centre of mass and area
      a curved face changed                 ->  None: it has no plane to find it by
    """
    plane = plane_of(face)
    if plane is None:
        return next((face_name(number) for number, candidate in enumerate(shape.Faces, 1)
                     if candidate.CenterOfMass.distanceToPoint(face.CenterOfMass) < SAME_PLACE
                     and abs(candidate.Area - face.Area) < SAME_PLACE), None)
    return face_in_plane(shape, *plane)


def in_plane(face, point, normal):
    """Whether `face` is planar and lies in the plane through `point` with the
    outward normal `normal`."""
    return (plane_of(face) is not None and middle_normal(face).dot(normal) > SAME_DIRECTION
            and abs((face.CenterOfMass - point).dot(normal)) < SAME_PLACE)


def face_in_plane(shape, point, normal):
    """The name of the largest face of `shape` in the plane through `point`
    with the outward normal `normal`, see in_plane(); None if there is none."""
    found = [(candidate.Area, number) for number, candidate in enumerate(shape.Faces, 1)
             if in_plane(candidate, point, normal)]
    return face_name(max(found)[1]) if found else None
