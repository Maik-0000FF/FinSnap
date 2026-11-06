# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""How the quick fin stands a part on the bed: the rims on its axis, the faces
that take fins, and the stands found for a face, each checked by building
its fins (geometry.py).
"""

import itertools
import math
from collections import namedtuple
from functools import partial

import Part

from . import defaults as d
from . import geometry, orient
from .face_frame import FinError, frame_of
from .i18n import QT_TRANSLATE_NOOP, translate
from .shapes import middle_normal, moved

# The order rims_on_axis() tries rims in: a chamfered one, then one of the
# side itself, then any other on the axis, which a part rarely stands on.
RIM_CHAMFERED, RIM_OWN, RIM_OTHER = range(3)
# Why Quick fins finds no way to stand a part: no face takes the fins, or
# the face selected takes them on no edge it can stand on.
NO_LEANING_FACE = QT_TRANSLATE_NOOP("FinSnap", "no face of the part leans over the bed and takes fins")
NO_STAND_FOR_FACE = QT_TRANSLATE_NOOP("FinSnap", "the part cannot stand so that this face takes fins")
# Faces of a prism count as parallel, square or equally turned within this, in
# radians; for an angle this small it also bounds the sine and the cosine that
# stand for it. Solids converted from a mesh or a STEP file are rarely exact.
PRISM_ANGLE_TOLERANCE = math.radians(d.RIGHT_ANGLE_TOLERANCE)


class EdgeSet:
    """Edges to ask whether one of them is the same as a given edge, as
    isSame() says, with one lookup by hash instead of a comparison with each."""

    def __init__(self, edges):
        self.by_hash = {}
        for edge in edges:
            self.by_hash.setdefault(edge.hashCode(), []).append(edge)

    def __contains__(self, edge):
        return any(edge.isSame(mine) for mine in self.by_hash.get(edge.hashCode(), ()))


def rims_on_axis(shape, side):
    """The rims of `shape` the round side `side` can stand on, best first.

    A rim counts where a flat face ends in a whole circle on the axis of the
    side. One that a chamfer joins to the side, a cone touching it, comes
    first: the chamfer gives the part more hold on the bed. The rims of the
    side itself come next, then any other on the axis, the bore of a tube or
    a smaller step of a shaft. Larger rims come before smaller ones.

    INPUTS this has to withstand:
      plain cylinder                        ->  both rims of the side
      chamfer on one rim                    ->  the small rim of the chamfer first,
                                                then the plain rim
      chamfer on both rims                  ->  the small rims of the chamfers; the
                                                rims of the side end in no flat face
      tube                                  ->  its outer rims, then its inner ones,
                                                on which it cannot stand
      shaft with a smaller step on the axis ->  the rims of the side before those of
                                                the step
      circle off the axis (a hole in the
        end face beside it)                 ->  not a rim of the side
    """
    # Edges looked up by their hash, then confirmed with isSame(): the same
    # edge with the same placement, whichever way round. One lookup each, not
    # a loop over every pair; a hash two edges share still tells them apart.
    own = EdgeSet(side.Edges)
    chamfered = EdgeSet(edge for face in shape.Faces if isinstance(face.Surface, Part.Cone)
                        and any(mine in own for mine in face.Edges) for edge in face.Edges)
    found = []
    for edge in shape.Edges:
        if not orient.is_rim(edge):
            continue
        circle = edge.Curve
        flat = any(face.findPlane() is not None for face in shape.ancestorsOfType(edge, Part.Face))
        if not (orient.on_axis(circle.Center, circle.Axis, side.Surface) and flat):
            continue
        if edge in chamfered:
            rank = RIM_CHAMFERED
        elif edge in own:
            rank = RIM_OWN
        else:
            rank = RIM_OTHER
        found.append((rank, -edge.Length, len(found), edge))
    return [edge for *_, edge in sorted(found)]


def best_face(shape, p, tried=()):
    """Number (from 0) of the face of `shape` that takes fins best: of the
    faces leaning over the bed, the largest one the fins can be built under.
    Faces numbered in `tried` were tried before and are passed over.

    INPUTS this has to withstand:
      part standing on an edge              ->  its largest leaning face that takes fins
      largest leaning face refuses fins
        (fins would run into the part)      ->  the next largest that takes them
      no face leans, or none takes fins     ->  FinError
    """
    return next(_or_refused(faces_taking_fins(shape, p, tried), NO_LEANING_FACE))


def faces_taking_fins(shape, p, tried=()):
    """The numbers (from 0) of the faces of `shape` leaning over the bed
    that the fins can be built under, the largest first, passing over those
    numbered in `tried`. Each is built to see that the fins fit, one at a
    time: best_face() takes the first and builds no further, Quick fins takes
    them all, to offer each."""
    leaning = []
    for number, face in enumerate(shape.Faces):
        try:
            frame_of(shape, face)
        except FinError:
            continue
        leaning.append((face.Area, number))
    for _, number in sorted(leaning, reverse=True):
        if number not in tried and first_taking_fins(shape, [number], p) is not None:
            yield number


def _or_refused(found, why):
    """What the iterator `found` yields, one at a time; FinError with `why`,
    translated, if it yields nothing at all."""
    empty = True
    for item in found:
        empty = False
        yield item
    if empty:
        raise FinError(translate("FinSnap", why))


def first_taking_fins(shape, numbers, p, errors=(FinError,)):
    """Of the faces of `shape` numbered `numbers`, in that order, the first
    the fins can be built under; None if none takes them. A build failing
    with one of `errors` passes to the next face; any other error is raised,
    so a fault in the kernel is not taken for a face without fins."""
    for number in numbers:
        try:
            geometry.build(shape, shape.Faces[number], p)
        except errors:
            continue
        return number
    return None


def stand_for_face(shape, number, p, angle_deg):
    """Stand `shape` so that face `number` leans over the bed by angle_deg and
    takes fins: (placement change, edge it stands on), the first of
    stands_for_face(), so it stands on the longest edge it can.

    INPUTS this has to withstand:
      planar face with straight edges       ->  stood on its longest edge that works
      longest edge does not carry the part
        or the fins do not fit there        ->  the next longest edge
      the kernel fails at one edge or rim   ->  the next one, as where fins do not fit
      round side                            ->  stood on the first rim of rims_on_axis()
                                                that works
      flat face without a straight edge     ->  leaned over the bed, resting on its
                                                lowest point (orient.lean()), edge None
      none works                            ->  FinError
    """
    return next(_or_refused(stands_for_face(shape, number, p, angle_deg), NO_STAND_FOR_FACE))


def stands_for_face(shape, number, p, angle_deg):
    """Every way to stand `shape` so that face `number` leans over the bed by
    angle_deg and takes fins, as (placement change, edge it stands on), one at
    a time.

    The face is laid onto the bed and the part turned about one of its straight
    edges, the longest first. A round side stands the part on a rim on its axis
    instead, see rims_on_axis(). A flat face without a straight edge, a round
    one, is leaned over the bed with the part resting on its lowest point,
    see orient.lean().
    """
    face = shape.Faces[number]
    if orient.is_round_side(face):
        tries = [(edge, partial(orient.stand_on_rim, shape, edge, orient.side_tilt(angle_deg), face))
                 for edge in rims_on_axis(shape, face)]
    else:
        straight = [edge for edge in face.Edges
                    if abs(edge.Length - (edge.Vertexes[-1].Point - edge.Vertexes[0].Point).Length) < d.TOLERANCE]
        tries = [(edge, partial(orient.stand, shape, edge, angle_deg, face))
                 for edge in sorted(straight, key=lambda candidate: -candidate.Length)]
        if not straight:
            tries = [(None, partial(orient.lean, shape, face, angle_deg))]
    # A fault in the kernel at one edge or rim passes to the next, as a face
    # without room for fins does: the next is there to fall back on.
    for edge, stand in tries:
        try:
            change = stand()
            standing = moved(shape, change)
            geometry.build(standing, standing.Faces[number], p)
        except (orient.OrientError, FinError, Part.OCCError):
            continue
        yield change, edge


# How Quick fins stands a part: the placement change, the face (number from 0)
# the fins go under, the edge or the two faces the part stands on, and the line
# it was leaned about where it stands on neither (orient.lean()), for the side view.
QuickPlan = namedtuple("QuickPlan", "change number edge beside line", defaults=(None,))


def quick_plan(shape, edges, faces, p, angle_deg):
    """How to stand `shape` for Quick fins and which face takes the fins.

    edges and faces are the selected elements of `shape` as (element, number
    from 0), faces in the order selected: the first face takes the fins, a
    second one is what the part rests on.

    SELECTIONS this has to withstand:
      one edge                              ->  stood on it: angle_deg on the bed, or the
                                                right angle of its faces; fins under the
                                                largest leaning face that takes them
      one edge off the bed, faces not at a
        right angle                         ->  FinError pointing to Stand on edge
      one rim                               ->  stood on it, its side leaning angle_deg
                                                as with the side selected; fins under it,
                                                larger flat faces passed over
      one rim, fins do not fit under its
        side, or it has no whole side       ->  fins under the largest leaning face
      one planar face                       ->  it leans angle_deg over the bed, on its
                                                longest edge that works; fins under it
      one side of a regular prism           ->  stood on the largest flat end that works,
                                                the right angle of the two; fins under
                                                the side; else as a chamfer
      one round side (cylinder, tube)       ->  stood on a rim, the side leaning
                                                angle_deg; one fin under it
      one rounded face (fillet)             ->  the part rests on it; fins under the
                                                largest leaning face
      one chamfer, wide or narrow           ->  as a rounded face: the part rests on it
      a face and one of its edges           ->  stood on that edge, the face leaning
                                                angle_deg; fins under it
      a face and an edge of another face    ->  OrientError from stand()
      a face, then a chamfer or fillet
        beside it, or any rounded face      ->  the part rests on the second; fins under
                                                the first
      two faces apart (beside a fillet)     ->  the part rests on what joins them; fins
                                                under the largest leaning face
      fins that do not fit under the face
        chosen                              ->  FinError
      anything else                         ->  FinError
    """
    return next(quick_plans(shape, edges, faces, p, angle_deg))


def quick_plans(shape, edges, faces, p, angle_deg):
    """Every way Quick fins can stand `shape` for the elements selected, as
    QuickPlans, one at a time: first the one quick_plan() takes, then the
    others the task panel can step to. A face selected alone stands on each
    of its edges that works; the side of a regular prism stands on one flat
    end, then lies on the bed; an edge, a rim or a part laid on a face or
    resting between two takes the fins under each face that takes them; a
    face with its edge, chamfer or fillet stands just one way. Raises what
    quick_plan() raises, before the first plan.
    """
    if len(edges) == 1 and not faces:
        edge = edges[0][0]
        if orient.is_rim(edge):
            # The fins go under its side, which leans angle_deg as any face under
            # fins does; under the largest leaning face only where they do not fit
            # under the side, or it has none.
            side = orient.side_of_rim(shape, edge)
            change = orient.stand_on_rim(shape, edge, orient.side_tilt(angle_deg), side)
            stood = moved(shape, change)
            sides = [] if side is None else [i for i, face in enumerate(shape.Faces) if face.isSame(side)]
            # A kernel fault under the side passes to the other faces as well:
            # they are there to fall back on.
            under_side = first_taking_fins(stood, sides, p, (FinError, Part.OCCError))
            numbers = itertools.chain([] if under_side is None else [under_side],
                                      faces_taking_fins(stood, p, sides))
            for number in _or_refused(numbers, NO_LEANING_FACE):
                yield QuickPlan(change, number, edge, ())
            return
        if not orient.on_bed(shape, edge) and orient.right_angle_faces(shape, edge) is None:
            raise FinError(translate("FinSnap", "This edge does not lie on the bed, and its faces do not meet at a "
                                                "right angle. Use Stand on edge with the edge and the face that "
                                                "is to lie on the bed, then Add fins."))
        angle = angle_deg if orient.on_bed(shape, edge) else orient.RIGHT_ANGLE_TILT
        yield from _under_each_face(shape, orient.stand(shape, edge, angle), edge, (), p)
        return
    if not edges and len(faces) == 1:
        face, number = faces[0]
        axis = prism_axis(shape, face)
        if axis is not None:
            upright = _stood_on_end(shape, face, number, axis, p)
            if upright is not None:
                yield upright
            try:
                yield from _under_each_face(shape, orient.lay_flat(shape, face), None, (), p)
            except (orient.OrientError, FinError, Part.OCCError):
                if upright is None:
                    raise
            return
        if not orient.is_round_side(face) and (face.findPlane() is None or is_chamfer(shape, face)):
            yield from _under_each_face(shape, orient.lay_flat(shape, face), None, (), p)
            return
        for change, edge in _or_refused(stands_for_face(shape, number, p, angle_deg), NO_STAND_FOR_FACE):
            # Without an edge, the face was leaned about LEAN_LINE.
            yield QuickPlan(change, number, edge, (), orient.LEAN_LINE if edge is None else None)
        return
    if len(edges) == 1 and len(faces) == 1:
        (edge, _), (face, number) = edges[0], faces[0]
        # stand() refuses an edge of another face itself.
        change = orient.stand(shape, edge, angle_deg, face)
        yield _checked(shape, QuickPlan(change, number, edge, ()), p)
        return
    if not edges and len(faces) == 2:
        (first, number), (second, _) = faces
        beside = any(edge.isSame(other) for edge in first.Edges for other in second.Edges)
        if beside or second.findPlane() is None:
            change = orient.lay_flat(shape, second)
            yield _checked(shape, QuickPlan(change, number, None, ()), p)
            return
        yield from _under_each_face(shape, orient.rest_between(shape, first, second), None, (first, second), p)
        return
    raise FinError(translate("FinSnap", "Select an edge or a face, a face and the edge or the chamfer or fillet "
                                        "it is to stand on, or the two faces beside a fillet."))


def _under_each_face(shape, change, edge, beside, p):
    """A QuickPlan for `shape` stood by `change` with the fins under each face
    that takes them, the largest first; FinError if none does."""
    for number in _or_refused(faces_taking_fins(moved(shape, change), p), NO_LEANING_FACE):
        yield QuickPlan(change, number, edge, beside)


def _flat_by_edge(shape):
    """The planar faces of `shape` by the edges they have, as (edge, face) by the
    hash of the edge, made once for many faces: looking each edge up on the shape
    takes far longer on a part of many faces."""
    by_edge = {}
    for face in shape.Faces:
        if face.findPlane() is not None:
            for edge in face.Edges:
                by_edge.setdefault(edge.hashCode(), []).append((edge, face))
    return by_edge


def _flat_beside(by_edge, face, edges):
    """The planar faces in `by_edge` (_flat_by_edge()) sharing one of `edges` with `face`."""
    beside = []
    for edge in edges:
        for own, other in by_edge.get(edge.hashCode(), ()):
            if (own.isSame(edge) and not other.isSame(face)
                    and not any(other.isSame(found) for found in beside)):
                beside.append(other)
    return beside


def _flat_round(by_edge, face):
    """The planar faces in `by_edge` sharing an edge of the outer wire of `face`:
    the sides of a prism meet there, what lies inside the side only recesses it,
    whatever the angle of its walls."""
    return _flat_beside(by_edge, face, face.OuterWire.Edges)


def _turn_about(axis, first, second):
    """The angle from the normal `first` to the normal `second` about `axis`,
    positive in its sense, in radians."""
    return math.atan2(first.cross(second).dot(axis), first.dot(second))


def _whole_side(by_edge, face):
    """The faces that make one flat side with `face`, `face` first: those parallel
    to it, joined to it edge to edge, as the halves a STEP file splits a side
    into. A groove across the side leaves what lies beyond it out: it shares no
    edge with the side."""
    normal = middle_normal(face)
    side = [face]
    for piece in side:
        for other in _flat_round(by_edge, piece):
            if (middle_normal(other).getAngle(normal) < PRISM_ANGLE_TOLERANCE
                    and not any(other.isSame(found) for found in side)):
                side.append(other)
    return side


def _side_after(by_edge, side, axis):
    """The whole side next after `side` going round `axis`: of the faces round it
    standing along the axis, the one turned on from it by the least. None where
    there is none."""
    here = middle_normal(side[0])
    turns = []
    for piece in side:
        for other in _flat_round(by_edge, piece):
            normal = middle_normal(other)
            turn = _turn_about(axis, here, normal)
            if abs(normal.dot(axis)) < PRISM_ANGLE_TOLERANCE and turn > PRISM_ANGLE_TOLERANCE:
                turns.append((turn, other))
    if not turns:
        return None
    return _whole_side(by_edge, min(turns, key=lambda found: found[0])[1])


def _ring_about(by_edge, face, axis):
    """The whole sides going round `axis` from the one of `face`, that one first;
    None where they do not come back to it."""
    ring = [_whole_side(by_edge, face)]
    while True:
        side = _side_after(by_edge, ring[-1], axis)
        if side is None:
            return None
        if any(piece.isSame(face) for piece in side):
            return ring
        if any(side[0].isSame(piece) for seen in ring for piece in seen):
            return None
        ring.append(side)


def _width_across(side, axis):
    """How wide the whole `side` is across `axis`, between its outermost corners."""
    across = axis.cross(middle_normal(side[0]))
    reach = [vertex.Point.dot(across) for piece in side for vertex in piece.Vertexes]
    return max(reach) - min(reach)


def _is_regular(ring, axis):
    """Whether the whole sides of `ring` make a regular prism about `axis`: enough
    of them, equally wide, each turned on from the last by the same angle."""
    if len(ring) < d.PRISM_LEAST_SIDES:
        return False
    normals = [middle_normal(side[0]) for side in ring]
    turns = [_turn_about(axis, one, after) for one, after in zip(normals, normals[1:] + normals[:1])]
    widths = [_width_across(side, axis) for side in ring]
    return (all(abs(turn - 2 * math.pi / len(ring)) < PRISM_ANGLE_TOLERANCE for turn in turns)
            and max(widths) - min(widths) < d.PRISM_WIDTH_TOLERANCE)


def prism_axis(shape, face):
    """The axis of the regular prism `face` is a side of: its whole sides, at
    least PRISM_LEAST_SIDES, close a ring equally wide at equal angles. None for
    any other face. A chamfer lies between its neighbours as such a side does,
    but breaks the ring's equal widths or angles.

    INPUTS this has to withstand:
      side of a hexagon or octagon prism    ->  its axis
      prism chamfered at its ends, a bore   ->  its axis
      a groove round the prism              ->  its axis, on either piece of the side
      a recess inside one side, square or
        with slanted walls, that side or
        another selected                    ->  its axis: its walls are not on the outer
                                                wire of the side
      a corner off by 0.01 mm               ->  its axis, within the tolerances
      a side split in halves along the axis ->  its axis, on either half
      a slot along the whole of a side      ->  None: the ring runs into the slot;
                                                the part lies on the side, as before
      a corner off by 1 mm                  ->  None: an uneven prism
      side of a box, a square bar           ->  None: fewer sides than a chamfer has
      side of a triangular prism            ->  None
      chamfer on one edge of a box          ->  None: angles differ
      all four edges of a box chamfered     ->  None: widths differ
      uneven hexagon                        ->  None
      side of half a hexagon                ->  None: the ring does not close
      rounded face, sides with fillets or
        turned corners between them         ->  None: they stand as any face does
      a large face with thousands of holes  ->  None, its holes not walked through
    """
    if face.findPlane() is None:
        return None
    by_edge = _flat_by_edge(shape)
    normal = middle_normal(face)
    for piece in _whole_side(by_edge, face):
        for other in _flat_round(by_edge, piece):
            axis = normal.cross(middle_normal(other))
            if axis.Length < PRISM_ANGLE_TOLERANCE:
                continue
            axis.normalize()
            ring = _ring_about(by_edge, face, axis)
            if ring is not None and _is_regular(ring, axis):
                return axis
    return None


def _stood_on_end(shape, face, number, axis, p):
    """The QuickPlan standing `shape` on what joins the side `face` of a prism to
    a flat end square to `axis`, the largest that works first, the fins under
    the side; None where no end carries it or the fins fit on none. The side and
    the end meet at a right angle, so the part stands at 45 degrees whatever
    angle is asked, as on an edge off the bed.

    INPUTS this has to withstand:
      sharp edge between side and end       ->  stood on that edge
      chamfer between side and end          ->  stood on the chamfer
      no flat end, a point at both          ->  None
      the larger end does not carry it      ->  the next
      fins that do not fit                  ->  None
      side in halves, as from a STEP file   ->  stood as if whole, the fins under the
                                                half selected
    """
    ends = [other for other in shape.Faces
            if other.findPlane() is not None and middle_normal(other).cross(axis).Length < PRISM_ANGLE_TOLERANCE]
    # On the joined shape: the other half of a side reaches the bed as well, and
    # the neighbour beyond it shares no edge with the half selected.
    try:
        whole = orient.joined(shape)
    except Part.OCCError:
        return None
    for end in sorted(ends, key=lambda candidate: -candidate.Area):
        try:
            change = orient.rest_between(whole, orient.counterpart(face, whole.Faces),
                                         orient.counterpart(end, whole.Faces))
            return _checked(shape, QuickPlan(change, number, None, (face, end)), p)
        except (orient.OrientError, FinError, Part.OCCError):
            continue
    return None


def is_chamfer(shape, face):
    """Whether planar `face` sits between two planar faces of `shape` like a
    chamfer: its normal turned part of the way from one neighbour's normal to
    the other's, whatever the angle or the two widths of the chamfer.

    INPUTS this has to withstand:
      chamfer on the edge of a box, equal or
        unequal widths, wide or narrow      ->  True
      chamfer at another angle than 45      ->  True
      side of a box                         ->  False: no two neighbours with its
                                                normal between theirs
      side of a prism of five sides or more ->  True: it lies between its neighbours
                                                too; quick_plans() asks prism_axis()
                                                first; to put fins under the side of
                                                an uneven one, select it with one of
                                                its edges
      rounded face                          ->  False
    """
    if face.findPlane() is None:
        return False
    normal = middle_normal(face)
    beside = [middle_normal(other) for other in _flat_beside(_flat_by_edge(shape), face, face.Edges)]
    for i, first in enumerate(beside):
        for second in beside[i + 1:]:
            apart = first.getAngle(second)
            # Between them: in their plane, and the two angles to it adding up
            # to the angle between them, neither of them zero.
            in_between = abs(first.getAngle(normal) + normal.getAngle(second) - apart) < d.TOLERANCE
            if d.TOLERANCE < apart < math.pi - d.TOLERANCE and in_between \
                    and min(first.getAngle(normal), second.getAngle(normal)) > d.TOLERANCE:
                return True
    return False


def _checked(shape, plan, p):
    """The plan, once the fins fit under its face; FinError naming why if not."""
    standing = moved(shape, plan.change)
    try:
        geometry.build(standing, standing.Faces[plan.number], p)
    except FinError as error:
        raise FinError(translate("FinSnap", "the fins do not fit under the selected face standing this way: %s")
                       % error)
    return plan
