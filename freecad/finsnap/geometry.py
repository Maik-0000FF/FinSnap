# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Fin geometry for one supported face.

The part stands tilted on the bed. A planar face of it leans outward over the
bed (its normal points down and to the side). Fins stand under that face: each
fin is a vertical wall whose inner edge, the flank, runs parallel to the face at
the gap distance. Horizontal tines reach across the gap and end on the face, or
the tine clearance short of it, as much shorter. A thin foot on the bed holds
the fin down.

The frame of the face is in face_frame.py, the tines in tine_rows.py, and
the way the quick fin stands a part on the bed in quick_stands.py.

INPUTS this has to withstand (build()):
  inclined planar face, part standing on the bed  ->  FinResult
  face not planar                       ->  FinError
  face vertical or flat (no lean)       ->  FinError: nothing to support
  face leaning upward (normal up)       ->  FinError: it is not an overhang
  face shorter along its edge than one
    fin plus both insets                ->  FinError
  corners: face shorter than a fin, a
    tine and FOOT_CLEARANCE             ->  FinError
  corners: each tine whole on the face,
    its outer side flush with the end   ->  FinResult, fins reach past the ends
  left or right corner                  ->  one fin, as on that end with corners
  left or right corner, face narrower
    than a tine                         ->  FinError
  tine_clearance > 0                    ->  tines end that far short of the face,
                                            measured along its normal; the fin stays
                                            at the gap, the tines as much shorter
  tine_clearance > 0, merged fins       ->  tines on the face, as with 0
  no tine fits below the top of the face ->  FinError
  hand-set first tine half a layer off
    the grid, rounding two tines closer
    than a free layer                   ->  the upper one moves up a layer
  face narrower than the fin at some
    tines (side of a frustum)           ->  those tines left out, warning
  face narrower than the fin at every
    tine                                ->  FinError
  fin moved by hand where the face is
    narrower than it at every tine, or
    past its end                        ->  FinError saying so, not naming a hole
  fixed tine count, some tines miss the
    face (narrow face or recess)        ->  those tines left out, warning
  face ending above the bed             ->  no tines below it
  manual fin_height below the first tine ->  FinError
  fins standing closer than they are
    thick plus FOOT_CLEARANCE           ->  FinError: they would collide
  fin collides with other geometry of
    the part (closer than the gap)      ->  FinError naming the distance
  tine wholly or partly over a recess
    or hole in the face                 ->  tine left out, warning
  upper tines of a fin over a recess,
    automatic fin height                ->  that fin ends at its highest tine left;
                                            the fin height of the result is the
                                            tallest fin
  upper tines over a recess, manual
    fin height                          ->  the fin keeps the height given
  every tine of a fin over a recess     ->  fin left out, warning
  face split by a groove into faces of
    its own in one plane                ->  one support: the fin reaches over the
                                            gap, tines over it left out, warning
  fins over the groove would run into the
    part higher up                      ->  fins under the selected face alone,
                                            warning naming why
  every tine of every fin over a recess ->  FinError
  fins removed by hand (left_out)       ->  not built, the others where they were
  every fin removed by hand             ->  FinError
  fin overlaps the part (separate mode) ->  FinError
  tine shorter than TINE_MIN_LENGTH_BEADS
    beads                               ->  warning in FinResult, no error
  face inclined outside FACE_ANGLE_MIN
    to FACE_ANGLE_MAX                    ->  warning in FinResult, no error
  round side                            ->  one fin under its lowest line, whatever
                                            the placement; a note to give the rim
                                            more hold on the bed
  part of a side                        ->  one fin under its lowest line, whatever
                                            the placement and shift; no note on a rim
  whole round side, two fins            ->  one parallel to the lowest line on each
                                            side of it, numbered from the left
  whole round side, three fins          ->  one under the lowest line, one parallel
                                            to it on each side, numbered from the left;
                                            their feet may overlap, see joined()
  two or three fins, contour not followed ->  FinError saying to follow it
  two or three fins, side too small for them
    to stand apart                      ->  FinError: they do not fit
  two or three fins, part of a side     ->  one fin: it has no line beside the lowest
                                            to count on
  two or three fins, part turned by hand ->  the fins stay in their places, as one does
