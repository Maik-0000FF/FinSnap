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
import time
from collections import namedtuple
from dataclasses import dataclass, field, fields, replace
from functools import partial

import FreeCAD as App
import Part

from . import contour as contours
from . import defaults as d
from . import orient
from .face_frame import UP, FinError, Frame, HandEditError, beside_lowest, frame_of, in_plane, support_of
from .i18n import QT_TRANSLATE_NOOP, translate
from .shapes import TooManyPairs, between_rings, bounds, enclosed_of, keep, meshed_of, shape_key, working
from .tine_rows import (NARROW_AT_EVERY_TINE, TINE_CUTS_IN, TINE_MISSES, extent_at, face_tines, fin_stretch, flank_bend,
                        forget_outline, restarted_tines, round_move, side_foot_start, side_tine, tine_end,
                        tine_end_fault, tine_end_points, tine_start, tines_on_face, touching_at, wide_enough)

NOTE_TOO_CLOSE = QT_TRANSLATE_NOOP("FinSnap", "a fin comes within %.3f mm of the part, closer than the %.3f mm it "
                                              "keeps from the face")
# Said where fins beside the lowest line end below what passes beside them: their numbers.
NOTE_ENDED_LOWER = QT_TRANSLATE_NOOP("FinSnap", "side fins %s end lower: above, the part comes too close beside them")
# Said where side fins end at the top of their contour, below the fin height set: their numbers.
NOTE_BELOW_SET_HEIGHT = QT_TRANSLATE_NOOP("FinSnap", "side fins %s end below the fin height set: the part does not "
                                                     "reach that high beside the lowest line")
# Said where a foot further out or the part itself leaves out tines of side fins: their numbers.
NOTE_TINES_AT_FOOT = QT_TRANSLATE_NOOP("FinSnap", "side fins %s: some tines left out, at a foot standing further out "
                                                  "to clear the part, or where they would reach into it")
# Said where side fins cannot stand clear of the part at all: their numbers.
NOTE_SIDE_FIN_LEFT_OUT = QT_TRANSLATE_NOOP("FinSnap", "side fins %s left out: the part leaves them no room there; "
                                                      "another angle may")
# Said where no fin beside the lowest line can stand and none stands under it.
NOTE_NO_SIDE_FIN = QT_TRANSLATE_NOOP("FinSnap", "no side fin finds room beside the part at this angle")
# What the shape of a single fin does not depend on, of the parameters.
NOT_SHAPING_A_FIN = ("placement", "fin_count", "end_inset", "face_length_per_fin", "brim_width",
                     "counter_tine_count", "round_fins", "round_fin_angle")
# A hair: how far apart at most points of a flank at the top of a fin are held (mm).
FLANK_TOP_HAIR = 1e-3
# Fins beside the lowest line built whole (shapes.keep()), by what they depend on.
_kept_side_fins = {}
SIDE_FINS_KEPT = 32
# Whether a fin, by its shape and that of the part, is clear of it (_not_known_clear()).
# Past this the oldest go first, and a run with more fins measures them all again.
_kept_clear = {}
CLEAR_KEPT = 1024
# What of a part stands out in front of the plane of a face (in_front_of()),
# by part and plane; and how far in front of that plane it is cut from (mm):
# a hair, so the face itself, lying in the plane, is not taken with it.
_kept_in_front = {}
IN_FRONT_KEPT = 32
IN_FRONT_SKIN = 1e-3
# The solids of what stands out in front of a face, each with what is known of
# it (_solids_in(), _Standing), by the shape in_front_of() keeps: of as many
# as keep() holds by itself, which is more than a search goes through and
# bounds what the meshes take in memory.
_kept_solids_in = {}
# The clock the kernel is timed by as it tells points inside a solid
# (_Standing._by_kernel()), in seconds; a test puts its own in its place.
_clock = time.perf_counter
# Where a fin is looked at for standing in what is in front of the face before it
# is built (_Places.surely_in_part()): the shares of its blade's height and of its
# width from the flank outward the points are taken at, by the flank, where a boss
# on the face stands, and at the top and the outer edge, where a fin under an
# overhang runs into it; and the share of the least distance allowed the points
# beside it lie off it, so each is nearer the fin than that distance for sure.
SURE_HEIGHT_SHARES = (0.99, 0.8, 0.5, 0.2)
SURE_OUT_SHARES = (0.02, 0.98, 0.5)
SURE_BESIDE_SHARE = 0.5
# How a foot and a blade beside the lowest line look for where they keep the gap,
# see _least_clear(): the first step out and how near it comes (mm).
FOOT_SEARCH_STEP = 0.5
FOOT_RESOLUTION = 0.05
FLANK_SEARCH_STEP = 0.1
FLANK_RESOLUTION = 0.01
# Where the side falls away steepest across such a fin, as the cosine: past it
# the fin has left the side, and more planes would follow nothing.
FLANK_STEEPEST = 0.2
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
NOTE_FACE_SHORT = QT_TRANSLATE_NOOP("FinSnap", "tines at %s mm above the bed left out: the face is narrower there "
                                               "than the %.2f mm a fin needs")
NOTE_MOVED = QT_TRANSLATE_NOOP("FinSnap", "fins moved along the face to where their tines hold better than at "
                                          "their planned place: %s")
NOTE_FIN_IN_PART = QT_TRANSLATE_NOOP("FinSnap", "fin %d would run into the part, which stands out of the face there; "
                                                 "move it along the face")
NOTE_CLEARED = QT_TRANSLATE_NOOP("FinSnap", "fins moved along the face clear of the part, which stands out of the "
                                            "face at their planned place: %s")
NOTE_BLOCKED = QT_TRANSLATE_NOOP("FinSnap", "fins at %s mm from the end of the face left out: the part stands out "
                                            "of the face there, and no place beside it is clear of it")
NOTE_ALL_BLOCKED = QT_TRANSLATE_NOOP("FinSnap", "the part stands out of the face under every fin, and no place "
                                                "along the face is clear of it")
NOTE_BLOCKED_OR_BARE = QT_TRANSLATE_NOOP("FinSnap", "no fin is left: the part stands out of the face under some, "
                                                    "and no tine of the others lies wholly on the face")


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
    # By number, how far a fin moved by itself from its planned place (mm, as
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
    if p.on_corner:
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
    if frame.flank_curve:
        # Not past the lowest line, where the part stands and the fin there has
        # its own foot; at least under the fin itself.
        half_width = max(thickness / 2, min(half_width, abs(t0 + thickness / 2 - frame.flank_curve[0])))
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


def nearest_place(span, inset, rests, t0, thickness, others):
    """Where along the face the fin planned to start at t0 starts nearest
    where `rests` accepts the place: one where its tines find the face, or find
    more of it; None if nowhere. It keeps within `span`, the frame whose
    stretch along the face is searched, `inset` from its ends as the fins
    planned there (positions_for()), and between its neighbours among the
    fins starting at `others`, clear of them, so the fins keep their order
    from the left; tried a fin thickness at a time, either way in turn.

    INPUTS this has to withstand:
      a hole under the middle of the fin     ->  the nearest start beside it, the
                                                 nearer side first
      a hole wider than the room between
        its neighbours                       ->  None: left out, as before
      a neighbour beside the hole            ->  not passed: the search ends clear
                                                 of it
      the end of `span` reached              ->  that way given up, the other tried on
      a place nearer the end of `span` than
        `inset`, such as on a chamfer        ->  not tried
    """
    clear = thickness + d.FOOT_CLEARANCE
    before = [other for other in others if other < t0 - d.TOLERANCE]
    after = [other for other in others if other > t0 + d.TOLERANCE]
    low = max([span.along_min + inset] + [other + clear for other in before])
    high = min([span.along_max - inset - thickness] + [other - clear for other in after])
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

    faces = [face(rings[0]), face(rings[-1])] + [face(list(triangle)) for triangle in between_rings(rings)]
    return Part.makeSolid(Part.makeShell(faces)).removeSplitter()


