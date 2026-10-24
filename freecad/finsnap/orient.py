"""Stand a part on one of its edges, and lay it flat again.

The part lies flat on the bed. It is turned about a selected edge until the
bottom face is lifted by the tilt angle, then lowered back onto the bed, so it
stands on that edge. An edge that is not on the bed comes with one of its
faces: that face is laid onto the bed first, which makes the edge a bottom edge.

The placement before the first tilt is kept on the moved object, so the part
can be laid flat again, also after several tilts.

INPUTS this has to withstand (tilt()):
  straight, horizontal edge on the bed  ->  placement standing on that edge
  curved edge                           ->  OrientError
  straight B-spline edge (loft side)    ->  as a straight edge
  edge not horizontal                   ->  OrientError
  edge above the lowest point           ->  OrientError: it is not a bottom edge
  angle <= 0 or >= 90                   ->  OrientError

INPUTS this has to withstand (stand()):
  no face                               ->  as tilt()
  edge of the face, face can lie on
    the bed                             ->  face laid down, then as tilt()
  face already on the bed               ->  same result as tilt() alone
  face facing up (normal +Z)            ->  part turned over, then as tilt()
  face curved (cone, cylinder)          ->  OrientError
  flat B-spline face (loft side)        ->  as a planar face
  edge not an edge of the face          ->  OrientError
  face the part cannot rest on (other
    geometry reaches below it)          ->  OrientError
  concave edge                          ->  OrientError from tilt()

INPUTS this has to withstand (remember_flat(), lay_back()):
  first tilt                            ->  placement kept
  second tilt                           ->  first placement stays kept
  lay_back on a tilted object           ->  placement restored, record gone, True
  lay_back on an untilted object        ->  nothing changed, False
"""

import FreeCAD as App

from . import defaults as d
from .i18n import QT_TRANSLATE_NOOP, translate

V = App.Vector
DOWN = V(0, 0, -1)

# Placement of the moved object before its first tilt.
FLAT_PLACEMENT = "FinSnapFlatPlacement"
FLAT_GROUP = QT_TRANSLATE_NOOP("App::Property", "FinSnap")
FLAT_TIP = QT_TRANSLATE_NOOP("App::Property", "Placement before Stand on edge, restored by Lay flat again")
PLACEMENT_TYPE = "App::PropertyPlacement"
# Editor mode that hides a property in the property view.
EDITOR_HIDDEN = 2


class OrientError(ValueError):
    """The part cannot be tilted onto this edge."""


def _moved(shape, change):
    moved = shape.copy()
    moved.Placement = change.multiply(moved.Placement)
    return moved


def tilt(shape, edge, angle_deg):
    """The placement change that stands `shape` on `edge`, tilted by angle_deg."""
    if not 0 < angle_deg < 90:
        raise OrientError(translate("FinSnap", "the tilt angle must lie between 0 and 90 degrees"))
    start, end = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
    axis = end - start
    # Measured instead of asking for a line: the side edges of a loft are
    # straight B-splines.
    if abs(edge.Length - axis.Length) > d.TOLERANCE:
        raise OrientError(translate("FinSnap", "the edge is curved; select a straight edge"))
    if abs(axis.z) > d.TOLERANCE * axis.Length:
        raise OrientError(translate("FinSnap", "the edge is not horizontal"))
    if start.z > shape.BoundBox.ZMin + d.TOLERANCE:
        raise OrientError(translate("FinSnap", "the edge does not lie on the bed"))

    # Of the two directions, the right one lifts the part over the edge
    # instead of pushing it through the bed.
    for sign in (1, -1):
        turn = App.Placement(V(0, 0, 0), App.Rotation(axis, sign * angle_deg), start)
        turned = _moved(shape, turn)
        if turned.BoundBox.ZMin >= start.z - d.TOLERANCE:
            lift = App.Placement(V(0, 0, start.z - turned.BoundBox.ZMin), App.Rotation())
            return lift.multiply(turn)
    raise OrientError(translate("FinSnap", "the part cannot stand on this edge"))


def lay_flat(shape, face):
    """The placement change that lays `face` onto the bed, at the bed level of `shape`."""
    if face.findPlane() is None:
        raise OrientError(translate("FinSnap", "the face that is to lie on the bed is curved; select a flat face"))
    u0, u1, v0, v1 = face.ParameterRange
    normal = face.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
    turn = App.Placement(V(0, 0, 0), App.Rotation(normal, DOWN), face.CenterOfMass)
    turned = _moved(shape, turn)
    if _moved(face, turn).BoundBox.ZMax > turned.BoundBox.ZMin + d.TOLERANCE:
        raise OrientError(translate("FinSnap", "the part cannot rest on this face"))
    lift = App.Placement(V(0, 0, shape.BoundBox.ZMin - turned.BoundBox.ZMin), App.Rotation())
    return lift.multiply(turn)


def stand(shape, edge, angle_deg, face=None):
    """Like tilt(); with a face, that face is laid onto the bed first."""
    if face is None:
        return tilt(shape, edge, angle_deg)
    if not any(edge.isSame(candidate) for candidate in face.Edges):
        raise OrientError(translate("FinSnap", "the edge is not an edge of the selected face"))
    flat = lay_flat(shape, face)
    return tilt(_moved(shape, flat), _moved(edge, flat), angle_deg).multiply(flat)


def remember_flat(owner):
    """Keep the placement of `owner` before its first tilt."""
    if FLAT_PLACEMENT in owner.PropertiesList:
        return
    owner.addProperty(PLACEMENT_TYPE, FLAT_PLACEMENT, FLAT_GROUP, FLAT_TIP)
    owner.setEditorMode(FLAT_PLACEMENT, EDITOR_HIDDEN)
    setattr(owner, FLAT_PLACEMENT, owner.Placement)


def lay_back(owner):
    """Restore the placement of `owner` before its first tilt. False if it was not tilted."""
    if FLAT_PLACEMENT not in owner.PropertiesList:
        return False
    owner.Placement = getattr(owner, FLAT_PLACEMENT)
    owner.removeProperty(FLAT_PLACEMENT)
    return True