"""

import math
from collections import namedtuple
from dataclasses import dataclass, field, replace
from functools import partial

import FreeCAD as App
import Part

from . import contour as contours
from . import defaults as d
from . import orient
from .face_frame import UP, FinError, Frame, HandEditError, across_side, beside_lowest, frame_of, support_of
from .i18n import QT_TRANSLATE_NOOP, translate
from .shapes import bounds
from .tine_rows import (NARROW_AT_EVERY_TINE, TINE_CUTS_IN, TINE_MISSES, extent_at, face_tines, restarted_tines,
                        tine_end_edges, tine_end_fault, tine_end_points, tine_start, tines_on_face, touching_at,
                        wide_enough)

# Said where fins beside the lowest line of a round side are asked for without
# the contour, on which alone they stand.
NOTE_SIDE_FINS_NEED_CONTOUR = QT_TRANSLATE_NOOP("FinSnap", "fins beside the lowest line of a round side stand on "
                                                           "its contour: turn on Follow the contour")
# Said where the end of a tine, measured on the part itself, lies further off
# its surface than the tine clearance and tolerance, or reaches into the part:
# the heights of those tines over the bed and the tolerance (mm).
NOTE_TINES_MISS = QT_TRANSLATE_NOOP("FinSnap", "tines at %s mm above the bed miss the face of the part by more "
                                               "than %.2f mm")
NOTE_TINES_CUT_IN = QT_TRANSLATE_NOOP("FinSnap", "tines at %s mm above the bed reach more than %.2f mm into the "
                                                 "part")
NOTE_TINES_SHORT = QT_TRANSLATE_NOOP("FinSnap", "tines are %.2f mm long, shorter than %.2f bead widths; the slicer "
                                               "may not print them to the face. A gap of %.2f mm makes them long "
                                               "enough")
NOTE_TINES_TOO_SHORT = QT_TRANSLATE_NOOP("FinSnap", "tines are %.2f mm long, shorter than %.2f bead widths; the "
                                                    "slicer may not print them to the face. No gap up to %.1f mm "
                                                    "makes them long enough: set a narrower bead")
NOTE_CONTOUR_RECEDES = QT_TRANSLATE_NOOP("FinSnap", "tines at %s mm above the bed left out: the contour falls back "
                                                    "further than the fin can follow without overhanging itself")


# What a warning of build() is about, for the task panel to show it: the
# numbers of the fins it names, tines left out, as shapes, and whether it is
# about the face. None of them, for a warning about the part as a whole.
WarningTarget = namedtuple("WarningTarget", "fins tines on_face")


@dataclass
class FinResult:
    fins: Part.Shape
    bodies: list
    tines: list
    height: float
    thickness: float
    tine_z: list
    positions: list
    foot_half_width: float
    warnings: list = field(default_factory=list)
    # What each warning is about, a WarningTarget, in the same order.
    warning_targets: list = field(default_factory=list)
    # The faces the fins stand under: the selected one, and the pieces beyond a
    # groove across it when the fins reach over it.
    carried: list = field(default_factory=list)
    # The number of each fin built, from the left, seen from outside: what
    # left_out of build() refers to.
    numbers: list = field(default_factory=list)
    # How many fins the face was planned for, before any was removed or left out.
    planned: int = 0
    # Tines that found no face, as shapes, for the red marks while editing.
    dropped: list = field(default_factory=list)
    # Where each fin built starts along the face (mm, as frame.along), by number.
    starts: dict = field(default_factory=dict)
    # The direction along the face, to the right seen from outside.
    along: App.Vector = None
    # The height of each fin built (mm, from the bed), by number.
    heights: dict = field(default_factory=dict)
    # The middle of the upright outer edge of each fin built, by number.
    edges: dict = field(default_factory=dict)
    # The direction away from the part, level with the bed: the outer edges face it.
    out: App.Vector = None
    # By number, the heights of the tines of each fin built that find the face
    # (mm, from the bed), all of them, also above a height of its own.
    touching_z: dict = field(default_factory=dict)
    # Where the face starts along it (mm, as starts): fins are placed from there.
    face_start: float = 0.0
    # The radius of a round side the fin stands under, 0 under a planar face.
    # Its fin stays under the lowest line; moved by hand, the part turns instead.
    radius: float = 0.0
    # The frame the fins were built in, to draw one at another height (fin_at()).
    frame: Frame = None
    # By number, the frames of fins beside the lowest line of a round side,
    # which stand in the plane of their own (side_frames()).
    frames: dict = field(default_factory=dict)
    # By number, how far a fin planned over a hole was moved beside it (mm, as
    # starts); its start is planned plus its shift by hand plus this.
    moved: dict = field(default_factory=dict)


def room_for_one_fin(p, frame, thickness):
    """The least stretch along the face a fin needs: inside both insets, or
    for a fin on each corner, both tines and the clearance between the fins.
    Under a round side only the tine touches it; the fin stands clear of it."""
    if frame.round_side:
        return p.tine_width
    if p.placement == d.PLACEMENT_CORNERS:
        return thickness + d.FOOT_CLEARANCE + p.tine_width
    if p.placement in d.PLACEMENT_ONE_CORNER:
        return p.tine_width
    return thickness + 2 * p.end_inset


def thickness_for(p, height):
    if p.fin_thickness > 0:
        return p.fin_thickness
    grown = d.FIN_THICKNESS_BASE * max(1.0, height / d.FIN_THICKNESS_BASE_HEIGHT)
    return max(grown, d.FIN_MIN_BEADS * p.bead_width)


def positions_for(p, frame, thickness):
    """Start of each fin along the face."""
    if frame.round_side:
        # One fin, its tine in the middle under the lowest line, whatever the
        # placement; on a whole side, if asked, one parallel on each side of
        # it instead, or as well.
        middle = (frame.along_min + frame.along_max - thickness) / 2
        if not (frame.whole_side and p.round_fins != d.ROUND_FINS_ONE):
            return [middle]
        pitch = beside_lowest(frame.radius, p.round_fin_angle)
        positions = [middle - pitch, middle, middle + pitch] if p.round_fins == d.ROUND_FINS_THREE \
            else [middle - pitch, middle + pitch]
        if positions[1] - positions[0] < thickness + d.FOOT_CLEARANCE:
            raise FinError(translate("FinSnap", "%d fins do not fit side by side on this face") % len(positions))
        return positions
    if p.placement == d.PLACEMENT_CORNERS or p.placement in d.PLACEMENT_ONE_CORNER:
        # The tine sits in the middle of the fin; its outer side ends flush
        # with the end of the face, the fin reaches past it. Along the face
        # runs to the right, seen from outside.
        overhang = (thickness - p.tine_width) / 2
        positions = [frame.along_min - overhang, frame.along_max - p.tine_width - overhang]
        if p.placement == d.PLACEMENT_CORNER_LEFT:
            return positions[:1]
        if p.placement == d.PLACEMENT_CORNER_RIGHT:
            return positions[1:]
        if positions[1] - positions[0] < thickness + d.FOOT_CLEARANCE:
            raise FinError(translate("FinSnap", "the face is too short for a fin on each corner"))
        return positions

    lo = frame.along_min + p.end_inset
    hi = frame.along_max - p.end_inset - thickness
    if hi < lo - d.TOLERANCE:
        raise FinError(translate("FinSnap", "the face is too short for a fin of %.2f mm") % thickness)
    middle = (lo + hi) / 2
    span = hi - lo

    if p.placement == d.PLACEMENT_CENTER:
        count = 1
    elif p.placement == d.PLACEMENT_ENDS:
        count = 2
    elif p.placement == d.PLACEMENT_DISTRIBUTED:
        count = p.fin_count
    else:
        length = frame.along_max - frame.along_min
        count = max(1, math.ceil(length / p.face_length_per_fin))

    if count == 1:
        return [middle]
    pitch = span / (count - 1)
    if pitch < thickness + d.FOOT_CLEARANCE:
        raise FinError(translate("FinSnap", "%d fins do not fit side by side on this face") % count)
    return [lo + i * pitch for i in range(count)]


def foot_half_width_for(p, half_length, thickness, positions):
    wanted = p.foot_half_width if p.foot_half_width > 0 else half_length * p.foot_width_ratio
    if len(positions) > 1:
        pitch = min(b - a for a, b in zip(positions, positions[1:]))
        wanted = min(wanted, (pitch - d.FOOT_CLEARANCE) / 2)
    return max(wanted, thickness / 2)


def flank_at(p, frame, z):
    """Where the flank of a fin stands at height z (absolute): the fin
    distance off the face, or along the contour the frame follows."""
    if frame.contour is not None:
        return frame.contour.flank(z - frame.bed_z)
    return frame.s_flank(z, p.gap)


def flank_outline(p, frame, low, high):
    """The flank of a fin from height `high` down to `low` (absolute), as
    (s, z) points: its two ends under a face, every bend along a contour."""
    if frame.contour is not None:
        return [(s, z + frame.bed_z) for s, z in frame.contour.outline(low - frame.bed_z, high - frame.bed_z)]
    return [(flank_at(p, frame, high), high), (flank_at(p, frame, low), low)]


def fin_out(p, frame, height):
    """Where the upright outer edge of a fin `height` high stands: the top
    width past the furthest out its flank reaches above the foot."""
    zb = frame.bed_z
    return max(s for s, _ in flank_outline(p, frame, zb + p.foot_height, zb + height)) + p.fin_plateau


def foot_span(p, frame, height):
    """Where the foot starts and ends, measured outward.

    The foot has vertical sides. It starts where the flank passes its top
    edge, so it keeps the gap to the part along its whole height; lower down
    the flank lies further in and the clearance only grows.
    """
    s_from = flank_at(p, frame, frame.bed_z + p.foot_height)
    if frame.foot_from is not None:
        s_from = max(s_from, frame.foot_from)
    return s_from, fin_out(p, frame, height) + p.foot_overhang


def foot(p, frame, t0, thickness, s_from, s_to, half_width):
    z = frame.bed_z
    height = p.foot_height
    if p.foot_shape == d.FOOT_RECTANGLE:
        t_mid = t0 + thickness / 2
        return frame.section(t_mid - half_width, [(s_from, z), (s_to, z), (s_to, z + height),
                                                  (s_from, z + height)], 2 * half_width)

    half_length = (s_to - s_from) / 2
    centre = frame.point(t0 + thickness / 2, s_from + half_length, z)
    major, minor = (frame.out, frame.along) if half_length >= half_width else (frame.along, frame.out)
    a, b = max(half_length, half_width), min(half_length, half_width)
    ellipse = Part.Ellipse(centre + major * a, centre + minor * b, centre)
    return Part.Face(Part.Wire(ellipse.toShape())).extrude(UP * height)


def _mm_list(values):
    """Lengths for a message, smallest first: "1.0, 6.0"."""
    return ", ".join("%.1f" % value for value in sorted(values))


def beside_hole(frame, rests, t0, thickness, others):
    """Where along the face the fin planned to start at t0, whose tines find
    no face there, starts nearest where `rests` finds a tine of it on the
    face; None if nowhere. It keeps within the face and between its neighbours
    among the fins starting at `others`, clear of them, so the fins keep
    their order from the left; tried a fin thickness at a time, either way
    in turn.

    INPUTS this has to withstand:
      a hole under the middle of the fin     ->  the nearest start beside it, the
                                                 nearer side first
      a hole wider than the room between
        its neighbours                       ->  None: left out, as before
      a neighbour beside the hole            ->  not passed: the search ends clear
                                                 of it
      the end of the face reached            ->  that way given up, the other tried on
    """
    clear = thickness + d.FOOT_CLEARANCE
    before = [other for other in others if other < t0 - d.TOLERANCE]
    after = [other for other in others if other > t0 + d.TOLERANCE]
    low = max([frame.along_min] + [other + clear for other in before])
    high = min([frame.along_max - thickness] + [other - clear for other in after])
    steps = int(max(t0 - low, high - t0) / thickness) + 1
    for step in range(1, steps + 1):
        for t in (t0 - step * thickness, t0 + step * thickness):
            if low - d.TOLERANCE <= t <= high + d.TOLERANCE and rests(t):
                return t
    return None


def one_fin(p, frame, t0, height, thickness, half_foot, tine_z):
    """A fin without tines, its tines, which end on the face, and the middle
    of the upright outer edge of its blade, where the handles go."""
    zb, top = frame.bed_z, frame.bed_z + height
    s_out = fin_out(p, frame, height)

    if p.foot_shape == d.FOOT_NONE:
        body = frame.section(t0, [(s_out, zb), (s_out, top)] + flank_outline(p, frame, zb, top), thickness)
    else:
        # Below the top of the foot the slanted flank would only add a thin tip
        # under the part; the blade ends vertically there and the foot carries it.
        s_from, s_to = foot_span(p, frame, height)
        foot_top = zb + p.foot_height
        body = frame.section(t0, [(s_from, zb), (s_out, zb), (s_out, top)]
                             + flank_outline(p, frame, foot_top, top), thickness)
        body = body.fuse(foot(p, frame, t0, thickness, s_from, s_to, half_foot))
    outer_middle = frame.point(t0 + thickness / 2, s_out, zb + height / 2)

    tines = []
    t_tine = tine_start(p, t0, thickness)
    for z in tine_z:
        bottom, tine_top = zb + z, zb + z + p.tine_height
        left, right = tine_end_edges(p, frame, z)
        # The fin edge furthest out along the tine: the flank at its ends, or
        # the vertical inner end of the foot for a tine below the top of the
        # foot. Measured from there, a tine always reaches into the fin.
        edge = max(flank_at(p, frame, bottom), flank_at(p, frame, tine_top))
        if p.foot_height > 0 and bottom < zb + p.foot_height:
            edge = max(edge, foot_span(p, frame, height)[0])
        s_into_fin = edge + d.TINE_INTO_FIN

        def outline(ends):
            return [(ends[0], bottom), (s_into_fin, bottom), (s_into_fin, tine_top), (ends[1], tine_top)]
        if left == right:
            tines.append(frame.section(t_tine, outline(left), p.tine_width))
        else:
            # Its end slants across it: ruled from one edge of the tine to the other.
            rings = [[frame.point(t, s, z_at) for s, z_at in outline(ends)]
                     for t, ends in ((t_tine, left), (t_tine + p.tine_width, right))]
            tines.append(Part.makeLoft([Part.makePolygon(ring + ring[:1]) for ring in rings], True, True))
    return body, tines, outer_middle


def fin_at(p, result, number, height):
    """Fin `number` of `result` as it would be `height` high (mm, from the
    bed), with the tines that find the face up to that height, as a list of
    shapes: where it stands and how thick it is as built, unchecked, to show
    where a fin cannot be built.

    INPUTS this has to withstand:
      height between its tines              ->  the fin, ending above the last tine below
      height above the face                 ->  the fin as high, its flank on along the face
      height below its first tine           ->  the fin without tines
      height at or below the top of its
        foot, down to 0                     ->  the fin as high as its foot: lower, its
                                                outline would cross itself
      no foot, height above 0               ->  the fin as high
    """
    height = max(height, p.foot_height)
    index = result.numbers.index(number)
    tine_z = [z for z in result.touching_z.get(number, []) if z + p.tine_height <= height + d.TOLERANCE]
    body, tines, _ = one_fin(p, result.frames.get(number, result.frame), result.positions[index], height,
                             result.thickness, result.foot_half_width, tine_z)
    return [body] + tines


def check(p, part, fins, bodies, slack=0.0):
    """Fins clear of the part, no closer than their distance from the face,
    give or take `slack`: along a contour, CONTOUR_TOLERANCE. That every tine
    reaches the face is settled when the tines are chosen, by contact_share()."""
    if p.connection == d.CONNECTION_SEPARATE:
        overlap = fins.common(part).Volume
        if overlap > d.TOLERANCE:
            raise FinError(translate("FinSnap", "the fins overlap the part by %.4f mm³") % overlap)

    for body in bodies:
        distance = body.distToShape(part)[0]
        if distance < p.gap - slack - d.TOLERANCE:
            raise FinError(translate("FinSnap", "a fin comes within %.3f mm of the part, closer than the %.3f mm it "
                                                  "keeps from the face")
                           % (distance, p.gap))


def build(part, face, p, tine_count=None, left_out=(), shifts=None, heights=None):
    """Fins under `face` of `part`, reaching over a groove to the pieces beyond
    it. tine_count overrides p.tine_count (counter fin). Fins are named by their
    number from the left, seen from outside, looking at the face, counting from
    1: left_out are removed by hand, shifts moves fins along the face (mm, to
    the right is positive), heights sets the height of single fins (mm).

    The fins over a groove are taller, and where the part reaches out in front
    of the face higher up they would run into it. Then they stand under the
    selected face alone, as they did before pieces were carried along. A
    change by hand that does not fit over the groove is refused instead: a
    drag never changes which faces the fins carry.
    """
    p.validate()
    shifts, heights = shifts or {}, heights or {}
    support = support_of(part, face)
    if support is face:
        return _build(part, face, face, p, tine_count, left_out, shifts, heights)
    try:
        return _build(part, face, support, p, tine_count, left_out, shifts, heights)
    except HandEditError:
        raise
    except FinError as error:
        reason = str(error)
    alone = _build(part, face, face, p, tine_count, left_out, shifts, heights)
    alone.warnings.append(translate("FinSnap", "fins under the selected face alone, not reaching over the "
                                               "groove: %s") % reason)
    alone.warning_targets.append(WarningTarget([], [], True))
    return alone


# One fin as planned: where it starts, how high it is, the heights its tines
# are tried at, which of them rest on the face, and every height at which a
# tine there would.
PlannedFin = namedtuple("PlannedFin", "number t0 height candidate_z on_face touching")
# The fins of a face as planned, before any is built.
FacePlan = namedtuple("FacePlan", "frame height thickness tine_z gap_z narrow_heights positions face_start "
                                  "starts half_foot fins moved fins_left_out")


def side_frames(part, frame, p, width):
    """By number, the frames of the two fins beside the fin under the lowest
    line of the whole round side of `frame`, or in its place; each at the place
    positions_for() gives it, as thick as `width` at most. The side falls away
    towards them: the gap and the clearance, measured in the upright plane, are
    as much longer that the part stays as far off along its normal.

    INPUTS this has to withstand:
      fin to the left, or the right         ->  its contour and tine edges at its own
                                                planes, nearest the lowest line first
      side with a step of another radius    ->  the gap measured for the radius of the
                                                side; check() allows for the difference
      a plane that misses the part          ->  contour.ContourError, as for one fin
    """
    middle = (frame.along_min + frame.along_max) / 2
    pitch = beside_lowest(frame.radius, p.round_fin_angle)
    foot_from = flank_at(p, frame, frame.bed_z + p.foot_height)
    frames = {}
    numbers = (1, 3) if p.round_fins == d.ROUND_FINS_THREE else (1, 2)
    for number, sense in zip(numbers, (-1, 1)):
        centre = middle + sense * pitch
        nearest, furthest = centre - sense * width / 2, centre + sense * width / 2

        def measured_at(t):
            share = across_side(frame.radius, t - middle)
            return replace(p, gap=p.gap * share, tine_clearance=p.tine_clearance * share)
        line = contours.beside(part, frame, measured_at(nearest), nearest, furthest)
        edges = tuple(contours.across(part, frame, measured_at(t), t)
                      for t in (centre - p.tine_width / 2, centre + p.tine_width / 2))
        frames[number] = replace(frame, contour=line, tine_edges=edges, foot_from=foot_from,
                                 face_top_z=frame.bed_z + line.top)
    return frames


def _plan(frame, support, p, all_z, face_height, reach, count, restart, left_out, shifts, heights, slices,
          frames):
    """The fins of the face planned for a fin height of at least `reach`,
    from which their thickness and foot follow. With `restart`, each fin is
    tried on its own tine grid (restarted_tines()), at its planned place and
    at every place it might move to beside a hole; without, on `all_z`.
    `slices` is the dict of extent_at() kept for the build. `frames` holds,
    by number, the frame of a fin that has one of its own (side_frames()), on
    which it gets its own heights of tines."""
    height = max(face_height, reach)
    thickness = thickness_for(p, height)
    if p.tine_width > thickness:
        raise FinError(translate("FinSnap", "tines (%.2f mm) are wider than the fin (%.2f mm)")
                       % (p.tine_width, thickness))
    tine_z, low, high, gap_z = tines_on_face(support, frame, all_z, p, room_for_one_fin(p, frame, thickness),
                                             slices)
    # Also with a fixed tine count: tines the narrow face cannot take are left
    # out and named, as over a recess, rather than refusing the whole fin.
    narrow_heights = set(all_z) - set(tine_z) - set(gap_z)
    if narrow_heights:
        # Fewer tines make a lower and so a thinner fin; it still fits where the thicker one did.
        height = max(p.fin_height if p.fin_height > 0 else tine_z[-1] + p.tine_height, reach)
        thickness = thickness_for(p, height)
    # Fins left out are named by their distance from this end of the face.
    face_start = frame.along_min
    # The face as a whole, before it is narrowed to the stretch every tine
    # shares: tines_at() measures a fin moved by hand on it.
    whole_face = frame
    frame = replace(frame, along_min=low, along_max=high)
    positions = positions_for(p, frame, thickness)
    if frame.round_side:
        # The fin stays under the lowest line, and its shift is how far the
        # part was turned (turn_of()); measured from the middle, the place on
        # the face is that shift.
        face_start = (low + high) / 2
    if frame.fixed_fin:
        # A part of a side has no turn to show: its fin stands where it stands.
        shifts = {}

    def refused(message, kind=FinError):
        """A FinError, or `kind`, that says how many fins the face is planned
        for: with another count, changes by hand name other fins, and the
        caller drops them instead of refusing."""
        error = kind(message)
        error.planned = len(positions)
        return error

    s_from, s_to = foot_span(p, frame, height)
    # Fins moved along the face by hand stay clear of their neighbours and in
    # their order: the numbers count from the left, also after a move.
    starts = {number: t0 + shifts.get(number, 0.0) for number, t0 in enumerate(positions, 1)}
    # Under a round side the shift is how far the part was turned, not a move
    # of any fin: they stay where they are planned.
    places = dict(enumerate(positions, 1)) if frame.round_side else starts
    standing = [(places[number], number) for number in sorted(places) if number not in left_out]
    for (first, one), (second, other) in zip(standing, standing[1:]):
        if second < first:
            raise refused(translate("FinSnap", "fin %d would pass fin %d; a fin stays between its neighbours")
                           % (one, other), HandEditError)
        if second - first < thickness + d.FOOT_CLEARANCE - d.TOLERANCE:
            raise refused(translate("FinSnap", "fins %d and %d stand %.2f mm apart, closer than %.2f mm")
                           % (one, other, second - first, thickness + d.FOOT_CLEARANCE), HandEditError)
    if all(number in left_out for number in range(1, len(positions) + 1)):
        raise refused(translate("FinSnap", "every fin is removed; delete the fins instead, or bring them back"),
                      HandEditError)
    # The feet under a round side may overlap, and are joined (joined()): one
    # fin keeps the foot it has alone, as wide as it holds best.
    half_foot = foot_half_width_for(p, (s_to - s_from) / 2, thickness,
                                    [] if frame.round_side else [t0 for t0, _ in standing])

    def tines_at(t, own, own_frame=frame):
        """The heights the tines of a fin starting at t are planned at, those
        of them below a height of its own, and those of its grid left out
        where the face is narrower than the fin (wide_enough()).

        INPUTS this has to withstand:
          fin within the stretch every tine
            of the face shares               ->  every tine of its grid planned
          fin moved by hand past that stretch,
            restart on or off                ->  the tines where the face is wide
                                                 enough under it, the others narrow
          fin past the end of the face       ->  none planned, every one narrow
                                                 (restart off) or no grid (on)
          round side                         ->  every tine planned: only the tine
                                                 rests on it, on a stretch narrower
                                                 than the fin
          fin beside the lowest line         ->  the tines of its own contour
        """
        own_z = None
        room = own_frame.face_top_z - own_frame.bed_z - d.FACE_TOP_MARGIN
        if restart:
            own_z = restarted_tines(p, frame, support, t, thickness,
                                    p.fin_height if p.fin_height > 0 else room, count)
        elif own_frame is not frame:
            own_z = face_tines(p, own_frame, count, False)[0]
        grid = tine_z if own_z is None else own_z
        if frame.round_side:
            planned_z, narrow = grid, []
        else:
            # Measured on the whole face: a fin moved past the stretch every
            # tine of the face shares keeps the tines where it is wide enough.
            wide = [wide_enough(extent_at(support, whole_face, z, p, slices), p, t, thickness) for z in grid]
            planned_z = [z for z, fits in zip(grid, wide) if fits]
            narrow = [z for z, fits in zip(grid, wide) if not fits]
        return planned_z, [z for z in planned_z if own is None or z + p.tine_height <= own + d.TOLERANCE], narrow

    def rests_at(t, own):
        """Whether a tine of the fin starting at t lies on the face."""
        planned_z, candidate_z, _ = tines_at(t, own)
        return any(z in candidate_z for z in touching_at(frame, support, p, planned_z, t, thickness))

    fins = []
    # Fins planned over a hole and moved beside it, as (number, mm moved).
    moved_fins = []
    fins_left_out = []
    # Whether every fin left out had no tine where the face is wide enough
    # under it, or no face under it at all, rather than its tines over a
    # hole: said so when none is left. Only width leaves no tine planned.
    all_too_narrow = True
    for number, t0 in starts.items():
        if number in left_out:
            continue
        if frame.round_side:
            t0 = positions[number - 1]
        own_frame = frames.get(number, frame)
        room = own_frame.face_top_z - own_frame.bed_z - d.FACE_TOP_MARGIN
        # A fin height set by hand for this fin alone: tines above it are left out.
        own = heights.get(number)
        if own is not None and own > room + d.TOLERANCE:
            raise refused(translate("FinSnap", "fin %d is %.2f mm high, above the face (%.2f mm)")
                           % (number, own, room), HandEditError)
        planned_z, candidate_z, narrow = tines_at(t0, own, own_frame)
        if own is not None and not candidate_z:
            raise refused(translate("FinSnap", "fin %d is lower than its first tine") % number, HandEditError)
        # A tine wholly or partly over a recess or a hole in the face would hang
        # free there; it is left out, and a fin without any tine left with it.
        # Tried at every height planned, also above a height of its own: those
        # are the heights the fin can be given with a tine on top.
        touching = touching_at(own_frame, support, p, planned_z, t0, thickness)
        if not any(z in touching for z in candidate_z) and not frame.round_side and number not in shifts:
            # Planned over a hole, the fin moves along the face to the nearest
            # place its tines rest; one moved by hand stays where it was put.
            others = [starts[n] for n in starts if n != number and n not in left_out]
            moved_to = beside_hole(frame, partial(rests_at, own=own), t0, thickness, others)
            if moved_to is not None:
                moved_fins.append((number, moved_to - t0))
                t0 = starts[number] = moved_to
                planned_z, candidate_z, narrow = tines_at(t0, own)
                touching = touching_at(frame, support, p, planned_z, t0, thickness)
        on_face = [z in touching for z in candidate_z]
        # Tines of its own grid left out where the face is too narrow are named
        # with those of the face, as far as the fin reaches up to them.
        narrow_heights.update(z for z in narrow if own is None or z + p.tine_height <= own + d.TOLERANCE)
        kept_z = [z for z, whole in zip(candidate_z, on_face) if whole]
        if not kept_z:
            fins_left_out.append(t0 + thickness / 2 - face_start)
            all_too_narrow = all_too_narrow and not planned_z
            continue
        # An automatic fin ends at its highest tine left, so no part of it
        # stands above the last contact with the face.
        if own is not None:
            fin_height = own
        else:
            fin_height = p.fin_height if p.fin_height > 0 else kept_z[-1] + p.tine_height
        fins.append(PlannedFin(number, t0, fin_height, candidate_z, on_face, sorted(touching)))
    if not fins and fins_left_out and all_too_narrow:
        raise refused(translate("FinSnap", NARROW_AT_EVERY_TINE) % thickness)
    if not fins:
        raise refused(translate("FinSnap", "no tine finds the face; it has a recess or hole at every tine"))
    return FacePlan(frame, height, thickness, tine_z, gap_z, narrow_heights, positions, face_start,
                    starts, half_foot, fins, moved_fins, fins_left_out)


def _build(part, face, support, p, tine_count, left_out, shifts, heights):
    frame = frame_of(part, face, support)
    # The one fin under a whole round side follows the contour of the part up
    # to its top; the tine ends are measured on the part then, not the side.
    surface = support
    if frame.whole_side and p.follow_contour:
        try:
            # As thick as a fin as high as the part, which no fin is thicker than.
            line = contours.of(part, frame, p, thickness_for(p, bounds(part).ZLength))
        except contours.ContourError as error:
            raise FinError(str(error))
        frame = replace(frame, contour=line, face_top_z=frame.bed_z + line.top)
        surface = Part.makeCompound(part.Faces)
    # Fins beside the lowest line stand on the contour alone: only that says
    # what they rest on there.
    frames = {}
    if frame.whole_side and p.round_fins != d.ROUND_FINS_ONE:
        if frame.contour is None:
            raise FinError(translate("FinSnap", NOTE_SIDE_FINS_NEED_CONTOUR))
        try:
            frames = side_frames(part, frame, p, thickness_for(p, bounds(part).ZLength))
        except contours.ContourError as error:
            raise FinError(str(error))
    # The slices of the face at the height of a tine, kept for every plan of this build.
    slices = {}
    count = p.tine_count if tine_count is None else tine_count
    restart = p.tine_restart and not frame.round_side
    all_z, face_height = face_tines(p, frame, count, restart)
    plan = _plan(frame, support, p, all_z, face_height, 0.0, count, restart, left_out, shifts, heights,
                 slices, frames)
    # With the restart a fin can reach above the tines of the face as a
    # whole, up to the top of the stretch it stands on; the fins are planned
    # again, as thick and with as large a foot as the highest of them needs.
    # The height planned for only grows, each time to that of a fin, and no
    # fin is higher than the face, so this ends. A height set by hand counts
    # too: it ends on a tine of its fin, which may lie above those of the face.
    while restart:
        reach = max(fin.height for fin in plan.fins)
        if reach <= plan.height + d.TOLERANCE:
            break
        plan = _plan(frame, support, p, all_z, face_height, reach, count, restart, left_out, shifts,
                     heights, slices, frames)
    frame, thickness = plan.frame, plan.thickness

    bodies = []
    all_tines = []
    dropped = []
    # The fins with tines left out over a recess, by number.
    gapped = []
    pieces = []
    # Tines over the gap between two faces in one plane are named as over a recess.
    gap_heights = set(plan.gap_z)
    # Along a contour: tines left out where it falls back further than the
    # flank can follow, and the fins they belong to. Those in a recess the
    # fin bridges are left out as asked, without a word.
    receded_heights, receded_fins, receded_tines = set(), [], []
    edges = []
    # Tines whose end misses the face or reaches into the part, by fault, as
    # (fin number, height, tine).
    off_ends = {TINE_MISSES: [], TINE_CUTS_IN: []}
    for fin in plan.fins:
        own_frame = frames.get(fin.number, frame)
        body, tines, edge = one_fin(p, own_frame, fin.t0, fin.height, thickness, plan.half_foot, fin.candidate_z)
        kept = [tine for tine, whole in zip(tines, fin.on_face) if whole]
        left = [(z, tine) for z, tine, whole in zip(fin.candidate_z, tines, fin.on_face) if not whole]
        dropped += [tine for _, tine in left]
        if frame.contour is not None:
            receded = [(z, tine) for z, tine in left if frame.contour.receded(z, z + p.tine_height)]
            receded_heights.update(z for z, _ in receded)
            receded_tines += [tine for _, tine in receded]
            if receded:
                receded_fins.append(fin.number)
        elif left:
            gap_heights.update(z for z, _ in left)
            gapped.append(fin.number)
        edges.append(edge)
        bodies.append(body)
        all_tines.extend(kept)
        # Each tine kept, its end measured against the part itself.
        for z, tine in zip([z for z, whole in zip(fin.candidate_z, fin.on_face) if whole], kept):
            fault = tine_end_fault(surface, tine_end_points(p, own_frame, fin.t0, thickness, z), p.clearance)
            if fault is not None:
                off_ends[fault].append((fin.number, z, tine))
        # One general fuse instead of one tine after the other: the lowest tine
        # sits on the top of the foot, where foot, flank and tine share an edge,
        # and fusing them pairwise fails on that edge.
        pieces.append(body.multiFuse(kept).removeSplitter())

    fins = Part.makeCompound(pieces)
    slack = 0.0 if frame.contour is None else d.CONTOUR_TOLERANCE
    if frames:
        # A step of another radius falls away otherwise than the gap of the
        # side allows for, by at most what the furthest place round the side asks.
        slack += p.gap * (1 - 1 / across_side(1.0, math.sin(math.radians(d.ROUND_FIN_ANGLE_MAX))))
    check(p, part, fins, bodies, slack)

    # Each warning with what it is about, as a WarningTarget, in the same order.
    warnings, targets = [], []
    if gap_heights:
        warnings.append(translate("FinSnap", "tines at %s mm above the bed left out: a recess or hole in the "
                                  "face lies under them") % _mm_list(gap_heights))
        targets.append(WarningTarget(gapped, dropped, False))
    if receded_heights:
        warnings.append(translate("FinSnap", NOTE_CONTOUR_RECEDES) % _mm_list(receded_heights))
        targets.append(WarningTarget(receded_fins, receded_tines, False))
    for fault, note in ((TINE_MISSES, NOTE_TINES_MISS), (TINE_CUTS_IN, NOTE_TINES_CUT_IN)):
        found = off_ends[fault]
        if found:
            warnings.append(translate("FinSnap", note) % (_mm_list({z for _, z, _ in found}), d.TINE_END_TOLERANCE))
            targets.append(WarningTarget(sorted({number for number, _, _ in found}), [tine for _, _, tine in found],
                                         False))
    if plan.moved:
        warnings.append(translate("FinSnap", "fins moved along the face to where their tines rest, beside a "
                                  "hole or recess under their planned place: %s") % ", ".join(
            translate("FinSnap", "fin %d by %.2f mm") % (number, mm) for number, mm in plan.moved))
        targets.append(WarningTarget([number for number, _ in plan.moved], [], False))
    if plan.fins_left_out:
        warnings.append(translate("FinSnap", "fins at %s mm from the end of the face left out: none of their "
                                  "tines lies wholly on the face") % _mm_list(plan.fins_left_out))
        targets.append(WarningTarget([], [], True))
    if plan.narrow_heights:
        warnings.append(translate("FinSnap", "tines at %s mm above the bed left out: the face is narrower "
                                  "there than the fin") % _mm_list(plan.narrow_heights))
        targets.append(WarningTarget([], [], True))
    angle = math.degrees(math.acos(min(1.0, -frame.n_z)))
    if not d.FACE_ANGLE_MIN <= angle <= d.FACE_ANGLE_MAX:
        warnings.append(translate("FinSnap", "the face is inclined %.0f degrees to the bed, outside "
                                  "%.0f to %.0f") % (angle, d.FACE_ANGLE_MIN, d.FACE_ANGLE_MAX))
        targets.append(WarningTarget([], [], True))
    tine_length = p.tine_length / frame.n_out
    shortest = d.TINE_MIN_LENGTH_BEADS * p.bead_width
    if tine_length < shortest:
        # The gap that makes them as long, along the face normal, the
        # clearance on top; rounded up to GAP_HINT_STEP.
        enough = math.ceil((shortest * frame.n_out + p.clearance) / d.GAP_HINT_STEP - d.TOLERANCE) * d.GAP_HINT_STEP
        if enough <= d.GAP_MAX + d.TOLERANCE:
            warnings.append(translate("FinSnap", NOTE_TINES_SHORT) % (tine_length, d.TINE_MIN_LENGTH_BEADS, enough))
        else:
            # No gap taken makes them long enough: the bead is too wide.
            warnings.append(translate("FinSnap", NOTE_TINES_TOO_SHORT)
                            % (tine_length, d.TINE_MIN_LENGTH_BEADS, d.GAP_MAX))
        targets.append(WarningTarget([fin.number for fin in plan.fins], [], False))
    if frame.whole_side:
        warnings.append(translate("FinSnap", "the part stands on one point of its rim: a chamfer on the rim and "
                                  "a brim in the slicer give it more hold on the bed"))
        targets.append(WarningTarget([], [], False))

    numbers = [fin.number for fin in plan.fins]
    fin_heights = [fin.height for fin in plan.fins]
    return FinResult(fins=fins, bodies=bodies, tines=all_tines, height=max(fin_heights),
                     thickness=thickness, tine_z=plan.tine_z, positions=[fin.t0 for fin in plan.fins],
                     foot_half_width=plan.half_foot, warnings=warnings, warning_targets=targets,
                     carried=support.Faces,
                     numbers=numbers, planned=len(plan.positions),
                     dropped=dropped, starts={n: plan.starts[n] for n in numbers}, along=frame.along,
                     out=frame.out, heights=dict(zip(numbers, fin_heights)), edges=dict(zip(numbers, edges)),
                     touching_z={fin.number: fin.touching for fin in plan.fins},
                     face_start=plan.face_start, radius=frame.radius, frame=frame, frames=frames,
                     moved=dict(plan.moved))


def joined(fins):
    """`fins` as they go to the slicer: solids that overlap, as the feet of three
    fins under a round side may, fused into one, the others as they are. Held
    apart in the document, so each fin can be picked and removed; left apart in a
    file, the overlap would print twice once a STEP file is split to objects.

    INPUTS this has to withstand:
      no solids overlap                     ->  `fins` itself, untouched
      solids touching without overlap       ->  `fins` itself, as fused they gain nothing
      all overlap in a row                  ->  one solid
      some overlap, others apart            ->  the overlapping ones one solid, the others kept
      fuse that fails or gives no solid     ->  `fins` itself: printed twice beats none
    """
    groups = []
    for solid in fins.Solids:
        touching = [group for group in groups
                    if any(solid.BoundBox.intersect(other.BoundBox) and solid.common(other).Volume > d.TOLERANCE
                           for other in group)]
        for group in touching:
            groups.remove(group)
        groups.append([solid] + [other for group in touching for other in group])
    if len(groups) == len(fins.Solids):
        return fins
    try:
        pieces = [group[0] if len(group) == 1 else group[0].multiFuse(group[1:]).removeSplitter() for group in groups]
    except Part.OCCError:
        return fins
    return Part.makeCompound(pieces) if all(piece.Solids for piece in pieces) else fins


def merged(part, *fin_shapes):
    """Part and fins as one body, for the connected mode."""
    result = part
    for shape in fin_shapes:
        result = result.fuse(shape)
    return result.removeSplitter()


def opposite_faces(part, face):
    """The faces of `part` that lean the other way, for a counter fin, the
    largest first: the side the part could tip towards. Whether a counter fin
    can be built under one is the caller's to try, on the face as it names
    it. The whole side of a cylinder or tube is passed over: its fin stays
    under its lowest line and moves only by turning the part, which the main
    fin does. A part of a side, the round end of a slot, counts: its fin stays
    where it stands.
    """
    out = frame_of(part, face).out
    leaning = []
    for number, candidate in enumerate(part.Faces):
        if orient.is_round_side(candidate):
            continue
        try:
            other = frame_of(part, candidate)
        except FinError:
            continue
        if other.out.dot(out) < -d.OPPOSITE_DIRECTION:
            leaning.append((candidate.Area, number))
    return [part.Faces[number] for _, number in sorted(leaning, reverse=True)]