def _cut_at_height(points, high, low):
    """The `points` (s, z) of a flank, from its top down to `low`, cut off at the
    height `high` where the flank passes it. Those above stay as points, as every
    plane of a blade has the same corners: held at the cut, falling from the
    height to the next point left, at most a hair apart, so no two coincide and
    the outline never folds back.

    INPUTS this has to withstand:
      nothing above the height, or the top
        exactly on it                       ->  as they are
      one point above                       ->  it moves onto the height, on the flank
      several above                         ->  held at the cut, falling
      the next point a hair under the
        height, or on it                    ->  held as well, the rest still falling
      a point turned above one before it,
        past the height                     ->  all down to it held, the fin no higher
      all of them above                     ->  all held at the last place, falling
                                                towards `low`
    """
    crossing = 1 + max((k for k, (_, z) in enumerate(points) if z > high), default=-1)
    if not crossing:
        return points
    if crossing == len(points):
        cut = points[-1][0]
    else:
        (s_above, z_above), (s_below, z_below) = points[crossing - 1], points[crossing]
        cut = s_below + (s_above - s_below) * (high - z_below) / (z_above - z_below)
    held = next((k for k in range(crossing, len(points)) if points[k][1] < high - FLANK_TOP_HAIR), len(points))
    floor = points[held][1] if held < len(points) else low
    hair = min(FLANK_TOP_HAIR, (high - floor) / (held + 1))
    return [(cut, high - (k + 1) * hair) for k in range(held)] + points[held:]


def _blade_rings(p, frame, t0, thickness, head, low, high, least=None):
    """The rings of the blade of a fin beside the lowest line, for _ruled(): its outline in every upright
    plane across its thickness the same but for the flank, from height `high`
    down to `low`, which follows the radius of the side across it, so the gap
    stays the same over all of it: each point of it turned about the axis at its
    own radius (round_move()). Every plane has the same corners, so a step or a
    cone cannot be cut through between two of them. `head` is the rest of the
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
      a point turned up past the height of
        the fin                             ->  the flank cut off at that height, where
                                                it runs: the fin is as high as it says,
                                                also where the flank rounds an end of the part
      fin over the lowest line              ->  the curve its middle there
      foot further out than the flank       ->  straight down onto the foot, from where
                                                the flank passes its start
      cone, fillet or step above the side   ->  turned as it is about the axis, at its
                                                own radius; measured in _clear_of_part()
    """
    middle, nearest, radius = frame.flank_curve
    furthest = max(abs(t0 - middle), abs(t0 + thickness - middle))
    outline = flank_outline(p, frame, low, high)
    # The chords across it are as long as the thinnest part it goes over allows.
    axis = frame.c - frame.radius
    radii = [math.hypot(s * frame.n_out + z * frame.n_z - axis, nearest - middle) for s, z in outline]
    tightest = max(furthest, min([radius] + radii))
    falling = max(FLANK_STEEPEST, math.sqrt(max(0.0, 1 - (furthest / tightest) ** 2)))
    pieces = max(1, math.ceil(thickness / (falling * math.sqrt(8 * tightest * d.CONTOUR_SHARE))))
    planes = [t0 + thickness * k / pieces for k in range(pieces + 1)]
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
    def turned_flank(t):
        """The flank in the plane at `t`, from its top down: each point turned,
        cut off at the height of the fin, no further in than the foot."""
        points = []
        for s, z in ((flank_there(z), z) for z in ordered):
            by = round_move(frame, s, z, t)
            points.append((s + by * frame.n_out, z + by * frame.n_z))
        return [(s if least is None else max(s, least), z) for s, z in _cut_at_height(points, high, low)]

    return [[frame.point(t, s, z) for s, z in head + turned_flank(t)] for t in planes]


def _blade_ends(p, frame, t0, height, thickness):
    """What the blade of a fin `height` high has but its flank: the rest of its
    outline, the height the flank comes down to and where the foot starts, None
    without one. Below the top of the foot the slanted flank would only add a thin
    tip under the part; the blade ends upright there and the foot carries it."""
    zb, top = frame.bed_z, frame.bed_z + height
    s_out = fin_out(p, frame, height)
    if p.foot_shape == d.FOOT_NONE:
        return [(s_out, zb), (s_out, top)], zb, None
    s_from = side_foot_start(p, frame, t0, thickness) if frame.flank_curve else foot_span(p, frame, height)[0]
    return [(s_from, zb), (s_out, zb), (s_out, top)], zb + p.foot_height, s_from


def _side_blade_rings(p, frame, t0, height, thickness):
    """The rings of the blade of a fin `height` high beside the lowest line."""
    head, low, s_from = _blade_ends(p, frame, t0, height, thickness)
    return _blade_rings(p, frame, t0, thickness, head, low, frame.bed_z + height, s_from)


def _tine_faults(p, surface, frame, fin, thickness, kept):
    """What is wrong with the end of each tine `kept` of `fin`, measured against
    the part itself, as (fault, height, tine)."""
    found = []
    for z, tine in zip([z for z, whole in zip(fin.candidate_z, fin.on_face) if whole], kept):
        fault = tine_end_fault(surface, tine_end_points(p, frame, fin.t0, thickness, z), p.clearance)
        if fault is not None:
            found.append((fault, z, tine))
    return found


def _shaping(p):
    """What of `p` the shape of a single fin depends on, as a key: not how many
    fins there are or where, nor what the slicer does round them."""
    return tuple(getattr(p, f.name) for f in fields(p) if f.name not in NOT_SHAPING_A_FIN)


def _side_fin(p, part, surface, frame, fin, thickness, half_foot):
    """A fin beside the lowest line built whole, for a build to keep: as it is the
    same as long as nothing it depends on changes, moving one of them or
    changing a height leaves the others untouched, and this takes most of a build.
    None where it cannot stand clear of the part: it is left out, and the others
    are built all the same, with a note.

    INPUTS this has to withstand:
      a fin that stands clear               ->  it, as a build takes it
      a fin nothing of which stands clear   ->  None, not a refusal of all the fins
      a tine reaching into the part         ->  that tine left out; the fin without it
      every tine reaching into the part     ->  None
    """
    try:
        body, tines, edge, frame, fin = _clear_of_part(p, part, frame, fin, thickness, half_foot)
    except FinError:
        return None
    kept = [tine for tine, whole in zip(tines, fin.on_face) if whole]
    faults = _tine_faults(p, surface, frame, fin, thickness, kept)
    # One reaching into the part, as over a large fillet the contour rounds off
    # by the width of the tine, is left out: the others hold the fin.
    cut_in = {z for fault, z, _ in faults if fault == TINE_CUTS_IN}
    if cut_in:
        on_face = [whole and z not in cut_in for z, whole in zip(fin.candidate_z, fin.on_face)]
        if not any(on_face):
            return None
        fin = fin._replace(on_face=on_face, touching=[z for z in fin.touching if z not in cut_in])
        faults = [found for found in faults if found[0] != TINE_CUTS_IN]
        kept = [tine for tine, whole in zip(tines, on_face) if whole]
    return body, tines, edge, frame, fin, faults, body.multiFuse(kept).removeSplitter()


def _on_flank(p, frame, fin, thickness):
    """`fin` without the tines where its foot, moved out, keeps the blade further
    off than its flank: straight down from the flank, they would stand long in
    the air, and so hold it no better than those above.

    INPUTS this has to withstand:
      foot not moved out, or little         ->  `fin` as it is
      tines below where the flank passes
        the start of the foot               ->  left out, as over a recess
    """
    if p.foot_height <= 0 or not frame.foot_out:
        return fin
    start = side_foot_start(p, frame, fin.t0, thickness)
    t_fin = fin.t0 + thickness / 2

    def on_flank(z):
        middle_z = frame.bed_z + z + p.tine_height / 2
        s = flank_at(p, frame, middle_z)
        return s + round_move(frame, s, middle_z, t_fin) / frame.n_out >= start - d.TOLERANCE

    on_face = [whole and on_flank(z) for z, whole in zip(fin.candidate_z, fin.on_face)]
    return fin._replace(on_face=on_face, touching=[z for z in fin.touching if on_flank(z)])


