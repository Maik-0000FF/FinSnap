"""Stand a part on one of its bottom edges.

The part lies flat on the bed. It is turned about a selected edge until the
bottom face is lifted by the tilt angle, then lowered back onto the bed, so it
stands on that edge.

INPUTS this has to withstand (tilt()):
  straight, horizontal edge on the bed  ->  placement standing on that edge
  curved edge                           ->  OrientError
  edge not horizontal                   ->  OrientError
  edge above the lowest point           ->  OrientError: it is not a bottom edge
  angle <= 0 or >= 90                   ->  OrientError
"""

import FreeCAD as App
import Part

from . import defaults as d

V = App.Vector


class OrientError(ValueError):
    """The part cannot be tilted onto this edge."""


def tilt(shape, edge, angle_deg):
    """The placement change that stands `shape` on `edge`, tilted by angle_deg."""
    if not 0 < angle_deg < 90:
        raise OrientError("the tilt angle must lie between 0 and 90 degrees")
    if not isinstance(edge.Curve, Part.Line):
        raise OrientError("select a straight edge")
    start, end = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
    axis = end - start
    if abs(axis.z) > d.TOLERANCE * axis.Length:
        raise OrientError("the edge is not horizontal")
    if start.z > shape.BoundBox.ZMin + d.TOLERANCE:
        raise OrientError("the edge does not lie on the bed")

    # Of the two directions, the right one lifts the part over the edge
    # instead of pushing it through the bed.
    for sign in (1, -1):
        turn = App.Placement(V(0, 0, 0), App.Rotation(axis, sign * angle_deg), start)
        turned = shape.copy()
        turned.Placement = turn.multiply(turned.Placement)
        if turned.BoundBox.ZMin >= start.z - d.TOLERANCE:
            lift = App.Placement(V(0, 0, start.z - turned.BoundBox.ZMin), App.Rotation())
            return lift.multiply(turn)
    raise OrientError("the part cannot stand on this edge")
