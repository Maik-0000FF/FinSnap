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
  fin beside the lowest line moved by
    hand                                ->  it stands there, up to ROUND_FIN_ANGLE_MAX
  fin height set above the contour of a
    fin beside the lowest line          ->  that fin ends at the top of its contour, the
                                            one under the lowest line keeps the height
"""

import math
from collections import namedtuple
from dataclasses import astuple, dataclass, field, replace
from functools import partial

import FreeCAD as App
import Part

from . import contour as contours
from . import defaults as d
from . import orient
from .face_frame import UP, FinError, Frame, HandEditError, beside_lowest, frame_of, in_plane, support_of
from .i18n import QT_TRANSLATE_NOOP, translate
from .shapes import bounds, keep, shape_key
from .tine_rows import (NARROW_AT_EVERY_TINE, TINE_CUTS_IN, TINE_MISSES, extent_at, face_tines, restarted_tines,
                        flank_bend, side_foot_start, side_tine, tine_end, tine_end_fault, tine_end_points, tine_start,
                        tines_on_face,
                        touching_at, wide_enough)

NOTE_TOO_CLOSE = QT_TRANSLATE_NOOP("FinSnap", "a fin comes within %.3f mm of the part, closer than the %.3f mm it "
                                              "keeps from the face")
# Said where fins beside the lowest line end below what passes beside them: their numbers.
NOTE_ENDED_LOWER = QT_TRANSLATE_NOOP("FinSnap", "fins %s end lower than the one under the lowest line: above, the part "
                                                "comes too close beside them")
# Fins beside the lowest line built whole (shapes.keep()), by what they depend on.
_kept_side_fins = {}
SIDE_FINS_KEPT = 32
# How often a fin beside the lowest line is moved out to keep the gap, measured
# on the part: each time by what was short, which a step or a cone leaves
# little of after the first.
FLANK_TRIES = 8
# How far the gap has to grow for each mm a fin moves out for that to be worth it.
FLANK_LEAST_GAIN = 0.02
# Where the side falls away steepest across such a fin, as the cosine: past it
# the fin has left the side, and more planes would follow nothing.
FLANK_STEEPEST = 0.2
# Twice the area of a triangle too small to be a face of a ruled solid (mm2).
SMALLEST_AREA = 1e-9
# Upright planes round a tine beside the lowest line of a round side at which
# its end is measured: how far apart (mm), and how far beyond its start towards
# the axis they go (mm), as it runs at the axis and so ends beside where it
# starts, the further the longer it is and the steeper a thin step rises.
TINE_END_STEP = 0.3
TINE_END_TRAVEL = 1.5
# Said where a fin beside the lowest line of a round side is moved past
# ROUND_FIN_ANGLE_MAX: its number and that angle.
NOTE_SIDE_FIN_TOO_FAR = QT_TRANSLATE_NOOP("FinSnap", "fin %d would stand further round the side than %.0f degrees "
                                                     "from its lowest line")
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
        return frame.contour.flank(z - frame.bed_z) + frame.flank_out
    return frame.s_flank(z, p.gap)


def flank_outline(p, frame, low, high):
    """The flank of a fin from height `high` down to `low` (absolute), as
    (s, z) points: its two ends under a face, every bend along a contour."""
    if frame.contour is not None:
        return [(s + frame.flank_out, z + frame.bed_z)
                for s, z in frame.contour.outline(low - frame.bed_z, high - frame.bed_z)]
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
    s_from = flank_at(p, frame, frame.bed_z + p.foot_height) + frame.foot_out
    return s_from, fin_out(p, frame, height) + p.foot_overhang


def foot(p, frame, t0, thickness, s_from, s_to, half_width):
    z = frame.bed_z
    height = p.foot_height
    if p.foot_shape == d.FOOT_RECTANGLE:
        t_mid = t0 + thickness / 2
        low, width = t_mid - half_width, 2 * half_width
        if frame.flank_curve:
            # Beside the lowest line the part lies further out towards that
            # line: the foot reaches away from it alone, plain, not along the part.
            middle = frame.flank_curve[0]
            low, width = (t0, half_width + thickness / 2) if t_mid > middle else (low, half_width + thickness / 2)
        return frame.section(low, [(s_from, z), (s_to, z), (s_to, z + height), (s_from, z + height)], width)

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


def _ruled(rings):
    """The solid between `rings`, polygons of as many points in upright planes
    one after the other, of plane faces: triangles from one ring to the next,
    so a surface that bends between them needs no curved face, which fusing
    fins and tines would take many times as long over.

    INPUTS this has to withstand:
      two rings, the same shape             ->  a prism
      rings that differ, their sides not
        flat                                ->  each side two triangles
      two points of a ring alike with the
        next                                ->  the triangle of no area left out
    """
    def face(points):
        return Part.Face(Part.makePolygon(points + points[:1]))

    faces = [face(rings[0]), face(rings[-1])]
    for one, other in zip(rings, rings[1:]):
        for k in range(len(one)):
            a, b, c, e = one[k], one[(k + 1) % len(one)], other[(k + 1) % len(one)], other[k]
            for triangle in ((a, b, c), (a, c, e)):
                if (triangle[1] - triangle[0]).cross(triangle[2] - triangle[0]).Length > SMALLEST_AREA:
                    faces.append(face(list(triangle)))
    return Part.makeSolid(Part.makeShell(faces)).removeSplitter()


def _following_blade(p, frame, t0, thickness, head, low, high, least=None):
    """The blade of a fin beside the lowest line: its outline in every upright
    plane across its thickness the same but for the flank, from height `high`
    down to `low`, which follows the radius of the side across it, so the gap
    stays the same over all of it. Every plane has the same corners, so a step or
    a cone cannot be cut through between two of them. `head` is the rest of the
    outline, the same in every plane. No flank comes further in than `least`, the
    start of the foot it stands on: below where it would, it goes straight down,
    so nothing hangs in the air over the foot.

    INPUTS this has to withstand:
      plain side                            ->  the gap the same across the fin, to
                                                within CONTOUR_SHARE
      thick fin, far round                  ->  as many planes as keep to that, more the
                                                more the side falls away
      fin as far round as the radius and
        past                                ->  the flank stays at the last place on it
      fin over the lowest line              ->  the curve its middle there
      foot further out than the flank       ->  straight down onto the foot, from where
                                                the flank passes its start
      cone, fillet or step above the side   ->  the same curve, of the side: the gap
                                                larger there, measured in _clear_of_part()
    """
    middle, _, radius = frame.flank_curve
    furthest = max(abs(t0 - middle), abs(t0 + thickness - middle))
    falling = max(FLANK_STEEPEST, math.sqrt(max(0.0, 1 - (furthest / radius) ** 2)))
    pieces = max(1, math.ceil(thickness / (falling * math.sqrt(8 * radius * d.CONTOUR_SHARE))))
    planes = [t0 + thickness * k / pieces for k in range(pieces + 1)]
    outline = flank_outline(p, frame, low, high)
    heights = {z for _, z in outline}
    if least is not None:
        # Where the flank of each plane passes the start of the foot: a corner
        # in every plane, as they have to have the same corners.
        for t in planes:
            by = flank_bend(frame, t)
            for (s_high, z_high), (s_low, z_low) in zip(outline, outline[1:]):
                if (s_high + by - least) * (s_low + by - least) < 0:
                    heights.add(z_low + (z_high - z_low) * (least - s_low - by) / (s_high - s_low))

    def flank_there(z):
        return next(s_low + (s_high - s_low) * (z - z_low) / (z_high - z_low)
                    for (s_high, z_high), (s_low, z_low) in zip(outline, outline[1:]) if z_low <= z <= z_high)

    ordered = sorted(heights, reverse=True)
    rings = []
    for t in planes:
        by = flank_bend(frame, t)
        flank = [(max(flank_there(z) + by, least) if least is not None else flank_there(z) + by, z) for z in ordered]
        rings.append([frame.point(t, s, z) for s, z in head + flank])
    return _ruled(rings)


def _tine_faults(p, surface, frame, fin, thickness, kept):
    """What is wrong with the end of each tine `kept` of `fin`, measured against
    the part itself, as (fault, height, tine)."""
    found = []
    for z, tine in zip([z for z, whole in zip(fin.candidate_z, fin.on_face) if whole], kept):
        fault = tine_end_fault(surface, tine_end_points(p, frame, fin.t0, thickness, z), p.clearance)
        if fault is not None:
            found.append((fault, z, tine))
    return found


def _side_fin(p, part, surface, frame, fin, thickness, half_foot):
    """A fin beside the lowest line built whole, for a build to keep: as it is the
    same as long as nothing it depends on changes, moving one of them or
    changing a height leaves the others untouched, and this takes most of a build."""
    body, tines, edge, frame, fin = _clear_of_part(p, part, frame, fin, thickness, half_foot)
    kept = [tine for tine, whole in zip(tines, fin.on_face) if whole]
    return (body, tines, edge, frame, fin, _tine_faults(p, surface, frame, fin, thickness, kept),
            body.multiFuse(kept).removeSplitter())


def _clear_of_part(p, part, frame, fin, thickness, half_foot):
    """One fin `fin` beside the lowest line as one_fin() builds it, the gap kept
    off the part as measured on it, what the curve of the side knows nothing of:
    where its foot comes closer, the foot alone starts further out, so the flank
    keeps to the side; where the blade does, it stands out by as much; where that
    does not help, as a cone or a thin step passing beside its wall, it ends
    below that place, at the last tine there. Returned with the frame and the fin
    as they came to be.

    INPUTS this has to withstand:
      plain side, the gap kept              ->  built once, as planned
      foot wider than the part leaves room  ->  the foot starts further out, the flank stays
      step or fillet in front of it         ->  moved out until it keeps the gap, as far
                                                as GAP_MAX from the side, past that lower
      a part passing beside its wall        ->  ends below, its tines above left out
      nothing of it clear of the part       ->  FinError, as check() says it
    """
    while True:
        moved_out = frame
        before = None
        foot_stuck = False
        for _ in range(FLANK_TRIES):
            built = one_fin(p, moved_out, fin.t0, fin.height, thickness, half_foot, fin.candidate_z)
            distance, points, _ = built[0].distToShape(part)
            short = p.gap - distance
            # As along a contour: the chords of the flank leave this much.
            if short <= d.CONTOUR_TOLERANCE:
                return (*built, moved_out, fin)
            at_foot = (not foot_stuck and p.foot_height > 0
                       and points[0][0].z - frame.bed_z <= p.foot_height + d.TOLERANCE)
            name = "foot_out" if at_foot else "flank_out"
            now = getattr(moved_out, name)
            # As far as the last move gained, the part may lie mostly beside the
            # fin, and little comes of moving out; nothing gained on the foot,
            # the blade moves; nothing gained on the blade, only lower helps.
            by = short / frame.n_out
            # Reaching into the part says nothing of how far is enough: on by as much.
            if distance <= d.TOLERANCE:
                before = None
            if before is not None and before[2] == name:
                gained = (distance - before[0]) / (now - before[1])
                if gained < FLANK_LEAST_GAIN:
                    if not at_foot:
                        break
                    foot_stuck = True
                    before = None
                    continue
                by = short / gained
            before = (distance, now, name)
            # Not past the gap tines still print straight across.
            if not at_foot and (now + by) * frame.n_out + p.gap > d.GAP_MAX:
                break
            moved_out = replace(moved_out, **{name: now + by})
        # Up to where it stays clear: the gap and a tine below that place.
        lowest_close = points[0][0].z - frame.bed_z - p.gap - p.tine_height
        kept = [(z, whole) for z, whole in zip(fin.candidate_z, fin.on_face) if z <= lowest_close and whole]
        if not kept or len(kept) == len(fin.candidate_z):
            raise FinError(translate("FinSnap", NOTE_TOO_CLOSE) % (distance, p.gap))
        fin = fin._replace(candidate_z=[z for z, _ in kept], on_face=[whole for _, whole in kept],
                           height=kept[-1][0] + p.tine_height)


def one_fin(p, frame, t0, height, thickness, half_foot, tine_z):
    """A fin without tines, its tines, which end on the face, and the middle
    of the upright outer edge of its blade, where the handles go."""
    zb, top = frame.bed_z, frame.bed_z + height
    s_out = fin_out(p, frame, height)

    if p.foot_shape == d.FOOT_NONE:
        head = [(s_out, zb), (s_out, top)]
        body = (_following_blade(p, frame, t0, thickness, head, zb, top) if frame.flank_curve
                else frame.section(t0, head + flank_outline(p, frame, zb, top), thickness))
    else:
        # Below the top of the foot the slanted flank would only add a thin tip
        # under the part; the blade ends vertically there and the foot carries it.
        s_from, s_to = foot_span(p, frame, height)
        foot_top = zb + p.foot_height
        if frame.flank_curve:
            s_from = side_foot_start(p, frame, t0, thickness)
        head = [(s_from, zb), (s_out, zb), (s_out, top)]
        body = (_following_blade(p, frame, t0, thickness, head, foot_top, top, s_from) if frame.flank_curve
                else frame.section(t0, head + flank_outline(p, frame, foot_top, top), thickness))
        body = body.fuse(foot(p, frame, t0, thickness, s_from, s_to, half_foot))
    outer_middle = frame.point(t0 + thickness / 2, s_out, zb + height / 2)

    tines = []
    t_tine = tine_start(p, t0, thickness)
    for z in tine_z:
        if frame.tine_edges is not None:
            low, high = side_tine(p, frame, t0, thickness, z)
            tines.append(_ruled([[frame.point(t, s, zb + z) for t, s in low],
                                 [frame.point(t, s, zb + z + p.tine_height) for t, s in high]]))
            continue
        bottom, tine_top, s_end_bottom, s_end_top = tine_end(p, frame, z)
        # The fin edge furthest out along the tine: the flank at its ends, or
        # the vertical inner end of the foot for a tine below the top of the
        # foot. Measured from there, a tine always reaches into the fin.
        edge = max(flank_at(p, frame, bottom), flank_at(p, frame, tine_top))
        if p.foot_height > 0 and bottom < zb + p.foot_height:
            edge = max(edge, foot_span(p, frame, height)[0])
        s_into_fin = edge + d.TINE_INTO_FIN
        tines.append(frame.section(t_tine, [(s_end_bottom, bottom), (s_into_fin, bottom),
                                            (s_into_fin, tine_top), (s_end_top, tine_top)], p.tine_width))
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
            raise FinError(translate("FinSnap", NOTE_TOO_CLOSE) % (distance, p.gap))


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


def side_numbers(round_fins):
    """The numbers of the fins beside the lowest line of a round side, from
    the left, for the choice `round_fins`: none of one fin."""
    return {d.ROUND_FINS_TWO: (1, 2), d.ROUND_FINS_THREE: (1, 3)}.get(round_fins, ())


def side_frames(part, frame, p, width, shifts):
    """By number, the frames of the two fins beside the fin under the lowest
    line of the whole round side of `frame`, or in its place; each at the place
    positions_for() gives it, moved by `shifts`, as thick as `width` at most.
    The gap and the clearance are measured in their upright planes, as much
    longer as the side falls away there (in_plane()).

    INPUTS this has to withstand:
      fin to the left, or the right         ->  its contour and tine edges at its own
                                                planes, nearest the lowest line first
      side with a step of another radius    ->  the gap of the side; _clear_of_part()
                                                moves the fin out where that is too little
      fin moved by hand                     ->  measured where it stands now
      fin moved over the lowest line        ->  its edge nearest that line stands on it
      fin moved past ROUND_FIN_ANGLE_MAX    ->  HandEditError, the number of fins known
      a plane that misses the part          ->  contour.ContourError, as for one fin
    """
    middle = (frame.along_min + frame.along_max) / 2
    pitch = beside_lowest(frame.radius, p.round_fin_angle)
    frames = {}
    furthest_round = beside_lowest(frame.radius, d.ROUND_FIN_ANGLE_MAX)
    numbers = side_numbers(p.round_fins)
    for number, sense in zip(numbers, (-1, 1)):
        centre = middle + sense * pitch + shifts.get(number, 0.0)
        if abs(centre - middle) > furthest_round + d.TOLERANCE:
            error = HandEditError(translate("FinSnap", NOTE_SIDE_FIN_TOO_FAR) % (number, d.ROUND_FIN_ANGLE_MAX))
            error.planned = len(positions_for(p, frame, thickness_for(p, frame.face_top_z - frame.bed_z)))
            raise error
        towards = 1.0 if centre > middle else -1.0
        nearest = middle if abs(centre - middle) < width / 2 else centre - towards * width / 2
        furthest = centre + towards * width / 2

        def measured_at(t):
            """`p` with gap and clearance as they come to in the plane at `t`."""
            away = t - middle
            return replace(p, gap=in_plane(frame.radius, away, p.gap),
                           tine_clearance=in_plane(frame.radius, away, p.tine_clearance))
        line = contours.beside(part, frame, measured_at(nearest), nearest, furthest)
        half = p.tine_width / 2 + TINE_END_STEP
        low = centre - half - (TINE_END_TRAVEL if centre > middle else 0.0)
        high = centre + half + (TINE_END_TRAVEL if centre < middle else 0.0)
        count = math.ceil((high - low) / TINE_END_STEP)
        planes = [low + (high - low) * k / count for k in range(count + 1)]
        ends = [contours.ends_at(part, frame, measured_at(t), t, line) for t in planes]
        edges = (planes, ends, [contours.across(part, frame, measured_at(centre), centre)])
        frames[number] = replace(frame, contour=line, tine_edges=edges,
                                 flank_curve=(middle, nearest, frame.radius + p.gap),
                                 face_top_z=frame.bed_z + line.top)
    return frames


def _within(p, room):
    """`p` with a fin height set by hand no higher than `room`."""
    return replace(p, fin_height=room) if p.fin_height > room else p


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
    if frame.round_side:
        # Only a fin beside the lowest line moves: the one under it stays there,
        # and the part turns instead (feature.set_round_shift()).
        shifts = {number: mm for number, mm in shifts.items() if number in frames}

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
    standing = [(starts[number], number) for number in sorted(starts) if number not in left_out]
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
            # Set higher than this fin reaches, it ends at the top of its own
            # contour; the fin under the lowest line keeps the height set.
            own_z = face_tines(_within(p, room), own_frame, count, False)[0]
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
        if frame.round_side and number not in frames:
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
            set_height = _within(p, room).fin_height if number in frames else p.fin_height
            fin_height = set_height if set_height > 0 else kept_z[-1] + p.tine_height
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
            frames = side_frames(part, frame, p, thickness_for(p, bounds(part).ZLength), shifts)
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
    # Fins beside the lowest line that end below what passes beside them.
    ended_lower = []
    built_fins = []
    for fin in plan.fins:
        own_frame = frames.get(fin.number, frame)
        faults, piece = None, None
        if fin.number in frames:
            planned_height = fin.height
            key = (shape_key(part), astuple(p), fin.number, fin.t0, fin.height, tuple(fin.candidate_z),
                   tuple(fin.on_face), thickness, plan.half_foot, own_frame.tine_edges[0][0])
            body, tines, edge, own_frame, fin, faults, piece = keep(
                _kept_side_fins, key, partial(_side_fin, p, part, surface, own_frame, fin, thickness, plan.half_foot),
                SIDE_FINS_KEPT)
            frames[fin.number] = own_frame
            if fin.height < planned_height - d.TOLERANCE:
                ended_lower.append(fin.number)
        else:
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
        built_fins.append(fin)
        edges.append(edge)
        bodies.append(body)
        all_tines.extend(kept)
        # Each tine kept, its end measured against the part itself.
        if faults is None:
            faults = _tine_faults(p, surface, own_frame, fin, thickness, kept)
        for fault, z, tine in faults:
            off_ends[fault].append((fin.number, z, tine))
        # One general fuse instead of one tine after the other: the lowest tine
        # sits on the top of the foot, where foot, flank and tine share an edge,
        # and fusing them pairwise fails on that edge.
        pieces.append(body.multiFuse(kept).removeSplitter() if piece is None else piece)

    fins = Part.makeCompound(pieces)
    # Fins beside the lowest line were measured as they were built.
    measured = [body for fin, body in zip(built_fins, bodies) if fin.number not in frames]
    check(p, part, fins, measured, 0.0 if frame.contour is None else d.CONTOUR_TOLERANCE)

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
    if ended_lower:
        warnings.append(translate("FinSnap", NOTE_ENDED_LOWER) % ", ".join(str(number) for number in ended_lower))
        targets.append(WarningTarget(ended_lower, [], False))
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

    numbers = [fin.number for fin in built_fins]
    fin_heights = [fin.height for fin in built_fins]
    return FinResult(fins=fins, bodies=bodies, tines=all_tines, height=max(fin_heights),
                     thickness=thickness, tine_z=plan.tine_z, positions=[fin.t0 for fin in plan.fins],
                     foot_half_width=plan.half_foot, warnings=warnings, warning_targets=targets,
                     carried=support.Faces,
                     numbers=numbers, planned=len(plan.positions),
                     dropped=dropped, starts={n: plan.starts[n] for n in numbers}, along=frame.along,
                     out=frame.out, heights=dict(zip(numbers, fin_heights)), edges=dict(zip(numbers, edges)),
                     touching_z={fin.number: [z for z in fin.touching if z in fin.candidate_z]
                                 if fin.number in frames else fin.touching for fin in built_fins},
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