def _halved(clear, inside, outside, resolution):
    """Between `inside`, where `clear` does not hold, and `outside`, where it does,
    the first value at which it holds, within `resolution` give or take TOLERANCE,
    so a rounding in the last step does not cost another fin."""
    while outside - inside > resolution + d.TOLERANCE:
        between_them = (inside + outside) / 2
        if clear(between_them):
            outside = between_them
        else:
            inside = between_them
    return outside


def _least_clear(clear, step, most, resolution):
    """The smallest value from 0 up to `most` at which `clear(value)` holds, within
    `resolution` give or take TOLERANCE (_halved()): outward by doubling `step` until it holds, then halved back
    between the last value that does not and the first that does, so it never
    stays further out than it has to. None where it holds nowhere up to `most`.

    INPUTS this has to withstand:
      clear at 0                            ->  0, asked once
      clear from 1.7 on                     ->  within that above 1.7
      clear from just below `most`          ->  found, `most` itself tried
      never clear                           ->  None
      `most` 0 or less, not clear at 0      ->  None
    """
    if clear(0.0):
        return 0.0
    if most <= 0:
        return None
    inside, outside = 0.0, min(step, most)
    while not clear(outside):
        if outside >= most:
            return None
        inside, outside = outside, min(2 * outside, most)
    return _halved(clear, inside, outside, resolution)


def _settled_clear(clear, guess, most, resolution):
    """What _least_clear() finds, asked from a `guess` near it: `resolution` to
    either side of the guess, doubled until `clear` changes, then halved back, to
    within `resolution` give or take TOLERANCE (_halved()).
    None where it holds nowhere up to `most`.

    INPUTS this has to withstand:
      guess right                           ->  within that, asked twice
      guess a little off, either way        ->  the same, a few more times
      clear at 0, guess above it            ->  0, whatever the guess
      never clear                           ->  None, `most` itself tried
      guess past `most`                     ->  taken as `most`
      `most` 0 or less, not clear at 0      ->  None
    """
    guess = max(0.0, min(guess, most))
    width = resolution
    if clear(guess):
        outside = guess
        while True:
            if outside <= 0:
                return 0.0
            inside = max(0.0, outside - width)
            if not clear(inside):
                break
            outside, width = inside, 2 * width
    else:
        inside = guess
        while True:
            if inside >= most:
                return None
            outside = min(most, inside + width)
            if clear(outside):
                break
            inside, width = outside, 2 * width
    return _halved(clear, inside, outside, resolution)


def _foot_out_for(p, part, frame, fin, thickness, half_foot):
    """How far out the foot of `fin` has to start to keep the gap off the part,
    measured on the foot alone; None where no place on its length does."""
    if p.foot_height <= 0:
        return 0.0
    s_to = foot_span(p, frame, fin.height)[1]

    def clear(out):
        moved = replace(frame, foot_out=out)
        s_from = side_foot_start(p, moved, fin.t0, thickness)
        shape = foot(p, moved, fin.t0, thickness, s_from, s_to, half_foot)
        return shape.distToShape(part)[0] >= p.gap - d.CONTOUR_TOLERANCE

    return _least_clear(clear, FOOT_SEARCH_STEP, (s_to - side_foot_start(p, frame, fin.t0, thickness)) / 2,
                        FOOT_RESOLUTION)


def _clear_of_part(p, part, frame, fin, thickness, half_foot):
    """One fin `fin` beside the lowest line as one_fin() builds it, the gap kept off
    the part as measured on it, what the curve of the side knows nothing of. As
    little as it takes, in this order: its foot starts further out; if the blade
    is still too close, it stands further out, as far as GAP_MAX from the side;
    if that does not do, it ends lower, below where it comes too close. Returned
    with the frame and the fin as they came to be.

    INPUTS this has to withstand:
      plain side, the gap kept              ->  built as planned, nothing moved
      foot wider than the part leaves room  ->  the foot as little further out as keeps
                                                the gap, within FOOT_RESOLUTION; the flank stays
      foot well inside the part             ->  the same
      step or fillet in front of the blade  ->  the blade as little further out as keeps
                                                the gap, within FLANK_RESOLUTION
      a part passing beside its wall, moving
        out does not help                   ->  ends below, its tines above left out
      the same above all its tines          ->  ends at its last tine
      the same at its last tine             ->  ends at the tine below it
      no tine left                          ->  FinError, as check() says it
    """
    furthest = (d.GAP_MAX - p.gap) / frame.n_out
    needed = p.gap - d.CONTOUR_TOLERANCE
    while True:
        def placed(out):
            """The frame with the blade `out` further out and its foot where that
            lets it stand, None where it finds no place."""
            moved = replace(frame, flank_out=out)
            foot_out = _foot_out_for(p, part, moved, fin, thickness, half_foot)
            return None if foot_out is None else replace(moved, foot_out=foot_out)

        def stays_clear(moved):
            return one_fin(p, moved, fin.t0, fin.height, thickness, half_foot, [])[0].distToShape(part)[0] >= needed

        def blade_clear(out):
            moved = placed(out)
            return moved is not None and stays_clear(moved)

        def looks_clear(out):
            """What the mesh says of blade_clear(), in a fraction of its time. For
            a guess the foot stays as it stands with nothing moved: looking for its
            place at every step is what a mesh is there to save."""
            rings = _side_blade_rings(p, replace(standing or frame, flank_out=out), fin.t0, fin.height, thickness)
            return mesh.distance(rings, p.gap) > needed

        def clear_past_0(out):
            """blade_clear() where 0 has said no already."""
            return out > 0 and blade_clear(out)

        # Most fins keep the gap as they stand, and need no mesh to say so.
        standing = placed(0.0)
        if standing is not None and stays_clear(standing):
            out = 0.0
        else:
            try:
                mesh = meshed_of(part)
                guess = _least_clear(looks_clear, FLANK_SEARCH_STEP, furthest, FLANK_RESOLUTION)
            except (TooManyPairs, MemoryError):
                guess = None
            # A mesh that sees no place, or one at 0 where the fin itself just said
            # no, gives nothing to start from: measured all the way.
            out = (_settled_clear(blade_clear, guess, furthest, FLANK_RESOLUTION) if guess
                   else _least_clear(clear_past_0, FLANK_SEARCH_STEP, furthest, FLANK_RESOLUTION))
        if out is not None:
            moved = standing if out == 0.0 else placed(out)
            return (*one_fin(p, moved, fin.t0, fin.height, thickness, half_foot, fin.candidate_z),
                    moved, _on_flank(p, moved, fin, thickness))
        # Where it stays clear with nothing moved but the foot: the gap and a tine
        # below where it is closest, and a tine less if it ends at that one already.
        moved = standing or frame
        distance, points, _ = one_fin(p, moved, fin.t0, fin.height, thickness, half_foot, [])[0].distToShape(part)
        lowest_close = points[0][0].z - frame.bed_z - p.gap - p.tine_height
        kept = [(z, whole) for z, whole in zip(fin.candidate_z, fin.on_face) if z <= lowest_close and whole]
        if kept and kept[-1][0] + p.tine_height >= fin.height - d.TOLERANCE:
            kept = kept[:-1]
        if not kept:
            raise FinError(translate("FinSnap", NOTE_TOO_CLOSE) % (distance, p.gap))
        fin = fin._replace(candidate_z=[z for z, _ in kept], on_face=[whole for _, whole in kept],
                           height=kept[-1][0] + p.tine_height)


def one_fin(p, frame, t0, height, thickness, half_foot, tine_z):
    """A fin without tines, its tines, which end on the face, and the middle
    of the upright outer edge of its blade, where the handles go."""
    zb, top = frame.bed_z, frame.bed_z + height
    s_out = fin_out(p, frame, height)
    head, low, s_from = _blade_ends(p, frame, t0, height, thickness)
    body = (_ruled(_blade_rings(p, frame, t0, thickness, head, low, top, s_from)) if frame.flank_curve
            else frame.section(t0, head + flank_outline(p, frame, low, top), thickness))
    if s_from is not None:
        body = body.fuse(foot(p, frame, t0, thickness, s_from, foot_span(p, frame, height)[1], half_foot))
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


