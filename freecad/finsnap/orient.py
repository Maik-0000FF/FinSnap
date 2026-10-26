"""Stand a part on one of its edges, and lay it flat again.

The part lies flat on the bed. It is turned about a selected edge until the
bottom face is lifted by the tilt angle, then lowered back onto the bed, so it
stands on that edge. An edge that is not on the bed comes with one of its
faces: that face is laid onto the bed first, which makes the edge a bottom edge.
An edge between two flat faces at a right angle needs no face at 45 degrees:
either face laid down gives the same result, both faces equally steep.
A face alone, a chamfer or a fillet, is laid onto the bed and carries the part.

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
  no face, edge on the bed              ->  as tilt()
  no face, edge between two flat faces
    at a right angle, 45 degrees        ->  as rest_between() on those faces
  no face, vertical edge between two
    side faces at a right angle         ->  as rest_between(): stands on that edge,
                                            which comes to lie on the bed
  no face, right angle off by less than
    RIGHT_ANGLE_TOLERANCE (mesh solids) ->  as a right angle
  no face, right angle, other angle     ->  OrientError: select the face
  no face, faces not at a right angle,
    or one of them rounded              ->  OrientError: select the face
  no face, edge of an inner corner      ->  OrientError from rest_between()
  edge of the face, face can lie on
    the bed                             ->  face laid down, then as tilt()
  face already on the bed               ->  same result as tilt() alone
  face facing up (normal +Z)            ->  part turned over, then as tilt()
  face rounded (fillet, cone mantle)    ->  OrientError: it touches the bed only
                                            along its middle, never with the edge;
                                            choose it alone or the faces beside it
  flat B-spline face (loft side)        ->  as a planar face
  edge not an edge of the face          ->  OrientError
  face the part cannot rest on (other
    geometry reaches below it)          ->  OrientError
  concave edge                          ->  OrientError from tilt()

INPUTS this has to withstand (rest_between()):
  two faces at a sharp edge             ->  part stands on the edge, both faces
                                            equally steep
  two faces with a chamfer or fillet
    between them                        ->  part stands on the chamfer or fillet
  two faces pointing opposite ways      ->  OrientError
  two faces of an inner corner, or
    other geometry reaching lower       ->  OrientError: cannot rest between them

INPUTS this has to withstand (lay_flat()):
  flat face (chamfer)                   ->  lies flat on the bed
  face rounded and convex (fillet, cone
    mantle)                             ->  touches the bed along its middle
  face rounded and concave (inner
    fillet)                             ->  OrientError: cannot rest on it

INPUTS this has to withstand (side_direction()):
  edge                                  ->  the edge after the change, horizontal
  two faces (sharp edge or fillet)      ->  the line joining them after the change
  face alone, turned                    ->  the axis of the turn
  face alone, already on the bed        ->  None
  line pointing to -Y, or along -X      ->  reversed, so a line is always seen from one side

INPUTS this has to withstand (remember_flat(), lay_back()):
  back_to_flat on a tilted object       ->  the change from its placement to the kept one
  back_to_flat on an untilted object    ->  None
  first tilt                            ->  placement kept
  second tilt                           ->  first placement stays kept
  lay_back on a tilted object           ->  placement restored, record gone, True
  lay_back on an untilted object        ->  nothing changed, False
"""

import math

import FreeCAD as App
import Part

from . import defaults as d
from .i18n import QT_TRANSLATE_NOOP, translate
from .shapes import bounds, middle_normal, middle_of

V = App.Vector
DOWN = V(0, 0, -1)
UP = V(0, 0, 1)

# Placement of the moved object before its first tilt.
FLAT_PLACEMENT = "FinSnapFlatPlacement"
FLAT_GROUP = QT_TRANSLATE_NOOP("App::Property", "FinSnap")
FLAT_TIP = QT_TRANSLATE_NOOP("App::Property", "Placement before Stand on edge, restored by Lay flat again")
PLACEMENT_TYPE = "App::PropertyPlacement"
# Editor mode that hides a property in the property view.
EDITOR_HIDDEN = 2
# The one angle at which an edge between two faces at a right angle stands the
# part without saying which face goes down: both faces end up equally steep.
RIGHT_ANGLE_TILT = 45.0