def overlap_of(fins, part):
    """How much of `fins` lies in `part` (mm3). Measured off first: what stands
    clear of the part cannot lie in it, and the kernel, cutting a fin of many plane
    faces, has been seen to give the whole part for it. More than the fins hold
    is no answer either.

    INPUTS this has to withstand:
      fins clear of the part                ->  0, not asked of the kernel
      fins touching it, none inside         ->  0
      fins reaching into it                 ->  the volume inside
      an answer larger than the fins        ->  0: says nothing of them
    """
    if fins.distToShape(part)[0] > d.TOLERANCE:
        return 0.0
    found = fins.common(part).Volume
    return 0.0 if found > fins.Volume else found


def _not_known_clear(pieces, part):
    """Those of `pieces` that are not clear of `part`, each measured once for its
    shape: a fin moved leaves the others as they are, and measuring them all with
    every move takes longer than anything else about it.

    INPUTS this has to withstand:
      pieces clear of the part              ->  none
      a piece touching or in it             ->  that piece
      a piece asked again, the same shape   ->  not measured again
      a piece mirrored onto the corners of
        one known clear                     ->  measured: shape_key() tells them apart
      the same shape, another part          ->  measured
    """
    # Its hash: a part of many corners would be held in full by every entry.
    part_key = hash(shape_key(part))

    def clear(piece):
        return keep(_kept_clear, (part_key, shape_key(piece)),
                    lambda: piece.distToShape(part)[0] > d.TOLERANCE, CLEAR_KEPT)

    return [piece for piece in pieces if not clear(piece)]


def check(p, part, pieces, bodies, slack=0.0):
    """Fins, of `pieces`, clear of the part, no closer than their distance from the
    face, give or take `slack`: along a contour, CONTOUR_TOLERANCE. That every tine
    reaches the face is settled when the tines are chosen, by contact_share()."""
    if p.connection == d.CONNECTION_SEPARATE:
        unsure = _not_known_clear(pieces, part)
        overlap = overlap_of(Part.makeCompound(unsure), part) if unsure else 0.0
        if overlap > d.TOLERANCE:
            raise FinError(translate("FinSnap", "the fins overlap the part by %.4f mm³") % overlap)

    for body in bodies:
        distance = body.distToShape(part)[0]
        if distance < p.gap - slack - d.TOLERANCE:
            raise FinError(translate("FinSnap", NOTE_TOO_CLOSE) % (distance, p.gap))


@working()
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
    try:
        return _build_reaching(part, face, p, tine_count, left_out, shifts or {}, heights or {})
    finally:
        forget_outline()


def _build_reaching(part, face, p, tine_count, left_out, shifts, heights):
    """build(), with the fins reaching over a groove where they can."""
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
                                  "starts half_foot fins moved fins_left_out cleared blocked short_heights room_needed")


def side_numbers(round_fins):
    """The numbers of the fins beside the lowest line of a round side, from
    the left, for the choice `round_fins`: none of one fin."""
    return {d.ROUND_FINS_TWO: (1, 2), d.ROUND_FINS_THREE: (1, 3)}.get(round_fins, ())


def side_frames(part, frame, p, width, shifts):
    """By number, the frames of the two fins beside the fin under the lowest
    line of the whole round side of `frame`, or in its place; each at the place
    positions_for() gives it, moved by `shifts`, as thick as `width` at most, and
    the numbers of those that cannot stand there.
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
      a plane that misses the part          ->  that fin named as missing, the others built
    """
    middle = (frame.along_min + frame.along_max) / 2
    pitch = beside_lowest(frame.radius, p.round_fin_angle)
    frames, missing = {}, []
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
        half = p.tine_width / 2 + TINE_END_STEP
        low = centre - half - (TINE_END_TRAVEL if centre > middle else 0.0)
        high = centre + half + (TINE_END_TRAVEL if centre < middle else 0.0)
        count = math.ceil((high - low) / TINE_END_STEP)
        planes = [low + (high - low) * k / count for k in range(count + 1)]
        try:
            line = contours.beside(part, frame, measured_at(nearest), nearest, furthest)
            ends = [contours.ends_at(part, frame, measured_at(t), t, line) for t in planes]
            edges = (planes, ends, [contours.across(part, frame, measured_at(centre), centre)])
        except contours.ContourError:
            missing.append(number)
            continue
        frames[number] = replace(frame, contour=line, tine_edges=edges,
                                 flank_curve=(middle, nearest, frame.radius + p.gap),
                                 face_top_z=frame.bed_z + line.top)
    return frames, missing


def _within(p, room):
    """`p` with a fin height set by hand no higher than `room`."""
    return replace(p, fin_height=room) if p.fin_height > room else p


def _inside(solid, point):
    """Whether `point` lies inside `solid`, not on its surface; False where the
    kernel cannot tell."""
    try:
        return solid.isInside(point, d.TOLERANCE, False)
    except Part.OCCError:
        return False


class _Standing:
    """A solid of what stands out in front of a face, and how it is told which
    points lie inside it. At first the kernel is asked, and timed. Once it has
    taken ENCLOSED_WORTH for this solid altogether, about what a mesh costs, it
    is settled for good: where the kernel took ENCLOSED_KERNEL_SLOW a point or
    longer by then, the solid gets a mesh (enclosed_of()) that tells most
    points from then on; else, or where it can have none, it stays with the
    kernel. Settled once, as an average looked at again with every point could
    tip, and a mesh refused would be made again.

    Only the calls of the kernel are timed, not what picks the points. What
    is said of a point is what the kernel says, whichever way it is told.

    INPUTS this has to withstand (any_inside()):
      no points, or none in the box         ->  False, nothing asked, no time counted
      asking still, the kernel quick or slow,
        less than ENCLOSED_WORTH taken      ->  the kernel asked of each point, timed
      ENCLOSED_WORTH reached, the kernel as
        slow as ENCLOSED_KERNEL_SLOW a point ->  a mesh made, used from the next points on
      ENCLOSED_WORTH reached, the kernel
        quicker than that, as on a dome     ->  no mesh, now or later, however slow
                                                the kernel turns after
      a mesh due, the solid too large for
        one                                 ->  tried that once, no mesh, not tried again
      with a mesh: a point it tells of      ->  its answer, the kernel not asked
      with a mesh: a point it does not tell
        of                                  ->  the kernel asked, no longer timed
      the kernel cannot tell of a point     ->  False for it (_inside()), its time counted
      a point found inside                  ->  True, no further point asked
    """

    def __init__(self, solid):
        self.solid, self.box = solid, solid.BoundBox
        self.mesh, self.settled = None, False
        # What the kernel took for this solid while it was asking still (s), and of how many points.
        self.spent, self.asked = 0.0, 0

    def any_inside(self, points):
        """Whether one of `points` lies inside the solid, not on its surface."""
        near = [point for point in points if self.box.isInside(point)]
        told = [None] * len(near) if self.mesh is None else self.mesh.told(near)
        return any(found for found in told) or any(
            self._by_kernel(point) for point, found in zip(near, told) if found is None)

    def _by_kernel(self, point):
        """Whether `point` lies inside, by the kernel; timed until it is settled how the solid is told."""
        if self.settled:
            return _inside(self.solid, point)
        start = _clock()
        found = _inside(self.solid, point)
        self.spent += _clock() - start
        self.asked += 1
        if self.spent >= d.ENCLOSED_WORTH:
            self.settled = True
            if self.spent >= d.ENCLOSED_KERNEL_SLOW * self.asked:
                self.mesh = enclosed_of(self.solid)
        return found


def _solids_in(front):
    """The solids of `front`, each as a _Standing. Made once for a shape and
    kept with it, so that no other takes its place in memory."""
    return keep(_kept_solids_in, id(front), lambda: (front, [_Standing(solid) for solid in front.Solids]))[1]


def _any_inside(front, points):
    """Whether one of `points` lies inside a solid of `front`, not on its
    surface, each solid asked by itself (_Standing.any_inside()), none once a
    point is found inside one."""
    return any(standing.any_inside(points) for standing in _solids_in(front))


def in_front_of(part, frame):
    """What of `part` stands out in front of the plane of the planar face of
    `frame`, IN_FRONT_SKIN off it, as a boss does; None for nothing. Cut once
    per part and plane, kept for every plan and build after.

    INPUTS this has to withstand:
      a plain face                          ->  None: the face lies in the plane
      a boss on the face                    ->  the boss
      a chamfer or a corner round the face  ->  None: it lies behind the plane
      the part reaching out in front of the
        plane above the face or beside it   ->  that part of it
    """
    def cut():
        box = bounds(part)
        reach = box.DiagonalLength
        low, high = box.ZMin, box.ZMax
        ring = [(frame.s_flank(low, IN_FRONT_SKIN), low), (frame.s_flank(high, IN_FRONT_SKIN), high),
                (frame.s_flank(high, IN_FRONT_SKIN) + reach, high), (frame.s_flank(low, IN_FRONT_SKIN) + reach, low)]
        middle = frame.along.dot(box.Center)
        front = part.common(frame.section(middle - reach, ring, 2 * reach))
        return front if front.Volume > d.TOLERANCE else None
    key = (shape_key(part), tuple(frame.out), tuple(frame.along), frame.n_out, frame.n_z, frame.c)
    return keep(_kept_in_front, key, cut, IN_FRONT_KEPT)