class OrientError(ValueError):
    """The part cannot be tilted onto this edge."""


def _moved(shape, change):
    moved = shape.copy()
    moved.Placement = change.multiply(moved.Placement)
    return moved


def on_bed(shape, edge):
    """True if both ends of `edge` lie on the bed, the lowest level of `shape`."""
    bed_z = bounds(shape).ZMin
    return all(vertex.Point.z <= bed_z + d.TOLERANCE for vertex in edge.Vertexes)


def right_angle_faces(shape, edge):
    """The two faces of `edge` if both are flat and meet at a right angle, within
    RIGHT_ANGLE_TOLERANCE, else None."""
    faces = shape.ancestorsOfType(edge, Part.Face)
    if len(faces) != 2 or any(face.findPlane() is None for face in faces):
        return None
    off_square = math.sin(math.radians(d.RIGHT_ANGLE_TOLERANCE))
    if abs(middle_normal(faces[0]).dot(middle_normal(faces[1]))) > off_square:
        return None
    return tuple(faces)


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
    if not on_bed(shape, edge):
        raise OrientError(translate("FinSnap", "the edge does not lie on the bed"))

    # Of the two directions, the right one lifts the part over the edge
    # instead of pushing it through the bed.
    for sign in (1, -1):
        turn = App.Placement(V(0, 0, 0), App.Rotation(axis, sign * angle_deg), start)
        lowest = bounds(_moved(shape, turn)).ZMin
        if lowest >= start.z - d.TOLERANCE:
            lift = App.Placement(V(0, 0, start.z - lowest), App.Rotation())
            return lift.multiply(turn)
    raise OrientError(translate("FinSnap", "the part cannot stand on this edge"))


def lay_flat(shape, face):
    """The placement change that lays `face` onto the bed, at the bed level of `shape`.

    The face is turned until its normal in the middle of it points straight
    down. A flat face, such as a chamfer, then lies on the bed; a rounded one,
    such as a fillet, touches it along a line through its middle, so a fillet
    of 90 degrees stands the part at 45.
    """
    middle = middle_of(face)
    normal = face.normalAt(*middle)
    contact = face.valueAt(*middle)
    turn = App.Placement(V(0, 0, 0), App.Rotation(normal, DOWN), contact)
    lowest = bounds(_moved(shape, turn)).ZMin
    # The part rests on the face only if nothing reaches below that point.
    if contact.z > lowest + d.TOLERANCE:
        raise OrientError(translate("FinSnap", "the part cannot rest on this face"))
    lift = App.Placement(V(0, 0, bounds(shape).ZMin - lowest), App.Rotation())
    return lift.multiply(turn)


def rest_between(shape, first, second):
    """The placement change that stands `shape` on what lies between two faces,
    both leaning equally steeply over the bed.

    Whatever joins the faces carries the part: a sharp edge, a chamfer or a
    fillet. Two faces at a right angle each end up at 45 degrees.
    """
    middle = middle_normal(first) + middle_normal(second)
    if middle.Length < d.TOLERANCE:
        raise OrientError(translate("FinSnap", "the two faces point in opposite directions"))
    middle.normalize()
    turn = App.Placement(V(0, 0, 0), App.Rotation(middle, DOWN), first.CenterOfMass)
    turned = _moved(shape, turn)
    bed_z = bounds(turned).ZMin
    # Only the two faces and what joins them may touch the bed. A copy keeps
    # the order of the faces but not their identity, so they are compared by
    # number, and neighbours are found on the original shape.
    faces = shape.Faces
    chosen = [next(i for i, face in enumerate(faces) if face.isSame(side)) for side in (first, second)]

    def joins(i, j):
        return any(edge.isSame(other) for edge in faces[i].Edges for other in faces[j].Edges)

    for i, face in enumerate(turned.Faces):
        if bounds(face).ZMin > bed_z + d.TOLERANCE or i in chosen:
            continue
        if not all(joins(i, j) for j in chosen):
            raise OrientError(translate("FinSnap", "the part cannot rest between these faces"))
    lift = App.Placement(V(0, 0, bounds(shape).ZMin - bed_z), App.Rotation())
    return lift.multiply(turn)