class _Places:
    """A fin of one plan measured at a place along the face: the heights of
    its tines and which of them lie on the face. Kept for the plan, as a
    search asks for a place more than once and the contact of a tine takes a
    cut through the part.

    `stretch` is the frame of the face narrowed to the stretch the fins are
    planned on, `whole_face` the face as a whole, on which a fin moved past
    that stretch is measured and a place of its own is searched for
    (_better_place(), _resting_place()). The tines and their contact are
    measured on `stretch` wherever the fin stands, as neither reads the ends
    of the frame; only the width is measured on `whole_face` (wide_enough()).
    `tine_z` is the one grid of the face and `face_narrow` its heights the
    face as a whole cannot take. With `restart`, each fin is measured on its
    own tine grid (restarted_tines()). `slices` is the dict of extent_at()
    kept for the build."""

    def __init__(self, *, p, part, support, stretch, whole_face, thickness, half_foot, tine_z, face_narrow, restart,
                 count, slices):
        self.p, self.part, self.support, self.stretch, self.whole_face = p, part, support, stretch, whole_face
        self.thickness, self.half_foot, self.tine_z, self.face_narrow = thickness, half_foot, tine_z, face_narrow
        self.restart, self.count, self.slices = restart, count, slices
        self._tines, self._contact, self._clear, self._surely_in = {}, {}, {}, {}
        # What front() found, once it was asked.
        self._front = []

    def front(self):
        """What of the part stands out in front of the face (in_front_of()), None
        for nothing, asked once for all the places: asking again works out the
        key of the part each time, which takes as long as telling a place."""
        if not self._front:
            self._front.append(in_front_of(self.part, self.whole_face))
        return self._front[0]

    def reach(self, t, own):
        """How high the fin starting at t reaches above the bed: a height of
        its own, else the fin height set, else the top of its highest tine."""
        if own is not None:
            return own
        if self.p.fin_height > 0:
            return self.p.fin_height
        candidate_z = self.tines(t, own)[1]
        return max(candidate_z) + self.p.tine_height if candidate_z else 0.0

    def clear_at(self, t, own, half_foot=None):
        """Whether the fin starting at t, without its tines, as one_fin()
        builds it up to its reach(), keeps its gap from what of the part
        stands out in front of the face (in_front_of()), such as a boss, as
        check() measures the fins as built. Behind the plane of the face the
        part keeps the gap by itself: the flank stands that far in front of
        it. check() still measures the fins as built, their tines with them.

        `half_foot` is the half width of its foot, the plan's for None.

        INPUTS this has to withstand:
          plain face, nothing in front of it   ->  True, no fin built for it
          a boss under the blade               ->  False
          a boss over the foot, low down       ->  False
          a boss beside the fin or its foot,
            within the gap of it               ->  False
          a boss beside, further off           ->  True
          a boss above the top of the fin      ->  True
          a chamfer below the face, where the
            face starts above the bed          ->  True: behind the plane
          a fin reaching nowhere, no tine      ->  True: nothing stands there
        """
        height = self.reach(t, own)
        half_foot = self.half_foot if half_foot is None else half_foot
        key = (t, height, half_foot)
        if key not in self._clear:
            front = self.front()
            self._clear[key] = front is None or height <= d.TOLERANCE or not self.surely_in_part(
                t, own, half_foot) and self._body(t, height, half_foot).distToShape(
                front)[0] >= self.p.gap - d.TOLERANCE
        return self._clear[key]

    def surely_in_part(self, t, own, half_foot=None):
        """Whether the fin starting at t stands in what of the part stands out in
        front of the face, or nearer it than clear_at() allows, told without
        building it: a point of the fin, or one beside it nearer than the least
        distance allowed, lies inside. Only yes is an answer: no leaves it to
        clear_at(), which measures the fin built. Asked before holds() where a
        place is searched, as that cuts through the part for every tine.

        INPUTS this has to withstand:
          nothing in front of the face          ->  False, no point asked
          a point of the fin inside what stands
            out                                 ->  True: no fin built, no tine measured
          the part beside the fin, a point
            beside it inside                    ->  True: nearer than the gap
          the part beside the fin, further off
            than those points                   ->  False: measured as before
          a point on the surface of what stands
            out                                 ->  False: not sure
          a fin without a height                ->  False
          what stands out in several solids     ->  each asked by itself
          a point the mesh of what stands out
            tells of, where it has one
            (_Standing)                         ->  not asked of the kernel
          the kernel cannot tell where a point
            lies                                ->  False for that solid
          a fin with a foot, without one, with a
            height of its own                   ->  every point inside the fin as built,
                                                    or the given share of the gap off it
          a frame along a contour or beside the
            lowest line of a round side         ->  False, by decision: its blade has
                                                    another shape, and it is measured
        """
        height = self.reach(t, own)
        half_foot = self.half_foot if half_foot is None else half_foot
        key = (t, height, half_foot)
        if key not in self._surely_in:
            front = self.front()
            self._surely_in[key] = front is not None and _any_inside(front, self.sure_points(t, height, half_foot))
        return self._surely_in[key]

    def sure_points(self, t, height, half_foot):
        """Points the fin starting at t, `height` high, holds or comes nearer than
        the least distance clear_at() allows: in its blade at SURE_HEIGHT_SHARES
        of its height above the foot and SURE_OUT_SHARES of its width there, and
        in the middle of its foot, each in the middle of its thickness and
        beside it on either side."""
        p, frame = self.p, self.stretch
        beside = (p.gap - d.TOLERANCE) * SURE_BESIDE_SHARE
        if height <= d.TOLERANCE or beside <= 0 or frame.contour is not None or frame.flank_curve:
            return []
        middle = t + self.thickness / 2
        _, low, s_from = _blade_ends(p, frame, t, height, self.thickness)
        top, s_out = frame.bed_z + height, fin_out(p, frame, height)
        # (s, z, how far to either side of the middle the fin reaches there)
        held = []
        if top - low > d.TOLERANCE:
            for z in (low + (top - low) * share for share in SURE_HEIGHT_SHARES):
                flank = flank_at(p, frame, z)
                held += [(flank + (s_out - flank) * share, z, self.thickness / 2) for share in SURE_OUT_SHARES]
        if s_from is not None and p.foot_height > d.TOLERANCE:
            s_to = foot_span(p, frame, height)[1]
            held.append(((s_from + s_to) / 2, frame.bed_z + p.foot_height / 2, max(half_foot, self.thickness / 2)))
        return [frame.point(at, s, z) for s, z, half in held
                for at in (middle, middle - half - beside, middle + half + beside)]

    def _body(self, t, height, half_foot):
        """The fin starting at t and `height` high, its foot `half_foot` wide to
        either side, without its tines."""
        return one_fin(self.p, self.stretch, t, height, self.thickness, half_foot, [])[0]

    def _frame_for(self, own_frame):
        """`own_frame`, the frame of a fin that has one of its own, or the plan's for None."""
        return self.stretch if own_frame is None else own_frame

    def tines(self, t, own, own_frame=None):
        """The heights the tines of a fin starting at t are planned at, those
        of them below a height of its own, and those of its grid left out
        where the face is narrower than the fin (wide_enough()). `own_frame`
        is the frame of a fin that has one of its own, the plan's otherwise.

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
        return self._measured(t, own, own_frame)[:3]

    def short(self, t, own, own_frame=None):
        """The heights of the one grid of the face the fin starting at t lacks
        where the face is wider than the fin under it, but the stretch every
        tine of the face shares is shorter there than a fin needs
        (room_for_one_fin()): tines() names the others, where it is narrower
        than the fin.

        INPUTS this has to withstand:
          the face wide enough there for a fin
            and its end insets                ->  not lacked, not named
          wider than the fin under it, not
            wide enough for its end insets    ->  named here
          narrower than the fin under it, or
            no face there                     ->  not here: tines() names it narrow
          a fin on a grid of its own (restart)->  none: its own grid has no such height
          round side                          ->  none: every tine is planned
        """
        return self._measured(t, own, own_frame)[3]

    def _measured(self, t, own, own_frame):
        """tines() and short(), measured once for each fin, place and frame."""
        own_frame = self._frame_for(own_frame)
        key = (t, own, id(own_frame))
        if key not in self._tines:
            self._tines[key] = self._measured_tines(t, own, own_frame)
        return self._tines[key]

    def _measured_tines(self, t, own, own_frame):
        """tines() and short(), measured."""
        p, frame = self.p, self.stretch
        own_z = None
        if self.restart:
            own_z = restarted_tines(p, frame, self.support, t, self.thickness,
                                    p.fin_height if p.fin_height > 0 else own_frame.room, self.count)
        elif own_frame is not frame:
            # Set higher than this fin reaches, it ends at the top of its own
            # contour; the fin under the lowest line keeps the height set.
            own_z = face_tines(_within(p, own_frame.room), own_frame, self.count, False)[0]
        grid = self.tine_z if own_z is None else own_z
        short = []
        if frame.round_side:
            planned_z, narrow = grid, []
        else:
            def wide_here(z):
                return wide_enough(extent_at(self.support, self.whole_face, z, p, self.slices), p, t, self.thickness)
            # Measured on the whole face: a fin moved past the stretch every
            # tine of the face shares keeps the tines where it is wide enough.
            wide = [wide_here(z) for z in grid]
            planned_z = [z for z, fits in zip(grid, wide) if fits]
            narrow = [z for z, fits in zip(grid, wide) if not fits]
            if own_z is None:
                # On the one grid, what the face as a whole cannot take this fin
                # lacks too: narrow where the face is narrower than the fin
                # under it, short where only the stretch shared is too short.
                for z in sorted(self.face_narrow):
                    (short if wide_here(z) else narrow).append(z)
        return (planned_z, [z for z in planned_z if own is None or z + p.tine_height <= own + d.TOLERANCE], narrow,
                short)

    def at(self, t, own, own_frame=None):
        """What the fin starting at t has there: the heights of tines() and
        those of the planned ones lying on the face."""
        own_frame = self._frame_for(own_frame)
        planned_z, candidate_z, narrow = self.tines(t, own, own_frame)
        key = (t, tuple(planned_z), id(own_frame))
        if key not in self._contact:
            self._contact[key] = touching_at(own_frame, self.support, self.p, planned_z, t, self.thickness)
        return planned_z, candidate_z, narrow, self._contact[key]

    def height_of(self, zs):
        """The height of the face (mm) that tines at `zs` span, from the bottom
        of the lowest to the top of the highest; 0 for none. A hole they bridge
        counts: they hold the fin on both sides."""
        return max(zs) + self.p.tine_height - min(zs) if zs else 0.0

    def held_by(self, candidate_z, resting):
        """The height of the face that the tines at `candidate_z` lying on it hold."""
        return self.height_of([z for z in candidate_z if z in resting])

    def holds(self, t, own, wanted):
        """Whether the tines of the fin starting at t hold `wanted` mm of the
        face. A place whose tines could not even span that is rejected before
        any contact is measured."""
        if self.height_of(self.tines(t, own)[1]) < wanted - d.TOLERANCE:
            return False
        _, candidate_z, _, resting = self.at(t, own)
        return self.held_by(candidate_z, resting) >= wanted - d.TOLERANCE


def _better_place(places, t0, room, others):
    """Where the fin planned at t0, free to find its own place, stands: the
    nearest place holding BETTER_PLACE_HOLDS times what its tines hold at t0,
    t0 where none does. Measured without a height of its own: that is set on
    a fin standing here, and lowering it does not send the fin elsewhere.
    Searching costs a cut through the face at every place tried, so none
    where no place could hold enough. `others` are the starts of the other
    fins, which it stays between and clear of (nearest_place()).

    INPUTS this has to withstand:
      one grid                          ->  t0: the fin as it was
      a fin on a corner                 ->  t0: that place was asked for
      no tine on the face               ->  t0: for the search for any tine
      holding BETTER_PLACE_HOLDS times
        as much would pass the room, the
        fin height set or what a fixed
        tine count can reach            ->  t0: no place can hold that
      on a short stretch                ->  the nearest place holding
                                            BETTER_PLACE_HOLDS times as much, t0
                                            if there is none
      that place past the stretch every
        tine of the face shares         ->  found there: the whole face is searched
      bridging a hole                   ->  as any other: both sides count
    """
    p = places.p
    if not places.restart or p.on_corner:
        return t0
    _, candidate_z, _, resting = places.at(t0, None)
    held = places.held_by(candidate_z, resting)
    if not held:
        return t0
    most = p.fin_height if p.fin_height > 0 else room
    if places.count:
        most = min(most, (places.count - 1) * p.tine_spacing + p.tine_height)
    wanted = held * d.BETTER_PLACE_HOLDS
    if wanted > most + d.TOLERANCE:
        return t0
    # Over the whole face: the stretch every tine shares can be a narrow part
    # of it, such as the web of a T, where no place holds more.
    better = nearest_place(places.whole_face, p.end_inset, partial(places.holds, own=None, wanted=wanted), t0,
                           places.thickness, others)
    return t0 if better is None else better


def _resting_place(places, t0, own, others):
    """The nearest place for the fin planned at t0, free to find its own
    place, where a tine below a height `own` of its own, None for none, lies
    wholly on the face; None if there is none. Searched over the whole face,
    as for _better_place(); `others` as there."""
    p = places.p
    return nearest_place(places.whole_face, p.end_inset, partial(places.holds, own=own, wanted=p.tine_height), t0,
                         places.thickness, others)


def _plan(part, frame, support, p, all_z, face_height, reach, count, restart, left_out, shifts, heights, slices,
          frames):
    """The fins of the face planned for a fin height of at least `reach`,
    from which their thickness and foot follow. With `restart`, each fin is
    tried on its own tine grid (restarted_tines()), at its planned place and
    at every place it might move to; without, on `all_z`.
    `slices` is the dict of extent_at() kept for the build. `frames` holds,
    by number, the frame of a fin that has one of its own (side_frames()), on
    which it gets its own heights of tines."""
    height = max(face_height, reach)
    thickness = thickness_for(p, height)
    if p.tine_width > thickness:
        raise FinError(translate("FinSnap", "tines (%.2f mm) are wider than the fin (%.2f mm)")
                       % (p.tine_width, thickness))
    room_needed = room_for_one_fin(p, frame, thickness)
    tine_z, low, high, gap_z = tines_on_face(support, frame, all_z, p, room_needed, slices)
    if restart:
        low, high = fin_stretch(support, frame, p, room_needed, count, low, high, slices)
    # Also with a fixed tine count: tines the narrow face cannot take are left
    # out and named, as over a recess, rather than refusing the whole fin.
    face_narrow = set(all_z) - set(tine_z) - set(gap_z)
    if face_narrow:
        # Fewer tines make a lower and so a thinner fin; it still fits where the thicker one did.
        height = max(p.fin_height if p.fin_height > 0 else tine_z[-1] + p.tine_height, reach)
        thickness = thickness_for(p, height)
    # Each fin names what of the one grid it lacks (_Places.short()), as far as
    # it reaches up; under a round side, where every tine is planned, the face.
    narrow_heights = set(face_narrow) if frame.round_side else set()
    short_heights = set()
    # Fins left out are named by their distance from this end of the face.
    face_start = frame.along_min
    # The face as a whole, before it is narrowed to the stretch every tine
    # shares: _Places measures a fin moved past that stretch on it, by hand
    # or by a search for a place of its own.
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
    def feet_for(fin_starts):
        return foot_half_width_for(p, (s_to - s_from) / 2, thickness, [] if frame.round_side else fin_starts)

    half_foot = feet_for([t0 for t0, _ in standing])

    places = _Places(p=p, part=part, support=support, stretch=frame, whole_face=whole_face, thickness=thickness,
                     half_foot=half_foot, tine_z=tine_z, face_narrow=face_narrow, restart=restart, count=count,
                     slices=slices)

    fins = []
    # Fins that left their planned place by themselves, as (number, mm moved).
    moved_fins = []
    fins_left_out = []
    # Fins moved clear of the part standing out of the face, by number, and
    # where fins with no place clear of it stood, from the end of the face.
    cleared, blocked = [], []
    # Fins neither stands, by number: no longer a neighbour to move round or
    # to keep a foot clear of.
    gone = set()
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
        room = own_frame.room
        # A fin height set by hand for this fin alone: tines above it are left out.
        own = heights.get(number)
        if own is not None and own > room + d.TOLERANCE:
            raise refused(translate("FinSnap", "fin %d is %.2f mm high, above the face (%.2f mm)")
                           % (number, own, room), HandEditError)
        # Only a fin nobody moved and not under a lowest line finds its own place.
        free = not frame.round_side and number not in shifts
        others = [starts[n] for n in starts if n != number and n not in left_out and n not in gone]
        planned_at = t0
        if free:
            t0 = _better_place(places, t0, room, others)
        planned_z, candidate_z, narrow, touching = places.at(t0, own, own_frame)
        if own is not None and not candidate_z:
            raise refused(translate("FinSnap", "fin %d is lower than its first tine") % number, HandEditError)
        # A tine wholly or partly over a recess or a hole in the face would hang
        # free there; it is left out, and a fin without any tine left with it.
        # Tried at every height planned, also above a height of its own: those
        # are the heights the fin can be given with a tine on top.
        if free and not places.held_by(candidate_z, touching):
            moved_to = _resting_place(places, t0, own, others)
            if moved_to is not None:
                t0 = moved_to
                planned_z, candidate_z, narrow, touching = places.at(t0, own, own_frame)
        # Where the part stands out of a planar face, as a boss, in the way of
        # the fin, it moves to the nearest place clear of it and with a tine on
        # the face, or is left out; a fin moved there by hand is refused.
        if not frame.round_side and not places.clear_at(t0, own):
            if not free:
                raise refused(translate("FinSnap", NOTE_FIN_IN_PART) % number, HandEditError)

            def clear_and_resting(t, own=own):
                return (not places.surely_in_part(t, own) and places.holds(t, own, p.tine_height)
                        and places.clear_at(t, own))
            moved_to = nearest_place(whole_face, p.end_inset, clear_and_resting, t0, thickness, others)
            if moved_to is None:
                # Named where it was planned, as the user knows it.
                blocked.append(planned_at + thickness / 2 - face_start)
                gone.add(number)
                continue
            t0 = moved_to
            cleared.append(number)
            planned_z, candidate_z, narrow, touching = places.at(t0, own, own_frame)
        if t0 != planned_at:
            moved_fins.append((number, t0 - planned_at))
            starts[number] = t0
        on_face = [z in touching for z in candidate_z]
        # Tines of its own grid left out where the face is too narrow are named
        # with those of the face, as far as the fin reaches up to them.
        def reached(zs, own=own):
            return {z for z in zs if own is None or z + p.tine_height <= own + d.TOLERANCE}
        narrow_heights.update(reached(narrow))
        short_heights.update(reached(places.short(t0, own, own_frame)))
        kept_z = [z for z, whole in zip(candidate_z, on_face) if whole]
        if not kept_z:
            fins_left_out.append(t0 + thickness / 2 - face_start)
            all_too_narrow = all_too_narrow and not planned_z
            gone.add(number)
            continue
        # An automatic fin ends at its highest tine left, so no part of it
        # stands above the last contact with the face.
        if own is not None:
            fin_height = own
        else:
            set_height = _within(p, room).fin_height if number in frames else p.fin_height
            fin_height = set_height if set_height > 0 else kept_z[-1] + p.tine_height
        fins.append(PlannedFin(number, t0, fin_height, candidate_z, on_face, sorted(touching)))
    if not fins and blocked:
        raise refused(translate("FinSnap", NOTE_BLOCKED_OR_BARE if fins_left_out else NOTE_ALL_BLOCKED))
    if not fins and fins_left_out and all_too_narrow:
        raise refused(translate("FinSnap", NARROW_AT_EVERY_TINE) % thickness)
    if not fins:
        raise refused(translate("FinSnap", "no tine finds the face; it has a recess or hole at every tine"))
    if moved_fins or gone:
        # The feet stay clear of each other where the fins ended up. Wider than
        # planned, where a fin moved off or is gone, they are taken only clear
        # of the part too; narrower always, or they would overlap.
        feet = feet_for([starts[number] for number in sorted(starts) if number not in left_out and number not in gone])
        if feet <= half_foot + d.TOLERANCE or frame.round_side or all(
                places.clear_at(fin.t0, heights.get(fin.number), feet) for fin in fins):
            half_foot = feet
    return FacePlan(frame, height, thickness, tine_z, gap_z, narrow_heights, positions, face_start,
                    starts, half_foot, fins, moved_fins, fins_left_out, cleared, blocked,
                    short_heights - narrow_heights, room_needed)


@dataclass
class _Found:
    """What building the fins of a plan found that a warning names (_warnings())."""
    # Fins beside the lowest line that cannot stand there, by number.
    side_missing: list
    # Heights of tines left out over a recess or the gap between two faces in
    # one plane, and the fins with such tines, by number.
    gap_heights: set
    gapped: list = field(default_factory=list)
    # Every tine left out, wherever.
    dropped: list = field(default_factory=list)
    # Along a contour: tines left out where it falls back further than the
    # flank can follow, and the fins they belong to. Those in a recess the
    # fin bridges are left out as asked, without a word.
    receded_heights: set = field(default_factory=set)
    receded_fins: list = field(default_factory=list)
    receded_tines: list = field(default_factory=list)
    # Tines whose end misses the face or reaches into the part, by fault, as
    # (fin number, height, tine).
    off_ends: dict = field(default_factory=lambda: {TINE_MISSES: [], TINE_CUTS_IN: []})
    # Fins beside the lowest line that end below what passes beside them.
    ended_lower: list = field(default_factory=list)
    # Fins beside the lowest line that lost tines to a foot standing further out.
    tines_at_foot: list = field(default_factory=list)
    # Fins beside the lowest line whose contour ends below the fin height set.
    below_set_height: list = field(default_factory=list)


def _warnings(p, frame, plan, findings):
    """The warnings of a build of the fins of `plan` on `frame`, from the
    `findings` of building them (_Found), and with each what it is about, as
    a WarningTarget, in the same order."""
    warnings, targets = [], []
    if findings.gap_heights:
        warnings.append(translate("FinSnap", "tines at %s mm above the bed left out: a recess or hole in the "
                                  "face lies under them") % _mm_list(findings.gap_heights))
        targets.append(WarningTarget(findings.gapped, findings.dropped, False))
    if findings.receded_heights:
        warnings.append(translate("FinSnap", NOTE_CONTOUR_RECEDES) % _mm_list(findings.receded_heights))
        targets.append(WarningTarget(findings.receded_fins, findings.receded_tines, False))
    for fault, note in ((TINE_MISSES, NOTE_TINES_MISS), (TINE_CUTS_IN, NOTE_TINES_CUT_IN)):
        ends = findings.off_ends[fault]
        if ends:
            warnings.append(translate("FinSnap", note) % (_mm_list({z for _, z, _ in ends}), d.TINE_END_TOLERANCE))
            targets.append(WarningTarget(sorted({number for number, _, _ in ends}), [tine for _, _, tine in ends],
                                         False))
    for note, numbers_of in ((NOTE_ENDED_LOWER, findings.ended_lower),
                             (NOTE_BELOW_SET_HEIGHT, findings.below_set_height),
                             (NOTE_TINES_AT_FOOT, findings.tines_at_foot),
                             (NOTE_SIDE_FIN_LEFT_OUT, findings.side_missing)):
        if numbers_of:
            warnings.append(translate("FinSnap", note) % ", ".join(str(number) for number in numbers_of))
            standing = [number for number in numbers_of if number not in findings.side_missing]
            targets.append(WarningTarget(standing, [], False))
    # A fin moved clear of the part is named for that alone, also if it moved
    # for its tines before.
    for note, moves in ((NOTE_MOVED, [move for move in plan.moved if move[0] not in plan.cleared]),
                        (NOTE_CLEARED, [move for move in plan.moved if move[0] in plan.cleared])):
        if moves:
            warnings.append(translate("FinSnap", note) % ", ".join(
                translate("FinSnap", "fin %d by %.2f mm") % (number, mm) for number, mm in moves))
            targets.append(WarningTarget([number for number, _ in moves], [], False))
    if plan.fins_left_out:
        warnings.append(translate("FinSnap", "fins at %s mm from the end of the face left out: none of their "
                                  "tines lies wholly on the face") % _mm_list(plan.fins_left_out))
        targets.append(WarningTarget([], [], True))
    if plan.blocked:
        warnings.append(translate("FinSnap", NOTE_BLOCKED) % _mm_list(plan.blocked))
        targets.append(WarningTarget([], [], True))
    if plan.narrow_heights:
        warnings.append(translate("FinSnap", "tines at %s mm above the bed left out: the face is narrower "
                                  "there than the fin") % _mm_list(plan.narrow_heights))
        targets.append(WarningTarget([], [], True))
    if plan.short_heights:
        warnings.append(translate("FinSnap", NOTE_FACE_SHORT) % (_mm_list(plan.short_heights), plan.room_needed))
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
    return warnings, targets


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
    frames, side_missing = {}, []
    if frame.whole_side and p.round_fins != d.ROUND_FINS_ONE:
        if frame.contour is None:
            raise FinError(translate("FinSnap", NOTE_SIDE_FINS_NEED_CONTOUR))
        frames, side_missing = side_frames(part, frame, p, thickness_for(p, bounds(part).ZLength), shifts)
        left_out = list(left_out) + side_missing
        if p.round_fins == d.ROUND_FINS_TWO and len(side_missing) == len(side_numbers(p.round_fins)):
            raise FinError(translate("FinSnap", NOTE_NO_SIDE_FIN))
    # The slices of the face at the height of a tine, kept for every plan of this build.
    slices = {}
    count = p.tine_count if tine_count is None else tine_count
    restart = p.tine_restart and not frame.round_side
    all_z, face_height = face_tines(p, frame, count, restart)
    plan = _plan(part, frame, support, p, all_z, face_height, 0.0, count, restart, left_out, shifts, heights,
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
        plan = _plan(part, frame, support, p, all_z, face_height, reach, count, restart, left_out, shifts,
                     heights, slices, frames)
    frame, thickness = plan.frame, plan.thickness

    bodies = []
    all_tines = []
    pieces = []
    # Tines over the gap between two faces in one plane are named as over a recess.
    findings = _Found(gap_heights=set(plan.gap_z), side_missing=side_missing)
    edges = []
    built_fins = []
    for fin in plan.fins:
        own_frame = frames.get(fin.number, frame)
        faults, piece = None, None
        if fin.number in frames:
            planned_height, planned_tines = fin.height, sum(fin.on_face)
            key = (shape_key(part), _shaping(p), fin.number, fin.t0, fin.height, tuple(fin.candidate_z),
                   tuple(fin.on_face), thickness, plan.half_foot, own_frame.tine_edges[0][0])
            side_found = keep(_kept_side_fins, key,
                              partial(_side_fin, p, part, surface, own_frame, fin, thickness, plan.half_foot),
                              SIDE_FINS_KEPT)
            if side_found is None:
                findings.side_missing.append(fin.number)
                continue
            body, tines, edge, own_frame, fin, faults, piece = side_found
            frames[fin.number] = own_frame
            if fin.height < planned_height - d.TOLERANCE:
                findings.ended_lower.append(fin.number)
            elif sum(fin.on_face) < planned_tines:
                findings.tines_at_foot.append(fin.number)
            if planned_height < p.fin_height - d.TOLERANCE:
                findings.below_set_height.append(fin.number)
        else:
            body, tines, edge = one_fin(p, own_frame, fin.t0, fin.height, thickness, plan.half_foot, fin.candidate_z)
        kept = [tine for tine, whole in zip(tines, fin.on_face) if whole]
        left = [(z, tine) for z, tine, whole in zip(fin.candidate_z, tines, fin.on_face) if not whole]
        findings.dropped += [tine for _, tine in left]
        if frame.contour is not None:
            receded = [(z, tine) for z, tine in left if frame.contour.receded(z, z + p.tine_height)]
            findings.receded_heights.update(z for z, _ in receded)
            findings.receded_tines += [tine for _, tine in receded]
            if receded:
                findings.receded_fins.append(fin.number)
        elif left:
            findings.gap_heights.update(z for z, _ in left)
            findings.gapped.append(fin.number)
        built_fins.append(fin)
        edges.append(edge)
        bodies.append(body)
        all_tines.extend(kept)
        # Each tine kept, its end measured against the part itself.
        if faults is None:
            faults = _tine_faults(p, surface, own_frame, fin, thickness, kept)
        for fault, z, tine in faults:
            findings.off_ends[fault].append((fin.number, z, tine))
        # One general fuse instead of one tine after the other: the lowest tine
        # sits on the top of the foot, where foot, flank and tine share an edge,
        # and fusing them pairwise fails on that edge.
        pieces.append(body.multiFuse(kept).removeSplitter() if piece is None else piece)

    if not built_fins:
        raise FinError(translate("FinSnap", NOTE_NO_SIDE_FIN))
    fins = Part.makeCompound(pieces)
    # Fins beside the lowest line were measured as they were built.
    measured = [body for fin, body in zip(built_fins, bodies) if fin.number not in frames]
    check(p, part, pieces, measured, 0.0 if frame.contour is None else d.CONTOUR_TOLERANCE)
    warnings, targets = _warnings(p, frame, plan, findings)

    numbers = [fin.number for fin in built_fins]
    fin_heights = [fin.height for fin in built_fins]
    return FinResult(fins=fins, bodies=bodies, tines=all_tines, height=max(fin_heights),
                     thickness=thickness, tine_z=plan.tine_z, positions=[fin.t0 for fin in built_fins],
                     foot_half_width=plan.half_foot, warnings=warnings, warning_targets=targets,
                     carried=support.Faces,
                     numbers=numbers, planned=len(plan.positions),
                     dropped=findings.dropped, starts={n: plan.starts[n] for n in numbers}, along=frame.along,
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