def stand(shape, edge, angle_deg, face=None):
    """Like tilt(); with a face, that face is laid onto the bed first. Without a
    face, an edge off the bed between two faces at a right angle stands the part
    at 45 degrees."""
    if face is None:
        if on_bed(shape, edge):
            return tilt(shape, edge, angle_deg)
        corner = right_angle_faces(shape, edge)
        if corner is None:
            raise OrientError(translate("FinSnap", "the edge does not lie on the bed"))
        if abs(angle_deg - RIGHT_ANGLE_TILT) > d.TOLERANCE:
            raise OrientError(translate("FinSnap", "an edge alone stands the part only at 45 degrees; for "
                                                   "another angle select the face that is to lie on the bed"))
        return rest_between(shape, *corner)
    if not any(edge.isSame(candidate) for candidate in face.Edges):
        raise OrientError(translate("FinSnap", "the edge is not an edge of the selected face"))
    if face.findPlane() is None:
        raise OrientError(translate("FinSnap", "a rounded face does not lie on the bed with its edge; select "
                                               "it alone, or the two faces beside it"))
    flat = lay_flat(shape, face)
    return tilt(_moved(shape, flat), _moved(edge, flat), angle_deg).multiply(flat)


def side_direction(change, edge=None, faces=()):
    """The horizontal direction of the line the part stands on after `change`.

    Looking along it shows the part from the side, the tilt angle in profile.
    The line is the edge, or what joins two faces (its direction is the cross
    product of their normals), or for a face alone the axis the part was turned
    about. Of the two senses the one pointing to +Y (or +X for a line along X)
    is returned, so the same line is always seen from the same side: for a
    line along Y that is FreeCAD's front view, for one along X the view from the left.
    None if the part was not turned, a face that already lay on the bed.
    """
    if edge is not None:
        line = edge.Vertexes[-1].Point - edge.Vertexes[0].Point
    elif len(faces) == 2:
        line = middle_normal(faces[0]).cross(middle_normal(faces[1]))
    elif abs(change.Rotation.Angle) > d.TOLERANCE:
        line = change.Rotation.Axis
    else:
        return None
    line = change.Rotation.multVec(line)
    line.z = 0
    if line.Length < d.TOLERANCE:
        return None
    line.normalize()
    if line.y < -d.TOLERANCE or (abs(line.y) <= d.TOLERANCE and line.x < 0):
        line = -line
    return line


def remember_flat(owner):
    """Keep the placement of `owner` before its first tilt."""
    if FLAT_PLACEMENT in owner.PropertiesList:
        return
    owner.addProperty(PLACEMENT_TYPE, FLAT_PLACEMENT, FLAT_GROUP, FLAT_TIP)
    owner.setEditorMode(FLAT_PLACEMENT, EDITOR_HIDDEN)
    setattr(owner, FLAT_PLACEMENT, owner.Placement)


def back_to_flat(owner):
    """The placement change lay_back() would make to `owner`, None if it was not tilted."""
    if FLAT_PLACEMENT not in owner.PropertiesList:
        return None
    return getattr(owner, FLAT_PLACEMENT).multiply(owner.Placement.inverse())


def lay_back(owner):
    """Restore the placement of `owner` before its first tilt. False if it was not tilted."""
    if FLAT_PLACEMENT not in owner.PropertiesList:
        return False
    owner.Placement = getattr(owner, FLAT_PLACEMENT)
    owner.removeProperty(FLAT_PLACEMENT)
    return True
