# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Build fins on the reference cube and check the result.

Run in FreeCAD, with this checkout installed as an addon (see CONTRIBUTING.md):
    freecad --console freecad/finsnap/tests/test_cube.py
"""

import math
import os
import re
import sys
import types

import numpy

import Part

from freecad.finsnap.tests.support import (CHAMFER, EDGE, HALF_TURN, RECESS_RADIUS, TILT, expect, grooved,
                                           largest_facing, lower_left_face, run, slot_on_end, split_cylinder, tilted,
                                           tilted_cube)
from freecad.finsnap import analysis
from freecad.finsnap import defaults as d
from freecad.finsnap import bridge as bridging
from freecad.finsnap.bridge import bridges as find_bridges
from freecad.finsnap import contour, face_frame, geometry, quick_stands, tine_rows
from freecad.finsnap import limits
from freecad.finsnap import orient
from freecad.finsnap import overhang
from freecad.finsnap import stability
from freecad.finsnap import shapes
from freecad.finsnap.shapes import Meshed
from freecad.finsnap.params import FinParams, ParamError

import FreeCAD as App

V = App.Vector
PYRAMID_BASE = 20.0
PYRAMID_STEEP = 20.0   # sides at 63 degrees against the base
PYRAMID_FLAT = 5.0     # sides at 27 degrees, flatter than the overhang limit
PYRAMID_TILT = 30.0    # flatter than the overhang limit
# Sides of pyramids standing on their apex for the levels of overhangs, in
# degrees from the bed: steeper than the critical limit, between the two
# limits, and flatter than the unprintable one.
SIDE_STEEP, SIDE_CRITICAL, SIDE_UNPRINTABLE = 60.0, 40.0, 20.0
# A slab on two piers for bridges: the piers this wide, deep and high, the
# slab this thick; gaps between the piers spanned short, critically and too far
# by the built-in limits, and a slab this much deeper than wide across the gap.
PIER = (5.0, 10.0, 10.0)
SLAB = 2.0
GAP_SHORT, GAP_CRITICAL, GAP_FAR = 1.5, 8.0, 15.0
DEEP_SLAB = 40.0
# A box as wide as the one lying flat, four times as high, and how closely its
# tipping angle is to atan(margin / height of its centre of mass) (degrees).
TALL_BOX_HEIGHT = 80.0
ANGLE_TOLERANCE = 0.5
# How closely a span is measured: a bead is laid across in lines one bead apart.
SPAN_TOLERANCE = 0.1
LINES_SIDE = 10.0  # side of a square the lines of a bridge are laid across, in whole mm
LINES_HOLE = (4.0, 4.0, 6.0, 6.0)  # a hole in it, from corner to corner, in whole mm
ROUND_TABLE = 20.0  # radius of a disc on a ring wall, in mm
ROUND_POST = 3.0  # radius of a post in the middle of it, in mm
LINES_SPACING = 1.0  # how far apart the lines are laid across that square, in mm
LINES_PAST = 1.0  # how far past the square they are laid, in mm
LINES_BESIDE = 1.0  # how far beside the square a point is put that lies outside it, in mm
LINES_DIGITS = 6  # places the ends of their pieces are compared to
LINES_FACETS = 200  # flat sides of a round outline as a part from a mesh has it
ODD_TILT = 30.0        # any angle but 45, at which a right-angled edge needs its face
# First tines half a layer (0.1 mm) off the grid of 0.2 mm layers.
HALF_LAYER_STARTS = (1.1, 1.3, 1.5, 1.7)
WIDE_NOZZLE = 0.8
WIDE_BEAD = 0.9       # two of them are thicker than the 1 mm base
GROOVE_DEPTH = 2.0     # a groove across the front of a box, splitting it
SINK_DEPTH = 0.5       # how deep the face is sunk around a stretch of it, so that stretch is a face of its own
SINK_INSET = 0.5       # how far that stretch ends inside the grid tines below and above it, in mm
SHORT_STRETCH_RECESS = 4.0  # half the width of a recess from the bed up, wider than a fin, in mm
SHORT_STRETCH_LEFT = 2.0    # height of the face left above that recess, in mm
CORNER_WALL = 0.1           # the face left at its end beside such a recess, thinner than a tine, in mm
POINTED_HALF_WIDTH = 30.0   # half the width of a face that tapers towards the bottom, in mm
POINTED_END_HALF_WIDTH = 2.0  # half its width at its lower edge, room for one fin, in mm
POINTED_WIDEST_AT = 8.0     # how far up it that width is reached, in mm
POINTED_TOP = 30.0          # how far up it the face ends, in mm
POINTED_DEPTH = 40.0        # how far back the part reaches behind that face, in mm
POINTED_LIFT = 2.0          # how far its lower edge stands above the bed, above the first grid tine, in mm
SKEWED_LOW = 3.0            # half the width of a face leaning aside as it rises, at its lower edge, in mm
SKEWED_WIDE = 28.0          # how far along it reaches higher up, in mm
SKEWED_WIDEST_AT = 10.0     # how far up it reaches that far, in mm
FEET_EDGE = 60.0            # a cube long enough for several fins with feet, in mm
FEET_RECESS = 8.0           # half the width of a recess that sends the middle one of them aside, in mm
FEET_FINS = 5
# A T standing on its narrow web, tilted TILT so its front overhangs: the web
# this wide and high, the flange this wide and the T this high and deep, and a
# slot this wide up the flange above the web, from this far above the web, so
# the stretch every tine of the face shares is the web (t_beam()).
T_WEB, T_WEB_HIGH = 10.0, 10.0
T_FLANGE, T_HIGH, T_DEEP = 70.0, 60.0, 10.0
T_SLOT, T_SLOT_ABOVE_WEB = 16.0, 2.0
OUT_OF_REACH = 100.0   # a height or a width beyond any test part, in mm
NOTCH_CLEAR = 1.0      # how far a notch in the end of a face stays from the grid tines, and its depth, in mm
PIN_HOLE_RADIUS = 0.9  # a hole that splits the face under a tine, small enough to leave the tines beside it
ISLAND_SPAN = 40.0     # length of the beam of the bridge islands hang from, in mm
ISLAND_DEPTH = 10.0    # depth of the bridge and of what hangs from it
ISLAND_TOP = 30.0      # height of the top of the bridge
ISLAND_BEAM = 5.0      # thickness of its beam, and of the cap of a mushroom
ISLAND_LOW = 10.0      # height of the bottom of what hangs from it, well above the bed
ISLAND_LAYER = 50      # a layer on whose middle the bottom of a hanging block or a slab is put
# How far beside a height where the layer changes a point is put to fall clearly on one side of it (mm):
# far more than rounding or the kernel moves it, well less than the tolerance.
BESIDE = d.TOLERANCE / 10
# First layer and layer heights the cut heights are checked with (mm): the first as high as the others, and
# higher and lower; and the layers whose middles they are checked at, the lowest among them.
LAYERINGS = ((d.FIRST_LAYER_HEIGHT, d.LAYER_HEIGHT), (1.5 * d.LAYER_HEIGHT, d.LAYER_HEIGHT),
             (d.LAYER_HEIGHT / 2, d.LAYER_HEIGHT))
CUT_LAYERS = (1, 2, ISLAND_LAYER)
COMB_TEETH = 4         # blocks or steps in layers one above the other, to count the cuts of them
COMB_TOOTH = ISLAND_SPAN / 16  # width of such a block and of the room between two, in mm
ISLAND_PILLAR = ISLAND_SPAN / 4  # width of the pillar of the bridge islands hang from, in mm
ISLAND_BLOCK = ISLAND_PILLAR  # width of a block hanging from its beam, in mm
ISLAND_UNDER = ISLAND_TOP - ISLAND_BEAM  # height of the underside of its beam, in mm
RIDGE_INTO_SLAB = SLAB / 2  # how far a ridge hanging from a slab reaches up into it, in mm
# How far above the middle of a layer something starts that is to lie clear of it, and below it, in mm.
CLEAR_OF_MIDDLE = d.LAYER_HEIGHT / 4
CUTS_LOW = 10.0  # the lowest of some heights to cut a part at together, in mm
CUTS_FEW = 3  # heights cut together where fewer are to be than as many as can
STOCK_LAYERS = (10, 20, 30)  # layers through the piers of a slab on piers, to cut it at their middles
CUTS_DIGITS = 4  # places the area of a cut, a point or a span is compared to
CUTS_AS_SET = overhang.CUTS_MOST  # how many heights are cut together, to put back after a test changed it
# How far from that middle it is put (mm): well below and above, right on it, within the tolerance of it,
# where it counts to the layer above, just beside the tolerance below, on either side of where the layer
# changes, and one to two tolerances below, where it counts to that layer.
MIDDLE_OFFSETS = (-CLEAR_OF_MIDDLE, -1.5 * d.TOLERANCE, -d.TOLERANCE - BESIDE, -d.TOLERANCE + BESIDE,
                  -d.TOLERANCE / 2, 0.0, d.TOLERANCE / 2, 1.5 * d.TOLERANCE, CLEAR_OF_MIDDLE)
ISLAND_STEM = 3.0      # radius of the stem of a mushroom, and of a hole through a box
ISLAND_CAP = 10.0      # radius of the cap of a mushroom
STABLE_TOLERANCE = 0.05  # how far a plumb line or a margin may be off what is reckoned, in mm
STABLE_BASE = 10.0     # side of a column on the bed, and of the arm out of its top
STABLE_HEIGHT = 20.0   # height of that column
STABLE_REACH = 30.0    # how far its arm reaches out, carrying the centre of mass past the column
STABLE_BRIM = 20.0     # a brim wide enough to hold a slab standing on its edge
LEAN_DISC_RADIUS = 20.0         # a disc whose round flat face takes fins leaning
LEAN_DISC_HEIGHT = 10.0         # its height, the face on top
LEAN_DISC_FILLET = 4.0          # a fillet round its top, bulging past the rim of that face once it leans
TINY_LEAN_DISC_RADIUS = 0.5     # a disc whose round face takes no fin
LEAN_DISC_TURN = 30.0           # how far the disc is turned before Quick fins, in degrees
LEAN_DISC_TURN_AXIS = V(1, 1, 0)  # about an axis neither along X nor Y
TINE_END_MESH_DEFLECTION = 0.1  # how closely the mesh of the reference cube, made a solid again, follows it, in mm
TINE_END_SHIFT = 0.5  # how far tine ends are measured off the face to be named, in mm
TINE_END_SEW_TOLERANCE = 0.01  # how far apart points of that mesh are sewn into one, in mm
CENTRE_SHARES = (0.1, 0.37, 0.5, 0.83)  # heights the centres of mass are compared at, as shares of the part's
CENTRE_FLAT_TOLERANCE = 1e-6    # how far a centre from the mesh may lie off the cut one, flat faces only, in mm
CENTRE_CURVED_TOLERANCE = 0.05  # the same with curved faces, which the mesh only follows, in mm
CENTRE_CUT_MARGIN = 1.0         # how far the box cutting out the part below a height reaches past it, in mm
FILLET_RADIUS = 3.0    # a fillet along the edge a part rests on, its leaning face starting above it
WIDE_FIN = 3.0         # a fin thick enough for a hole under its flank, clear of its tine, in mm
FLANK_HOLE_RADIUS = 0.5  # that hole, across the side of the fin, in mm
GROOVE_WIDTH = 2.0
GROOVE_FROM = 8.0
WIDE_BOX = 60.0          # long enough for a U profile with legs of a third each
SHIFT = 1.5           # how far a fin is moved along the face by hand, in mm
MERGED_CLEARANCE = 0.3  # a tine clearance that merged fins must not take
# A nozzle and bead so wide that no gap up to GAP_MAX makes the tines long
# enough, and a layer it prints, in mm.
WIDE_NOZZLE = 4.0
WIDE_LAYER = 1.0
UP = V(0, 0, 1)
BOX_SIDE = 20.0
EDGE_ROUND = 3.0       # size of the chamfer or radius of the fillet on a box edge
CHAMFER_LONG = 3.0     # the long leg of a chamfer of unequal widths on a rim, in mm
CHAMFER_SHORT = 1.0    # its short leg
# Bosses on the face of the tilted cube (bossed_cube()): how high they stand
# out, the radii one fin moves aside from, one beside the fin, the shift by
# hand onto it, one over the middle of the face, one over all of it (mm).
BOSS_HEIGHT = 3.0
BOSS_RADII = (1.5, 3.0)
BOSS_BESIDE = 4.0
BOSS_SHIFT = 6.0
BOSS_MIDDLE = 6.0
BOSS_WIDE = 9.0
# Faces of straight edges leaning over the bed (check_straight_faces()): how far
# they lean (degrees), how much a cut worked out may differ from the kernel's
# (mm), and the layer a stretch is made to end on.
STRAIGHT_LEAN = 55.0
STRAIGHT_SAME = 1e-6
STRAIGHT_LAYER = 0.2
# Their outlines, flat before they lean (mm): how wide and how high the
# rectangle is that all of them start from, the upper corners of the slanted
# quad, where the tip of the triangle lies, how far in the L and the U step,
# from where to where the square hole and the notch of the U reach, across and
# upwards, and the radius of the round hole in the middle.
STRAIGHT_WIDE = 20.0
STRAIGHT_HIGH = 30.0
STRAIGHT_SLANTED_TOP = ((23.0, 30.0), (-2.0, 27.0))
STRAIGHT_TIP = 9.0
STRAIGHT_STEP = 8.0
STRAIGHT_HOLE_ACROSS = (6.0, 14.0)
STRAIGHT_HOLE_UP = (10.0, 20.0)
STRAIGHT_ROUND_HOLE = 4.0
# Where they are cut: the heights as shares of the height of the face, how far
# below and above it a height misses it (mm), and the places along a fin, the
# last two beside the face (mm). None of them through a corner or along an edge.
STRAIGHT_SHARES = (0.07, 0.31, 0.5, 0.77, 0.93)
STRAIGHT_PAST = 1.0
STRAIGHT_PLACES = (1.3, 4.9, 9.7, 11.1, 13.3, 17.7, -5.0, 40.0)
# A face that is not planar: the radius and the height of a cylinder (mm).
STRAIGHT_CURVED = (10.0, 20.0)
# The hole a stretch ends at on a layer boundary: its lower and upper edge in
# layers up the face, where the fin tried there starts and where the stretches
# are asked for, inside the hole (mm).
STRAIGHT_HOLE_LAYERS = (40, 75)
STRAIGHT_FIN_AT = 9.0
STRAIGHT_BANDS_AT = 9.5
# Solids whose mesh tells which points lie inside them (check_enclosed()): the
# edge of a cube, how thick the walls of the hollow one are, the radius, the
# height and the radius of the bore of a tube, and round it where the points
# in it are taken, at what angle (degrees) and share of its height (mm).
ENCLOSED_EDGE = 10.0
ENCLOSED_WALL = 2.0
ENCLOSED_TUBE = (10.0, 20.0, 4.0)
ENCLOSED_TUBE_AT = (17.0, 0.37)
# The axis and the angle (degrees) a tube is turned by to lie askew, its long
# triangles then reaching over the grid they are sorted into on every side.
ENCLOSED_ASKEW = ((1.0, 2.0, 3.0), 37.0)
# The points tried on each: a grid of that many a side, reaching that far past
# the solid (mm); a point deep in the cube and one in the hollow of the hollow
# one, off every diagonal of their faces, as shares of the edge; and how far
# off a wall, in margins of the mesh, a point is not told of, and is.
ENCLOSED_GRID = 9
ENCLOSED_PAST = 1.0
ENCLOSED_DEEP = (0.23, 0.41, 0.67)
ENCLOSED_IN_HOLLOW = (0.37, 0.45, 0.58)
ENCLOSED_OFF_UNTOLD = (0.0, 0.1, 0.9)
ENCLOSED_OFF_TOLD = 3.0
# A gap so narrow that the points beside a fin lie within the margin of the
# mesh of what they come near (mm), and a tine clearance that fits it.
ENCLOSED_NARROW_GAP = 0.02
ENCLOSED_NARROW_CLEARANCE = 0.0
# How long the kernel takes a point on the clock of the test, as shares of
# ENCLOSED_KERNEL_SLOW: quick, as on a dome, and slow; and past how many points
# asked a solid is no longer waited for to be settled.
ENCLOSED_QUICK_SHARE = 0.5
ENCLOSED_SLOW_SHARE = 2.0
ENCLOSED_ASKED_MOST = 5000
# A face tapering from the bed up (tapered()): its half width at the bed, how
# deep the part is, and as (half width at the top, height) one wider than a
# fin at the top tine but too narrow for it and its end insets, and one
# narrower there than the fin (mm).
TAPER_BASE_HALF = 10.0
TAPER_DEPTH = 20.0
TAPER_SHORT = (0.2, 12.0)
TAPER_NARROW = (0.0, 11.7)
FLOOR_SIZE = 1000.0    # a plane under every test part, to measure how high it rests
FLOOR_DEPTH = 100.0
FRUSTUM_BASE = 40.0
FRUSTUM_TOP = 20.0
FRUSTUM_HEIGHT = 15.0  # sides at 56 degrees against the base
ROD_RADIUS = 10.0      # a cylinder standing on its rim
ROD_HEIGHT = 40.0
THIN_ROD_RADIUS = 2.0  # too thin for side fins to stand clear of the middle one
PLANE_INSIDE = 0.01    # how far inside the outer edge of a fin it is cut through
BIG = 500.0            # far past any test part
GAP_ACROSS_FIN = 0.01  # how far the gap may differ across the thickness of a fin
SIDE_FIN_MOVE = 0.5    # how far a side fin is moved by hand
CONE_TOP = 3.0         # a cone on top of a rod narrows to this radius
CONE_HEIGHT = 15.0
FILLET_RADIUS = 3.0    # a fillet round the free end of a rod
STEPS_NEAR_FINS = (5.4, 5.5, 5.6, 6.0)  # steps ending about where side fins stand at 30 degrees
TINE_MIDDLE_TOLERANCE = 0.05  # how far off the middle of a side fin a tine may leave it (mm)
OVERHANG_LAYER = 0.2   # layers a side fin is cut into to see what hangs over (mm)
OVERHANG_REACH = 3.0   # how far up its foot and blade are looked at (mm)
OVERHANG_DEFLECTION = 0.05
JOINED_VOLUME_TOLERANCE = 0.01  # mm3, of some 1700: the plane faces of the side fins round a little
FLANK_OUT_LITTLE = 0.2 # how far out a foot may make a side fin stand on a plain side (mm)
# The cases of check_side_fin_matrix(): fins, degrees round the side, fin thickness (0 from its height).
MATRIX_CASES = ((d.ROUND_FINS_TWO, 30.0, 0.0), (d.ROUND_FINS_THREE, 45.0, 0.0), (d.ROUND_FINS_THREE, 30.0, 3.0),
                (d.ROUND_FINS_THREE, 45.0, 3.0))
MATRIX_FIN_COUNTS = {d.ROUND_FINS_TWO: 2, d.ROUND_FINS_THREE: 3}
# Cases with a fin height set, above what the side fins can reach on some shapes.
MATRIX_HIGH_CASES = {"rod": ((d.ROUND_FINS_THREE, 45.0, 0.0, 35.0), (d.ROUND_FINS_THREE, 30.0, 3.0, 35.0),
                             (d.ROUND_FINS_THREE, 30.0, 0.0, 30.0), (d.ROUND_FINS_THREE, 45.0, 2.0, 32.0)),
                     "cone": ((d.ROUND_FINS_THREE, 45.0, 3.0, 38.0),),
                     "thin step": ((d.ROUND_FINS_THREE, 45.0, 3.0, 35.0),),
                     "step near the fins": ((d.ROUND_FINS_THREE, 45.0, 3.0, 35.0),),
                     "fillet": ((d.ROUND_FINS_THREE, 45.0, 0.0, 20.0),)}
# How many tines a side fin has, by shape, for MATRIX_CASES and then MATRIX_HIGH_CASES.
MATRIX_SIDE_TINES = {"rod": (7, 7, 7, 7, 7, 7, 7, 7), "tube": (7, 7, 7, 7), "step near the fins": (13, 7, 13, 7, 7),
                     "flange": (7, 7, 7, 6), "thin step": (7, 7, 7, 7, 7), "cone": (7, 7, 7, 7, 7),
                     "fillet": (7, 7, 7, 7, 5),
                     "large fillet": (5, 6, 5, 5)}
HEIGHT_ACROSS_FIN = 0.02  # how far above the height it says a fin may reach (mm)
LARGE_FILLET_RADIUS = 9.5  # nearly the radius of the rod
MESHED_BOX, MESHED_OFF = 10.0, 0.5  # a box measured by its mesh, and how far off it (mm)
# A fin measured by what it is fused from (check_known_clear()): how far its tine
# ends off the box, and how far a tine reaches into it (mm).
APART_TINE_OFF = 0.05
APART_TINE_IN = 0.2
# A round part that carries a coarse mesh, for the end of a tine measured
# against the faces near it (check_tine_ends()): its radius, its height and how
# closely the mesh follows it (mm); the clearance a tine end is to keep; how
# far off the side a point lies, far nearer than the clearance; and half the
# side of a flat face standing the clearance beyond the point, whose box is
# exact while that of the meshed side stops short (mm).
ENDS_ROUND = (2000.0, 20.0)
ENDS_ROUND_MESH = 5.0
ENDS_ROUND_CLEARANCE = 0.2
ENDS_ROUND_OFF = 0.01
ENDS_ROUND_FLAT = 1.0
# A ring, whose face lies on a torus and so has no box to tell what is near
# it by (check_tine_ends(), check_known_clear()): its two radii (mm).
RING = (10.0, 2.0)
# A round part that carries a mesh: its radius, its height and how closely the
# mesh follows it (mm); the turns about its axis its side is looked at for
# where its BoundBox stops shortest of it (degrees); and the share of that a
# tine cuts into it there.
APART_ROUND = (10.0, 20.0)
APART_ROUND_MESH = 0.02
APART_ROUND_TURNS = (0.0, 90.0, 180.0, 270.0)
APART_ROUND_CUT = 0.9
MESHED_VOLUME_APART = 0.5  # mm3: found on the mesh and exactly, the fins stand within a resolution
FLANK_OUT_MOVED = 0.05  # mm: a blade moved out by more than this has really moved
SETTLE_RESOLUTION, SETTLE_MOST = 0.01, 2.0  # what check_settled_clear() searches to and up to
GROOVE_WIDTH = 4.0     # a groove round a shaft
TINE_NEAR_START = 6.0  # the first tine above a groove starts within this of the side (mm)
AIM_TOLERANCE = 1e-3   # how far off the axis a tine beside the lowest line may aim (cross product, mm2)
RIB_OFF_WALL = 0.1     # a rib stands this far beside the wall of a side fin
RIB_WIDTH = 1.0
RIB_LENGTH = 30.0      # reaching past the fin
RIB_INTO_PART = 1.0    # how far it starts inside the part
RIB_HEIGHT_SHARE = 0.6 # how high up the side fin it stands
THIN_STEP_RADIUS = 3.0 # a step thinner than the side fins stand from the lowest line
FLANGE_RADIUS = 14.0   # a flange at the start of a rod
FLANGE_HEIGHT = 2.0
DISC_HEIGHT = 4.0      # a disc: its flat face is larger than its side, the side takes the fins all the same
BORE_RADIUS = 6.0      # the hole that makes it a tube
ROUND_TURN = 5.0       # how far the fin under a round side is moved by hand, in mm round it
ROUND_DEGREES = 30.0   # how far a part is turned about its round side, in degrees
SLOT_PAST_SIDE = 10.0  # moved that far, the fin stands past the side of the end face, in mm
SLOT_ASIDE = 7.0       # how far a fin is moved along the end face of a slot, towards its side, in mm
ODD_TURNS = (77.0, 200.0)  # turns of a part about its axis before it is stood, in degrees
ABOVE_FACE = 30.0      # how far above its own height a fin is drawn, beyond the face, in mm
NORMAL_DECIMALS = 6    # places to which the directions of faces are compared
# A shaft for the fin along the contour: the cylinder of ROD_RADIUS and
# ROD_HEIGHT, and on it a thinner one, or a body of revolution whose outline
# runs through SPLINE_RADII, as far up again.
STEP_RADIUS = 6.0
# The thinner part only this high, the part stood on its free rim: about 6 mm
# of it carry tines below the side, past CONTOUR_OWN_PART, or, lower, less.
THIN_PART_CARRIES = 14.0
THIN_PART_SHORT = 12.0
# The long leg of a chamfer round the rim the part stands on, tines resting
# on about 4 mm of it, just short of CONTOUR_OWN_PART.
CHAMFER_TALL = 8.0
SPLINE_RADII = (ROD_RADIUS, 9.5, 8.5, 8.0)
GROOVE_DEPTH = 1.0     # a groove round the shaft, as deep and,
GROOVE_LENGTH = 2.0    # along the axis, as long, lower than the bridge
# A pocket under the lowest line, longer than the bridge and narrower than
# the fin, so no tine rests in it: as long, as wide and as deep, in mm.
POCKET_SIZE = (12.0, 0.6, 1.5)

# Thin horizontal slices through the fin, to measure it layer by layer.
SLICE_SIZE = 1000.0
SLICE_HEIGHT = 0.01
SLICE_LOW = 0.1


def shape_regression(cube, face):
    """Fixed measurements of the reference fin, so a change in shape shows up."""
    result = geometry.build(cube, face, FinParams())
    fin = result.fins
    expect(len(fin.Solids) == 1 and fin.isValid(), "the fin is one valid solid")
    gap = min(body.distToShape(cube)[0] for body in result.bodies)
    expect(abs(gap - d.GAP) < d.TOLERANCE, "fin and foot keep the gap of %.2f mm" % d.GAP)

    foot_top = d.FOOT_THICKNESS
    inner = []
    for z in (SLICE_LOW, foot_top / 2, foot_top - SLICE_LOW):
        layer = fin.common(Part.makeBox(SLICE_SIZE, SLICE_SIZE, SLICE_HEIGHT,
                                        App.Vector(-SLICE_SIZE / 2, -SLICE_SIZE / 2, z)))
        inner.append(layer.BoundBox.XMax)
    expect(max(inner) - min(inner) < d.TOLERANCE, "the inner end of the foot is vertical, no tip below it")

    above = fin.common(Part.makeBox(SLICE_SIZE, SLICE_SIZE, SLICE_HEIGHT,
                                    App.Vector(-SLICE_SIZE / 2, -SLICE_SIZE / 2, foot_top + SLICE_LOW)))
    foot = fin.common(Part.makeBox(SLICE_SIZE, SLICE_SIZE, SLICE_HEIGHT,
                                   App.Vector(-SLICE_SIZE / 2, -SLICE_SIZE / 2, SLICE_LOW)))
    expect(abs(foot.BoundBox.XMin - above.BoundBox.XMin) < d.TOLERANCE,
           "the foot ends at the straight outer edge of the fin")
    length = foot.BoundBox.XLength
    width = foot.BoundBox.YLength
    expect(abs(width - length * d.FOOT_WIDTH_RATIO) < d.TOLERANCE,
           "the foot is %.0f %% as wide as long (%.2f x %.2f mm)" % (d.FOOT_WIDTH_RATIO * 100, length, width))


def check_stand():
    """Any edge with one of its faces: the face is laid down first, then the part stands on the edge."""
    box = Part.makeBox(30, 10, 10)
    top = [e for e in box.Edges if e.BoundBox.ZMin > 10 - d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]
    front = [f for f in box.Faces if f.BoundBox.YMax < d.TOLERANCE][0]
    upper = [f for f in box.Faces if f.BoundBox.ZMin > 10 - d.TOLERANCE][0]
    # A top edge alone: its two faces meet at a right angle, so it stands at 45 degrees.
    cornered = moved(box, orient.stand(box, top, orient.RIGHT_ANGLE_TILT))
    lowest = [e for e in cornered.Edges if abs(e.Length - 30) < d.TOLERANCE and e.BoundBox.ZMax < d.TOLERANCE]
    expect(abs(cornered.BoundBox.ZMin) < d.TOLERANCE and len(lowest) == 1 and len(leaning_at(cornered, 45)) == 2,
           "a top edge alone stands the box on it, both faces at 45 degrees")
    try:
        orient.stand(box, top, ODD_TILT)
    except orient.OrientError as error:
        expect("45" in str(error), "a top edge alone is refused at another angle: %s" % error)
    else:
        raise AssertionError("a top edge alone was accepted at another angle")
    chamfered = box.makeChamfer(EDGE_ROUND, [top])
    slanted = [e for e in chamfered.Edges if e.BoundBox.YMax < d.TOLERANCE
               and abs(e.BoundBox.ZMin - (10 - EDGE_ROUND)) < d.TOLERANCE and e.BoundBox.ZLength < d.TOLERANCE][0]
    try:
        orient.stand(chamfered, slanted, orient.RIGHT_ANGLE_TILT)
    except orient.OrientError as error:
        expect("not lie on the bed" in str(error), "an edge alone between slanted faces is refused: %s" % error)
    else:
        raise AssertionError("an edge alone between faces not at a right angle was accepted")

    # A vertical edge alone: the two side faces meet square, the edge comes to lie on the bed.
    vertical = [e for e in box.Edges if e.BoundBox.XMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]
    upended = moved(box, orient.stand(box, vertical, orient.RIGHT_ANGLE_TILT))
    on_it = [e for e in upended.Edges if abs(e.Length - 10) < d.TOLERANCE and e.BoundBox.ZMax < d.TOLERANCE]
    expect(abs(upended.BoundBox.ZMin) < d.TOLERANCE and on_it and len(leaning_at(upended, 45)) == 2,
           "a vertical edge alone stands the box on it, both side faces at 45 degrees")

    # The inner corner of an L profile: square, but hollow, so nothing rests on it.
    profile = box.cut(Part.makeBox(20, 10, 5, App.Vector(10, 0, 5)))
    hollow = [e for e in profile.Edges if abs(e.BoundBox.XMin - 10) < d.TOLERANCE
              and abs(e.BoundBox.XMax - 10) < d.TOLERANCE and abs(e.BoundBox.ZMax - 5) < d.TOLERANCE
              and e.BoundBox.YLength > d.TOLERANCE][0]
    try:
        orient.stand(profile, hollow, orient.RIGHT_ANGLE_TILT)
    except orient.OrientError as error:
        expect("cannot rest" in str(error), "the edge of an inner corner alone is refused: %s" % error)
    else:
        raise AssertionError("the edge of an inner corner was accepted")

    # A side leaning slightly out of square, as on a solid from a mesh.
    for off, accepted in ((d.RIGHT_ANGLE_TOLERANCE / 2, True), (d.RIGHT_ANGLE_TOLERANCE * 2, False)):
        reach = 10 * math.tan(math.radians(off))
        outline = Part.makePolygon([App.Vector(0, 0, 0), App.Vector(10, 0, 0), App.Vector(10 + reach, 0, 10),
                                    App.Vector(0, 0, 10), App.Vector(0, 0, 0)])
        skewed = Part.Face(outline).extrude(App.Vector(0, 30, 0))
        ridge = [e for e in skewed.Edges if e.BoundBox.ZMin > 10 - d.TOLERANCE
                 and e.BoundBox.XMin > 10 - d.TOLERANCE][0]
        try:
            orient.stand(skewed, ridge, orient.RIGHT_ANGLE_TILT)
            taken = True
        except orient.OrientError:
            taken = False
        expect(taken == accepted, "an edge %.2f degrees out of square alone is %s"
               % (off, "taken" if accepted else "refused"))

    # The view looks along the line the part stands on.
    along_x = App.Vector(1, 0, 0)
    alone_change = orient.stand(box, top, orient.RIGHT_ANGLE_TILT)
    expect(orient.side_direction(alone_change, top).getAngle(along_x) < d.TOLERANCE,
           "the side view looks along the edge the box stands on")
    upper_and_front = (upper, front)
    expect(orient.side_direction(orient.rest_between(box, *upper_and_front), faces=upper_and_front)
           .getAngle(along_x) < d.TOLERANCE, "the side view looks along what joins two faces")
    bottom_face = [f for f in box.Faces if f.BoundBox.ZMax < d.TOLERANCE][0]
    expect(orient.side_direction(orient.lay_flat(box, bottom_face)) is None,
           "a face already on the bed gives no side view")

    for face, name in ((front, "the side face"), (upper, "the upper face")):
        stood = box.copy()
        stood.Placement = orient.stand(box, top, d.TILT_ANGLE, face).multiply(stood.Placement)
        expect(abs(stood.BoundBox.ZMin) < d.TOLERANCE, "with %s the part rests on the bed" % name)
        moved_top = [e for e in stood.Edges if abs(e.Length - 30) < d.TOLERANCE
                     and e.BoundBox.ZMax < d.TOLERANCE]
        expect(len(moved_top) == 1, "with %s the part stands on the chosen edge" % name)
        leaning = [f for f in stood.Faces if abs(f.normalAt(0, 0).z + math.sqrt(0.5)) < 1e-6]
        expect(len(leaning) == 2, "with %s two faces lean over the bed at 45 degrees" % name)

    bottom = [f for f in box.Faces if f.BoundBox.ZMax < d.TOLERANCE][0]
    on_bed = [e for e in bottom.Edges if e.BoundBox.YMax < d.TOLERANCE][0]
    alone = orient.stand(box, on_bed, d.TILT_ANGLE)
    with_face = orient.stand(box, on_bed, d.TILT_ANGLE, bottom)
    expect(alone.isSame(with_face, d.TOLERANCE), "a face already on the bed changes nothing")

    side = [f for f in box.Faces if f.BoundBox.XMax < d.TOLERANCE][0]
    try:
        orient.stand(box, top, d.TILT_ANGLE, side)
    except orient.OrientError as error:
        expect("not an edge" in str(error), "an edge of another face is refused: %s" % error)
    else:
        raise AssertionError("an edge of another face was accepted")

    # An L profile cannot rest on the inner face of its notch.
    notched = box.cut(Part.makeBox(20, 10, 5, App.Vector(10, 0, 5)))
    inner = [f for f in notched.Faces if abs(f.BoundBox.ZMin - 5) < d.TOLERANCE
             and f.BoundBox.ZLength < d.TOLERANCE][0]
    try:
        orient.lay_flat(notched, inner)
    except orient.OrientError as error:
        expect("cannot rest" in str(error), "a face the part cannot rest on is refused: %s" % error)
    else:
        raise AssertionError("a face inside a notch was laid onto the bed")


def reach_behind(result, frame):
    """How far the tines reach behind the plane of the face."""
    return max(frame.s_face(v.Point.z) - v.Point.dot(frame.out) for t in result.tines for v in t.Vertexes)


def tine_lengths(result, frame):
    """Length of each tine across the gap, measured horizontally."""
    lengths = []
    for tine in result.tines:
        ss = [v.Point.dot(frame.out) for v in tine.Vertexes]
        lengths.append(max(ss) - min(ss))
    return lengths


def check_corner_tines(part, face, name):
    """Corner tines lie whole on the face, end on it and are all equally long."""
    result = geometry.build(part, face, FinParams(placement=d.PLACEMENT_CORNERS))
    frame = face_frame.frame_of(part, face)
    expect(reach_behind(result, frame) < d.TOLERANCE, "%s: no corner tine reaches past the face" % name)
    lengths = tine_lengths(result, frame)
    expect(max(lengths) - min(lengths) < d.TOLERANCE,
           "%s: all corner tines are equally long (%.3f to %.3f mm)" % (name, min(lengths), max(lengths)))
    return result, frame


def check_corners(cube, face):
    """Two fins on the face ends: each tine lies whole on the face and ends flush with its end."""
    result, frame = check_corner_tines(cube, face, "chamfered cube")
    expect(len(result.fins.Solids) == 2, "corner placement gives two fins")
    ts = [v.Point.dot(frame.along) for tine in result.tines for v in tine.Vertexes]
    expect(abs(min(ts) - frame.along_min) < d.TOLERANCE and abs(max(ts) - frame.along_max) < d.TOLERANCE,
           "the outer tines end flush with both ends of the face")
    reach = (result.thickness - FinParams().tine_width) / 2
    ends = sorted(result.positions)
    expect(abs(ends[0] - (frame.along_min - reach)) < d.TOLERANCE,
           "the corner fin reaches %.2f mm past the end of the face" % reach)

    sharp = Part.makeBox(30, 20, 20)
    edge = [e for e in sharp.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]
    sharp.Placement = orient.tilt(sharp, edge, d.TILT_ANGLE).multiply(sharp.Placement)
    leaning = [f for f in sharp.Faces if f.normalAt(0, 0).z < -d.TOLERANCE][0]
    check_corner_tines(sharp, leaning, "sharp box")

    try:
        geometry.build(cube, face, FinParams(placement=d.PLACEMENT_CORNERS, fin_thickness=30.0))
    except face_frame.FinError as error:
        expect("too short" in str(error) or "narrower" in str(error),
               "corner fins that would collide are refused: %s" % error)
    else:
        raise AssertionError("colliding corner fins were accepted")


def solid_from_polygons(polygons):
    return Part.Solid(Part.Shell([Part.Face(Part.makePolygon(p + p[:1])) for p in polygons]))


def pyramid(height, apex_down=False):
    """Square base of PYRAMID_BASE, apex above its centre, or below with apex_down."""
    half = PYRAMID_BASE / 2
    base = [V(-half, -half, 0), V(half, -half, 0), V(half, half, 0), V(-half, half, 0)]
    apex = V(0, 0, -height if apex_down else height)
    sides = [[base[i], base[(i + 1) % 4], apex] for i in range(4)]
    shape = solid_from_polygons([base] + sides)
    shape.translate(V(0, 0, -shape.BoundBox.ZMin))
    return shape


def overhanging(shape, supported=()):
    """Numbers of the faces of `shape` overhanging by the built-in limits, critical or not printable."""
    return [number for number, _ in overhang.rated(shape, supported, limits.Limits())]


def apex_down(side_deg):
    """A pyramid standing on its apex, its sides `side_deg` from the bed."""
    return pyramid(PYRAMID_BASE / 2 * math.tan(math.radians(side_deg)), apex_down=True)


def check_limits():
    """The limits of the checks: validated, saved and read back; the levels
    of overhanging faces they rate."""
    limits.Limits().validate()
    limits.Limits(overhang_critical=40.0, overhang_unprintable=40.0).validate()
    limits.Limits(overhang_unprintable=0.0, overhang_min_area=0.0, tipping_angle=0.0).validate()
    limits.Limits(bridge_critical=0.0, bridge_unprintable=0.0).validate()
    rating = limits.Limits()
    expect([rating.bridge_level(span) for span in (rating.bridge_critical, rating.bridge_critical + 1,
                                                    rating.bridge_unprintable, rating.bridge_unprintable + 1)]
           == [limits.GOOD, limits.CRITICAL, limits.CRITICAL, limits.UNPRINTABLE],
           "a span at a limit is the level below it, past it the level above")
    bad = (dict(overhang_critical=-1.0), dict(overhang_critical=91.0), dict(overhang_unprintable=50.0),
           dict(tipping_angle=-0.1), dict(tipping_angle=91.0), dict(overhang_min_area=-1.0),
           dict(tipping_angle=float("nan")),
           dict(overhang_critical=float("inf")), dict(bridge_critical=-1.0),
           dict(bridge_critical=12.0, bridge_unprintable=10.0))
    for values in bad:
        try:
            limits.Limits(**values).validate()
            expect(False, "limits %s are refused" % values)
        except limits.LimitError:
            expect(True, "limits %s are refused" % values)

    limits.reset()
    expect(limits.current() == limits.Limits(), "nothing saved: the built-in limits")
    group = App.ParamGet("%s/%s" % (limits.PREFERENCES, limits.LIMITS_GROUP))
    group.SetString(limits.STRICTNESS_KEY, limits.CUSTOM)
    group.SetFloat("tipping_angle", 3.0)
    expect(limits.current() == limits.Limits(tipping_angle=3.0), "one custom limit saved: that, the rest built-in")
    group.SetFloat("overhang_unprintable", 80.0)
    expect(limits.current() == limits.Limits(), "custom limits that do not fit together: the built-in ones")
    group.SetString(limits.STRICTNESS_KEY, limits.STRICT)
    expect(limits.current() == limits.STRICTNESS[limits.STRICT], "strict saved: its limits, the values beside ignored")
    group.SetString(limits.STRICTNESS_KEY, "lenient")
    expect(limits.current() == limits.Limits(), "a strictness no longer known: the built-in limits")
    limits.save(limits.STRICTNESS[limits.STRICT])
    expect(group.GetString(limits.STRICTNESS_KEY) == limits.STRICT and not group.GetFloats(),
           "the limits of a strictness are saved by its name alone, so they follow the version")
    own = limits.Limits(overhang_critical=50.0, overhang_unprintable=35.0, overhang_min_area=2.0, tipping_angle=1.0)
    limits.save(own)
    expect(limits.current() == own and group.GetString(limits.STRICTNESS_KEY) == limits.CUSTOM,
           "custom limits are saved as values and read back")
    try:
        limits.save(limits.Limits(overhang_unprintable=60.0))
        expect(False, "invalid limits are not saved")
    except limits.LimitError:
        expect(limits.current() == own, "invalid limits are not saved, the saved ones stay")
    limits.reset()
    expect(limits.current() == limits.Limits(), "reset: the built-in limits")
    for name, preset in limits.STRICTNESS.items():
        preset.validate()
        expect(limits.strictness_of(preset) == name, "the limits of %s are that strictness" % name)
    expect(limits.strictness_of(limits.Limits()) == limits.NORMAL, "the built-in limits are normal")
    expect(limits.strictness_of(own) == limits.CUSTOM, "limits set otherwise are custom")
    strict = limits.STRICTNESS[limits.STRICT]
    expect(strict.overhang_unprintable == strict.overhang_critical
           and strict.tipping_angle > limits.Limits().tipping_angle,
           "strict leaves no critical overhangs and asks a larger tipping angle")

    rating = limits.Limits()
    expect(overhang.rated(apex_down(SIDE_STEEP), (), rating) == [],
           "sides steeper than the critical limit are not rated")
    for side, level in ((SIDE_CRITICAL, limits.CRITICAL), (SIDE_UNPRINTABLE, limits.UNPRINTABLE),
                        (rating.overhang_unprintable, limits.CRITICAL)):
        found = overhang.rated(apex_down(side), (), rating)
        expect(len(found) == 4 and all(rated == level for _, rated in found),
               "sides %.0f degrees from the bed are %s: %s" % (side, level, found))
    expect(overhang.rated(apex_down(rating.overhang_critical), (), rating) == [],
           "sides at exactly the critical limit are not rated")
    equal = limits.Limits(overhang_critical=SIDE_STEEP, overhang_unprintable=SIDE_STEEP)
    found = overhang.rated(apex_down(SIDE_CRITICAL), (), equal)
    expect(found and all(level == limits.UNPRINTABLE for _, level in found),
           "both limits equal: not printable, never critical")
    nothing_red = limits.Limits(overhang_unprintable=0.0)
    found = overhang.rated(apex_down(SIDE_UNPRINTABLE), (), nothing_red)
    expect(found and all(level == limits.CRITICAL for _, level in found),
           "an unprintable limit of 0 degrees: critical at most")


def piers(gap, depth=PIER[1], slab_depth=None, height=PIER[2]):
    """A slab on two piers `gap` apart, `depth` deep and `height` high, the
    slab across the gap, as deep as the piers or `slab_depth`, reaching past
    them at the back."""
    width = PIER[0]
    first = Part.makeBox(width, depth, height)
    second = Part.makeBox(width, depth, height, V(width + gap, 0, 0))
    slab = Part.makeBox(2 * width + gap, slab_depth or depth, SLAB, V(0, 0, height))
    return first.fuse([second, slab]).removeSplitter()


def plate(x0, y0, x1, y1, hole=None):
    """A face in the plane of the bed from (x0, y0) to (x1, y1), with `hole`,
    four numbers the same way, cut out of it."""
    face = Part.makePlane(x1 - x0, y1 - y0, V(x0, y0, 0))
    if hole is None:
        return face
    hx0, hy0, hx1, hy1 = hole
    return face.cut(Part.makePlane(hx1 - hx0, hy1 - hy0, V(hx0, hy0, 0))).Faces[0]


def check_bridge_lines():
    """The lines a bridge lays across a free region, by arithmetic on its
    outline: every kind of outline, point and line the tables of
    bridge._outline(), _supports(), _inside(), _resting(), _pieces(),
    _anchored() and _covered() name."""
    bead, side, half = d.BEAD_WIDTH, LINES_SIDE, LINES_SIDE / 2
    lo, hi = LINES_HOLE[0], LINES_HOLE[2]
    slack = d.TOLERANCE + bridging._deflection(bead)

    def diamond_of(x0, y0, x1, y1):
        """A square stood on a corner, its corners in the middles of the sides of the box given."""
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        corners = [V(x0, my, 0), V(mx, y0, 0), V(x1, my, 0), V(mx, y1, 0)]
        return Part.Face(Part.makePolygon(corners + corners[:1]))

    square = bridging._outline(plate(0, 0, side, side), bead)
    holed = bridging._outline(plate(0, 0, side, side, LINES_HOLE), bead)
    diamond = bridging._outline(diamond_of(0, 0, side, side), bead)
    tipped = bridging._outline(plate(0, 0, side, side).cut(diamond_of(*LINES_HOLE)).Faces[0], bead)
    disc = Part.Face(Part.Wire(Part.makeCircle(half, V(half, half, 0))))
    round_outline = bridging._outline(disc, bead)
    off = numpy.abs(numpy.hypot(*((round_outline[0] + round_outline[1]) / 2 - half).T) - half).max()
    turns = [2 * math.pi * k / LINES_FACETS for k in range(LINES_FACETS + 1)]
    faceted = Part.Face(Part.makePolygon(
        [V(half + half * math.cos(turn), half + half * math.sin(turn), 0) for turn in turns]))
    expect(len(square[0]) == 4 and len(holed[0]) == 8 and len(bridging._outline(faceted, bead)[0]) == LINES_FACETS
           and (square[0][0] == square[1][-1]).all() and (round_outline[0][0] == round_outline[1][-1]).all()
           and 0 < off <= bridging._deflection(bead) + d.TOLERANCE,
           "the outline of a face is its corners, its holes with it, those of a face of many flat sides as "
           "many, each ring closed on its first point; a round one in pieces no farther off than the "
           "deflection: %.4f mm" % off)
    opened = Part.Wire(Part.makePolygon([V(0, 0, 0), V(side, 0, 0), V(side, side, 0)]))
    unclosed = bridging._outline(type("OpenRing", (), {"Wires": [opened]})(), bead)
    expect(len(unclosed[0]) == 3 and (unclosed[1][-1] == unclosed[0][0]).all()
           and bridging._outline(Part.Shape(), bead) is None,
           "a ring the kernel gives open is closed by a piece from its last point to its first; a face "
           "without a ring has no outline")
    carrying = bridging._supports([plate(0, 0, side, side), Part.Shape(), plate(side, 0, 2 * side, side)], bead)
    lowest = [tuple(float(value) for value in box[0]) for _, box in carrying]
    expect(lowest == [(0.0, 0.0), (float(side), 0.0)] and bridging._supports([], bead) == [],
           "a face no outline can be taken of is left out of the supports, the faces beside it are kept, in "
           "their order: %s" % lowest)

    def inside(outline, *points, slack=d.TOLERANCE):
        return list(bridging._inside(numpy.array(points, dtype=float), outline, slack))

    beside = LINES_BESIDE
    expect(inside(square, (half, half), (side + beside, half), (side + d.TOLERANCE / 2, half), (-beside, 0),
                  (-beside, side)) == [True, False, True, False, False],
           "a point lies in a face inside its outline or within the slack of it, not outside, nor on the line "
           "of a side beside it")
    expect(inside(holed, ((lo + hi) / 2, (lo + hi) / 2), (lo / 2, half), (lo + d.TOLERANCE / 2, half))
           == [False, True, True],
           "a point in a hole of a face lies in no face, one beside the hole or on its rim does")
    expect(inside(diamond, (-beside, half), (half, half), (half / 2, half)) == [False, True, True],
           "a ray through a corner of the outline counts the corner once, one touching it not at all")
    # Between two points of the round outline its straight piece lies inside
    # the circle: a point the tolerance outside the circle there is farther
    # from the piece than the tolerance, and rests only with the slack for it.
    between = (round_outline[0][0] + round_outline[1][0]) / 2 - half
    outward = between / numpy.hypot(*between)
    on_rim = tuple(half + outward * (half + d.TOLERANCE))
    inner, off_rim = tuple(half + outward * (half - bead)), tuple(half + outward * (half + bead))
    expect(inside(round_outline, on_rim, inner, off_rim, slack=slack) == [True, True, False]
           and inside(round_outline, on_rim) == [False],
           "a point the tolerance outside a round outline, between two of its points, rests on it with the "
           "slack for its straight pieces and not without; one a bead outside does not")
    resting = list(bridging._resting(numpy.array([(half, half), (side + half, half), (-beside, half)]), carrying,
                                     slack))
    expect(resting == [True, True, False]
           and not bridging._resting(numpy.array([(half, half)]), [], slack).any(),
           "a point rests where it lies in any of the supports, and on nothing without one")

    def pieces(outline, degrees):
        found, _, _ = bridging._pieces(outline, (half, half), half + LINES_PAST, LINES_SPACING, degrees)
        return [tuple(round(float(value), LINES_DIGITS) for value in row) for row in found]

    for degrees in (0, 90):
        found = pieces(square, degrees)
        inner = [piece for piece in found if 0 < abs(piece[0]) < side]
        expect(len(inner) == int(side) - 1 and all(piece[1:] == (0.0, float(side)) for piece in found)
               and len(found) - len(inner) <= 2,
               "lines across a square a millimetre apart at %d degrees: one piece each from side to side; a "
               "line along a side has one or none: %s" % (degrees, found))
    through = [piece for piece in pieces(diamond, 0) if piece[0] == half]
    touching = [piece for piece in pieces(diamond, 0) if piece[0] in (0.0, float(side)) and piece[2] - piece[1] > 0]
    expect(through == [(half, 0.0, float(side))] and not touching,
           "a line through two corners of a diamond is one piece from corner to corner; one touching a "
           "corner only has no piece of any length: %s" % pieces(diamond, 0))
    past = [piece for piece in pieces(holed, 0) if piece[0] == half]
    expect(past == [(half, 0.0, float(lo)), (half, float(hi), float(side))],
           "a line across a hole stops at it and goes on past it: %s" % past)
    at_tips = [piece for piece in pieces(tipped, 0) if piece[0] in (float(lo), float(hi))]
    expect(at_tips == [(float(lo), 0.0, float(side)), (float(hi), 0.0, float(side))],
           "a line touching the tip of a hole, from below or from above, is one piece past the tip: %s" % at_tips)

    gap = (PIER[0], 0, PIER[0] + GAP_CRITICAL, PIER[1])
    region = bridging._outline(plate(*gap), bead)
    left, right = (0, 0, PIER[0], PIER[1]), (PIER[0] + GAP_CRITICAL, 0, 2 * PIER[0] + GAP_CRITICAL, PIER[1])
    centre, reach = (PIER[0] + GAP_CRITICAL / 2, PIER[1] / 2), GAP_CRITICAL

    def anchored(supports, degrees=0, across=region):
        return bridging._anchored(across, bridging._supports(supports, bead), bead, centre, reach, bead, degrees)

    held = anchored([plate(*left), plate(*right)])
    expect(held is not None and abs(held[1] - GAP_CRITICAL) < d.TOLERANCE and held[3].shape[1:] == (2, 2)
           and anchored([plate(*left), plate(*right)], 90) is None and anchored([plate(*left)]) is None
           and anchored([]) is None,
           "lines across a gap rest on a support at each end, on two of them; along the gap, with one "
           "support or with none, nothing is anchored")
    open_left = (PIER[0] - bead, 0, PIER[0], PIER[1])
    expect(anchored([plate(*left, hole=open_left), plate(*right)]) is None,
           "ends that come to lie over a hole of a support rest on nothing")
    short = bridging._outline(plate(PIER[0], 0, PIER[0] + bead / 2, PIER[1]), bead)
    expect(anchored([plate(*left), plate(*right)], across=short) is None,
           "pieces no longer than a bead are left out")

    lines = numpy.array([[(0.0, 0.0), (float(side), 0.0)]])
    expect(bridging._covered(plate(0, -bead, side, bead), lines, bead)
           and not bridging._covered(plate(0, -bead, side, 2 * bead + 1), lines, bead)
           and not bridging._covered(plate(0, -bead, side, bead), lines[:0], bead),
           "a face is covered where all of it lies within a spacing of a line, not where it reaches farther, "
           "nor without a line")

    def table(post=0.0):
        """A disc on a ring wall, with a post in its middle `post` in radius."""
        wall = Part.makeCylinder(ROUND_TABLE, PIER[2]).cut(Part.makeCylinder(ROUND_TABLE - PIER[0], PIER[2]))
        parts = [Part.makeCylinder(ROUND_TABLE, SLAB, V(0, 0, PIER[2]))]
        if post:
            parts.append(Part.makeCylinder(post, PIER[2]))
        return wall.fuse(parts).removeSplitter()

    def spans_of(shape):
        found = find_bridges(shape, d.FIRST_LAYER_HEIGHT, d.LAYER_HEIGHT, bead, limits.Limits())
        return [bridged.span for bridged in found]

    across = 2 * (ROUND_TABLE - PIER[0])
    plain, posted = spans_of(table()), spans_of(table(ROUND_POST))
    expect(len(plain) == 1 and abs(plain[0] - across) < SPAN_TOLERANCE,
           "a disc on a ring wall spans the whole hole, the line through the seam of its round outline "
           "kept: %s" % plain)
    # With a post in the middle the longest line is the first that passes
    # beside the post: the lines lie as they are laid across the box of the
    # hole (bridge._laying()), and a line at the post ends on it.
    reach, spacing = bridging._laying(math.hypot(across, across), bead)
    past_post = min(offset for offset in bridging._offsets(reach, spacing) if offset > ROUND_POST)
    chord = 2 * math.sqrt((across / 2) ** 2 - past_post ** 2)
    expect(len(posted) == 1 and abs(posted[0] - chord) < SPAN_TOLERANCE,
           "the same with a post in its middle spans beside the post, the chord of the first line past it, "
           "%.2f mm: %s" % (chord, posted))
    on_facets = bridging._outline(faceted, bead)
    middle = [piece for piece in pieces(on_facets, 0) if piece[0] == half]
    wide = bridging._supports([plate(-side, -side, 2 * side, 2 * side, (0, 0, side, side))], bead)
    held = bridging._anchored(on_facets, wide, bead, (half, half), half + LINES_PAST, LINES_SPACING, 0)
    expect(middle == [(half, 0.0, float(side))] and held is not None and abs(held[1] - side) < SPAN_TOLERANCE,
           "across a round outline of %d flat sides the line through the middle is one piece from rim to "
           "rim, and the lines rest on the plate around it: %s" % (LINES_FACETS, middle))


def check_bridge_faces():
    """The faces of a part lying over a free region, their points turned away by the box around
    the region before the kernel measures how far they are from it."""
    first, layer, bead = d.FIRST_LAYER_HEIGHT, d.LAYER_HEIGHT, d.BEAD_WIDTH
    side, near, far = 10.0, bead / 4, bead
    region = plate(0, 0, side, side)
    corners = {7: [(side / 2, side / 2)], 3: [(OUT_OF_REACH, 0)], 5: [(OUT_OF_REACH, 0), (side + near, side / 2)],
               4: [(side + far, side / 2)], 9: [(side + bead / 2, 0)]}
    expect(bridging._over(region, corners, bead) == [7, 5, 9] and bridging._over(region, {}, bead) == [],
           "the faces with a point within half a bead of a region lie over it, one right at half a bead "
           "among them, in the order given; no faces, none: %s" % bridging._over(region, corners, bead))
    # A point in the box around a region, yet far from the region: in the hole of a ring.
    ring = plate(0, 0, side, side, hole=(side / 4, side / 4, 3 * side / 4, 3 * side / 4))
    within = {1: [(side / 2, side / 2)], 2: [(side / 2, side / 2), (side / 8, side / 8)]}
    expect(bridging._over(ring, within, bead) == [2],
           "a face with its only point in the hole of a ring does not lie over the ring, one with a point "
           "on the ring as well does: %s" % bridging._over(ring, within, bead))

    class Region:
        """A region standing in for one of the kernel: its box, or none to be had, and what it
        is asked to measure, raising where told."""

        def __init__(self, box=None, raising=False):
            self.box, self.raising, self.asked = box, raising, []

        def optimalBoundingBox(self, mesh, tolerance):
            self.took = (mesh, tolerance)
            if self.box is None:
                raise Part.OCCError("no box")
            return self.box

        def distToShape(self, vertex):
            self.asked.append((vertex.Point.x, vertex.Point.y))
            if self.raising:
                raise Part.OCCError("no distance")
            return (0.0,)

    box = App.BoundBox(0, 0, 0, side, side, 0)
    edge = side + bead / 2 + d.TOLERANCE
    boxed = Region(box)
    expect(bridging._over(boxed, {1: [(edge, 0), (0, -bead / 2 - d.TOLERANCE)], 2: [(edge + BESIDE, 0)],
                                  3: [(0, edge + BESIDE)]}, bead) == [1]
           and boxed.asked == [(edge, 0)] and boxed.took == (False, False),
           "a point right on the edge of the box around a region, grown by half a bead and the tolerance, "
           "is measured, one beside it is not; the box is taken without a mesh: %s" % boxed.asked)
    unboxed = Region()
    expect(bridging._over(unboxed, {1: [(OUT_OF_REACH, 0)], 2: [(0, OUT_OF_REACH)]}, bead) == [1, 2]
           and len(unboxed.asked) == 2,
           "of a region the kernel can tell no box of, every point is measured")
    failing = Region(box, raising=True)
    expect(bridging._over(failing, {1: [(side / 2, side / 2)], 2: [(OUT_OF_REACH, 0)]}, bead) == []
           and failing.asked == [(side / 2, side / 2)],
           "the kernel raising on a point of a face, the face does not lie over the region; a point turned "
           "away by the box is not measured and cannot raise")
    disc = Part.Face(Part.Wire(Part.makeCircle(side)))
    expect(sorted(bridging._corners(region)) == sorted([(0, 0), (side, 0), (0, side), (side, side),
                                                        (side / 2, side / 2)]),
           "the corners of a face and its middle are its points, seen from above: %s" % bridging._corners(region))
    expect(len(bridging._corners(disc)) == 2 and bridging._corners(disc)[-1] != bridging._corners(disc)[0],
           "a disc has the one corner of its edge and its middle: %s" % bridging._corners(disc))

    # Slabs on piers side by side: the bridges found with the boxes are those found measuring every point.
    pitch = 2 * PIER[0] + GAP_CRITICAL + PIER[0]
    row = Part.makeCompound([piers(GAP_CRITICAL).translated(V(step * pitch, 0, 0)) for step in range(COMB_TEETH)])

    def told(found):
        return [(bridge.faces, bridge.covered, round(bridge.span, CUTS_DIGITS), bridge.level,
                 round(bridge.region.Area, CUTS_DIGITS)) for bridge in found]

    found = find_bridges(row, first, layer, bead, limits.Limits())
    real_box = bridging._box
    bridging._box = lambda region: None
    try:
        measured = find_bridges(row, first, layer, bead, limits.Limits())
    finally:
        bridging._box = real_box
    expect(len(found) == COMB_TEETH and told(found) == told(measured)
           and all(len(bridge.faces) == 1 for bridge in found),
           "%d slabs on piers side by side: each bridge lies under its own face alone, found with the boxes "
           "as measuring every point, in the same order: %s" % (COMB_TEETH, told(found)))
    # A region under no face that counts, as under one carried by fins: its lines are not laid.
    undersides = [face for face in row.Faces if face.BoundBox.ZLength < d.TOLERANCE
                  and abs(face.BoundBox.ZMin - PIER[2]) < d.TOLERANCE]
    carried = [face for face in undersides if face.BoundBox.XMax < pitch]
    laid = []
    real_span = bridging._span
    bridging._span = lambda *args: laid.append(args) or real_span(*args)
    try:
        left = find_bridges(row, first, layer, bead, limits.Limits(), carried)
    finally:
        bridging._span = real_span
    expect(len(carried) == 1 and len(left) == COMB_TEETH - 1 and len(laid) == COMB_TEETH - 1,
           "the face under one of %d slabs carried by fins: the lines of the region under it are not laid, "
           "the others are bridged: %d bridges, lines laid %d times" % (COMB_TEETH, len(left), len(laid)))

    # The supports a line can rest on and the faces a face is cut by, picked by their boxes: the
    # bridges are those found looking at every support and cutting by every face below.
    real_near, real_boxes = bridging._near, bridging._boxes
    bridging._near = lambda supports, outline, bead: supports
    bridging._boxes = lambda faces: numpy.array([bridging.EVERYWHERE] * len(faces), dtype=float).reshape(-1, 4)
    try:
        by_all = find_bridges(row, first, layer, bead, limits.Limits())
    finally:
        bridging._near, bridging._boxes = real_near, real_boxes
    cut_by = []
    real_free = bridging._free

    def free(here, below, here_boxes, below_boxes):
        cut_by.extend(int(((below_boxes[:, 0] <= box[1]) & (box[0] <= below_boxes[:, 1])).sum())
                      for box in here_boxes)
        return real_free(here, below, here_boxes, below_boxes)

    bridging._free = free
    try:
        find_bridges(row, first, layer, bead, limits.Limits())
    finally:
        bridging._free = real_free
    expect(told(found) == told(by_all) and cut_by == [2] * COMB_TEETH,
           "%d slabs on piers side by side: the bridges found with the supports and the faces below picked "
           "by their boxes are those found with all of them, in the same order; each slab is cut by its own "
           "two piers alone: %s" % (COMB_TEETH, cut_by))

    # A support whose box only touches the box of a region, grown by half a bead and the slack, is
    # kept; one beside that is not.
    reach = bead / 2 + bridging._slack(bead)
    outline = bridging._outline(region, bead)
    beside_it = [plate(side + reach, 0, 2 * side, side), plate(side + reach + BESIDE, 0, 2 * side, side),
                 plate(OUT_OF_REACH, 0, OUT_OF_REACH + side, side), plate(-side, -side, 0, 0),
                 plate(0, -side - reach, side, -reach), plate(0, -side - reach - BESIDE, side, -reach - BESIDE)]
    supports = bridging._supports(beside_it, bead)
    kept = [number for each in bridging._near(supports, outline, bead)
            for number, support in enumerate(supports) if support is each]
    expect(kept == [0, 3, 4] and bridging._near([], outline, bead) == []
           and bridging._near(supports[1:3], outline, bead) == [],
           "the supports whose boxes meet or touch the box of a region grown by half a bead and the slack "
           "are kept, in their order, those beside it are not; of no supports, or none near, none: %s" % kept)

    # A face meeting no face below is free whole and not cut; one meeting some is cut by those.
    here = [plate(0, 0, side, side), plate(OUT_OF_REACH, 0, OUT_OF_REACH + side, side),
            plate(2 * side, 0, 3 * side, side), plate(5 * side, 0, 6 * side, side)]
    below = [plate(0, 0, side / 2, side), plate(2 * side, 0, 3 * side, side), plate(6 * side, 0, 7 * side, side)]
    regions = bridging._free(here, below, bridging._boxes(here), bridging._boxes(below))
    expect(len(regions) == 3 and abs(regions[0].Area - side * side / 2) < d.TOLERANCE and regions[1] is here[1]
           and abs(regions[2].Area - side * side) < d.TOLERANCE and regions[2] is not here[3],
           "a face half on one below is free by half, one with no face below near it is given whole as it "
           "is, one a face below only touches is free whole, one resting whole on another has no region: %s"
           % [round(each.Area, CUTS_DIGITS) for each in regions])
    expect(bridging._free([], below, bridging._boxes([]), bridging._boxes(below)) == []
           and bridging._boxes([]).shape == (0, 4),
           "no faces have no boxes and no free region")

    class Face:
        """A face standing in for one of the kernel: its box, or none to be had, and a cut that
        raises or gives what it is cut by."""

        def __init__(self, box=None, raising=False):
            self.box, self.raising, self.cut_by = box, raising, None

        def optimalBoundingBox(self, mesh, tolerance):
            if self.box is None:
                raise Part.OCCError("no box")
            return self.box

        def cut(self, others):
            if self.raising:
                raise Part.OCCError("no cut")
            self.cut_by = len(others.Faces)
            return Part.makeCompound([])

    unboxed, away = Face(), Face(App.BoundBox(OUT_OF_REACH, 0, 0, OUT_OF_REACH + side, side, 0), raising=True)
    faces = [unboxed, away]
    regions = bridging._free(faces, below, bridging._boxes(faces), bridging._boxes(below))
    expect(unboxed.cut_by == len(below) and regions == [away]
           and tuple(bridging._boxes(faces)[0]) == bridging.EVERYWHERE,
           "a face the kernel can tell no box of is cut by every face below; one meeting none below is "
           "not cut, so the kernel cannot raise on it")
    under = [Face(), plate(OUT_OF_REACH, 0, OUT_OF_REACH + side, side)]
    cut = Face(App.BoundBox(0, 0, 0, side, side, 0))
    bridging._free([cut], [plate(0, 0, side, side)] + under[1:], bridging._boxes([cut]),
                   numpy.vstack([bridging._boxes([under[0]]), bridging._boxes(under[1:])]))
    expect(cut.cut_by == 1, "a face below without a box cuts every face: %s" % cut.cut_by)
    raising = Face(App.BoundBox(0, 0, 0, side, side, 0), raising=True)
    faces = [here[1], raising]
    expect(bridging._free(faces, below, bridging._boxes(faces), bridging._boxes(below)) == [],
           "the kernel raising on the cut of one face, the layer has no free region")


def check_bridges():
    """Bridges: where a layer spans a gap between supports, how far, rated."""
    first, layer, bead = d.FIRST_LAYER_HEIGHT, d.LAYER_HEIGHT, d.BEAD_WIDTH
    rating = limits.Limits()

    def found(shape, rate=rating, supported=()):
        return find_bridges(shape, first, layer, bead, rate, supported)

    expect(found(Part.makeBox(30, 10, 10)) == [], "a box lying on the bed has no bridge")
    for gap, level in ((GAP_SHORT, limits.GOOD), (GAP_CRITICAL, limits.CRITICAL), (GAP_FAR, limits.UNPRINTABLE)):
        spans = found(piers(gap))
        expect(len(spans) == 1 and abs(spans[0].span - gap) < SPAN_TOLERANCE and spans[0].level == level,
               "a slab across a %.1f mm gap between piers spans it, %s: %s"
               % (gap, level, [(s.span, s.level) for s in spans]))
    # The underside of the slab right on the middle of a layer, where the
    # layers are cut, within the tolerance of it and beside it.
    middle = overhang.layer_middle(ISLAND_LAYER, first, layer)
    for height in (middle + offset for offset in MIDDLE_OFFSETS):
        spans = found(piers(GAP_CRITICAL, height=height))
        expect(len(spans) == 1 and abs(spans[0].span - GAP_CRITICAL) < SPAN_TOLERANCE,
               "a slab with its underside at %.5f mm, the middle of a layer at %.2f mm, spans the gap: %s"
               % (height, middle, [s.span for s in spans]))
    for first_height, layer_height in LAYERINGS:
        def found_here(shape, starts=None):
            return find_bridges(shape, first_height, layer_height, bead, rating, starts=starts)

        # A ridge hanging from the slab across the whole gap, its sides too
        # steep to overhang, its edge just below the middle of the layer under
        # the slab's: it starts in the layer of the slab and carries nothing.
        below = overhang.layer_middle(ISLAND_LAYER, first_height, layer_height)
        under = below + CLEAR_OF_MIDDLE
        edge, top = below - d.TOLERANCE + BESIDE, under + RIDGE_INTO_SLAB
        centre = PIER[0] + GAP_CRITICAL / 2
        corners = [V(centre - (top - edge) / 2, 0, top), V(centre + (top - edge) / 2, 0, top), V(centre, 0, edge)]
        ridge = Part.Face(Part.makePolygon(corners + corners[:1])).extrude(V(0, PIER[1], 0))
        spans = found_here(piers(GAP_CRITICAL, height=under).fuse(ridge).removeSplitter())
        expect(len(spans) == 1 and abs(spans[0].span - GAP_CRITICAL) < SPAN_TOLERANCE,
               "first layer %.2f mm: a ridge hanging in the gap, starting just below the middle of the layer "
               "under the slab, carries nothing: the slab spans the whole gap: %s"
               % (first_height, [s.span for s in spans]))
        # Steps under the slab, side by side across the gap, each a layer
        # higher than the last and clear of the middles: every layer is cut
        # once, and the layer below the lowest.
        stairs = stairs_under_slab(first_height, layer_height)
        kernel, (cut_at, spans) = kernel_cuts(lambda: cuts_counted(lambda: found_here(stairs)))
        expect(spans and len(cut_at) == COMB_TEETH + 1 and kernel == cuts_due(stairs, cut_at) < len(cut_at),
               "first layer %.2f mm: %d steps under a slab in layers one above the other are bridged, found "
               "with each layer asked for once and the one below the lowest, in a cut of the kernel for each "
               "batch of them and no more: %d "
               "heights, %d cuts, spans %s"
               % (first_height, COMB_TEETH, len(cut_at), kernel, [s.span for s in spans]))
        # A slab whose underside, the ceiling of the gap, starts near a middle,
        # beside a block hanging in the same layer: no lowest point lies on the
        # ceiling, yet what carries that layer is cut lowered for the islands, and
        # the bridges take that cut from the same Starts: the part is meshed once
        # and no height is cut twice.
        near = below - d.TOLERANCE / 2
        hanging = Part.makeBox(ISLAND_PILLAR, ISLAND_DEPTH, ISLAND_UNDER - under,
                               V(ISLAND_SPAN - ISLAND_PILLAR, 0, under))
        beside = bridge(hanging).translated(V(2 * PIER[0] + GAP_CRITICAL + ISLAND_PILLAR, 0, 0))
        both = Part.makeCompound([piers(GAP_CRITICAL, height=near), beside])
        starts = overhang.Starts(both)
        sampled, (meshed, (for_islands, for_bridges)) = calls_counted("facing_down", lambda: calls_counted(
            "_lowest_points", lambda: (
                cuts_counted(lambda: overhang.islands(both, first_height, layer_height, starts)),
                cuts_counted(lambda: found_here(both, starts)))))
        supports = [sorted(z for z in cut_at if abs(z - below) < CLEAR_OF_MIDDLE)
                    for cut_at, _ in (for_islands, for_bridges)]
        over_gap = [found for found in for_bridges[1] if abs(found.span - GAP_CRITICAL) < SPAN_TOLERANCE]
        expect(len(for_islands[1]) == 1 and len(over_gap) == 1 and len(meshed) == 1 and len(sampled) == 1
               and len(supports[0]) == 1 and supports[1] == [] and not set(for_islands[0]) & set(for_bridges[0])
               and abs(supports[0][0] - (below - overhang.SUPPORT_CUT_DROP)) < BESIDE,
               "first layer %.2f mm: a ceiling starting near a middle beside a block hanging in its layer, an "
               "island, the ceiling a bridge across the gap: islands "
               "cut what carries that layer the drop under the middle, the bridges take that cut and cut no "
               "height again, the part "
               "meshed once and its faces sampled once: %s, %d meshes, %d samplings"
               % (first_height, supports, len(meshed), len(sampled)))
    plain = Part.makeBox(*PIER)
    meshed, (cut_at, spans) = calls_counted("_lowest_points", lambda: cuts_counted(lambda: found(plain)))
    expect(spans == [] and not cut_at and not meshed,
           "a box with no face hanging is neither meshed nor cut for bridges")
    deep = found(piers(GAP_CRITICAL, DEEP_SLAB))
    expect(len(deep) == 1 and abs(deep[0].span - GAP_CRITICAL) < SPAN_TOLERANCE,
           "a slab deeper than the gap spans across the gap, not along it: %s" % [s.span for s in deep])
    slab = piers(GAP_CRITICAL)
    expect(found(slab)[0].covered == found(slab)[0].faces, "the bridge covers the underside of the slab whole")
    reaching = found(piers(GAP_CRITICAL, slab_depth=DEEP_SLAB))
    expect(len(reaching) == 1 and reaching[0].faces and not reaching[0].covered,
           "a slab reaching past the piers at the back: the bridge does not cover its underside whole")
    under = slab.Faces[found(slab)[0].faces[0] - 1]
    expect(abs(under.BoundBox.ZMin - PIER[2]) < d.TOLERANCE and under.BoundBox.ZMax - under.BoundBox.ZMin < d.TOLERANCE,
           "the bridge lies under the underside of the slab")
    expect(found(slab, supported=(under,)) == [], "a face carried by fins spans nothing")
    strict = limits.STRICTNESS[limits.STRICT]
    expect(found(slab, strict)[0].level == limits.UNPRINTABLE, "strict: a critical span is not printable")
    width, depth, height = PIER
    arm = Part.makeBox(width, depth, height + SLAB).fuse(
        Part.makeBox(width + GAP_CRITICAL, depth, SLAB, V(0, 0, height))).removeSplitter()
    expect(found(arm) == [], "an arm reaching out at one side is no bridge, it overhangs")
    floating = Part.makeBox(width, width, width, V(0, 0, height))
    expect(found(floating) == [], "a block floating above the bed is no bridge, it is an island")
    expect(found(Part.Shape()) == [], "an empty shape has no bridge said, nothing raised")


# Calls into the kernel that crash FreeCAD on some shapes, in a way no
# exception catches: the 2D offset dies in its medial axis on some outlines.
FRAGILE_CALLS = ("makeOffset2D",)


def check_no_fragile_calls():
    """No module of FinSnap calls into the kernel where it can crash FreeCAD."""
    from freecad.finsnap.paths import PACKAGE
    found = []
    for folder, folders, files in os.walk(PACKAGE):
        folders[:] = [name for name in folders if name != "tests"]
        for name in files:
            if name.endswith(".py"):
                with open(os.path.join(folder, name), encoding="utf-8") as handle:
                    text = handle.read()
                found += ["%s: %s" % (name, call) for call in FRAGILE_CALLS if call in text]
    expect(not found, "no module calls into the kernel where it can crash FreeCAD: %s" % found)


def check_frustum():
    """A truncated pyramid stood on a base edge: fins under every face that leans
    over the bed, a clear refusal for the side faces that lean upward."""
    b, t = FRUSTUM_BASE / 2, FRUSTUM_TOP / 2
    base = [V(-b, -b, 0), V(b, -b, 0), V(b, b, 0), V(-b, b, 0)]
    top = [V(-t, -t, FRUSTUM_HEIGHT), V(t, -t, FRUSTUM_HEIGHT), V(t, t, FRUSTUM_HEIGHT), V(-t, t, FRUSTUM_HEIGHT)]
    shape = solid_from_polygons([base, top[::-1]] + [[base[i], base[(i + 1) % 4], top[(i + 1) % 4], top[i]]
                                                     for i in range(4)])
    edge = [e for e in shape.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < -b + d.TOLERANCE][0]
    shape.Placement = orient.tilt(shape, edge, d.TILT_ANGLE).multiply(shape.Placement)

    leaning, upward = [], []
    for f in shape.Faces:
        u0, u1, v0, v1 = f.ParameterRange
        (leaning if f.normalAt((u0 + u1) / 2, (v0 + v1) / 2).z < -d.MIN_NORMAL_COMPONENT else upward).append(f)
    built = [geometry.build(shape, f, FinParams()) for f in leaning]
    expect(len(built) == 2 and all(r.fins.Solids for r in built),
           "the tilted frustum gets fins under both faces leaning over the bed")
    for f in leaning:
        check_corner_tines(shape, f, "frustum")
    for f in upward:
        try:
            geometry.build(shape, f, FinParams())
        except face_frame.FinError as error:
            expect(face_frame.NOT_OVERHANGING in str(error) or face_frame.HORIZONTAL_FACE in str(error),
                   "a face leaning upward is refused: %s" % error)
        else:
            raise AssertionError("fins were built under a face leaning upward")


def check_loft():
    """A frustum built as a loft has B-spline sides and edges that are still flat and straight."""
    b, t = FRUSTUM_BASE / 2, FRUSTUM_TOP / 2

    def square(half, z):
        return Part.makePolygon([V(-half, -half, z), V(half, -half, z), V(half, half, z), V(-half, half, z),
                                 V(-half, -half, z)])

    loft = Part.makeLoft([square(b, 0), square(t, FRUSTUM_HEIGHT)], True, True)
    side = [f for f in loft.Faces if isinstance(f.Surface, Part.BSplineSurface)][0]
    slanted = [e for e in side.Edges if isinstance(e.Curve, Part.BSplineCurve)][0]
    stood = loft.copy()
    stood.Placement = orient.stand(loft, slanted, d.TILT_ANGLE, side).multiply(stood.Placement)
    expect(abs(stood.BoundBox.ZMin) < d.TOLERANCE, "a loft stands on a slanted B-spline edge of its side")

    cone = Part.makeCone(t, b, FRUSTUM_HEIGHT)
    mantle = [f for f in cone.Faces if f.findPlane() is None][0]
    lying = moved(cone, orient.lay_flat(cone, mantle))
    on_bed = [f for f in lying.Faces if f.findPlane() is None][0]
    expect(abs(lying.BoundBox.ZMin) < d.TOLERANCE and abs(on_bed.BoundBox.ZMin) < d.TOLERANCE,
           "a cone frustum lies on its mantle")


def moved(shape, change):
    result = shape.copy()
    result.Placement = change.multiply(result.Placement)
    return result


def leaning_at(shape, degrees):
    """Faces that lean over the bed at `degrees` against it."""
    wanted = -math.cos(math.radians(degrees))
    return [f for f in shape.Faces if f.findPlane() is not None and abs(f.normalAt(0, 0).z - wanted) < 1e-6]


def resting_height(shape):
    """Height of the lowest point of `shape`, measured to a plane far below, not from its BoundBox."""
    floor = Part.makePlane(FLOOR_SIZE, FLOOR_SIZE, V(-FLOOR_SIZE / 2, -FLOOR_SIZE / 2, -FLOOR_DEPTH))
    return shape.distToShape(floor)[0] - FLOOR_DEPTH


def check_tight_bounds():
    """Two fillets meeting at a corner: after the part is laid on one, the BoundBox of the
    other reaches below the bed. The part must still rest on the fillet, on the bed, with
    its fins on the bed too."""
    box = Part.makeBox(30, 20, 20)
    corner = [e for e in box.Edges if e.BoundBox.ZMin > 20 - d.TOLERANCE
              and (e.BoundBox.YMax < d.TOLERANCE or e.BoundBox.XMax < d.TOLERANCE)]
    rounded = box.makeFillet(EDGE_ROUND, corner)
    long_fillet = [f for f in rounded.Faces if f.findPlane() is None and f.BoundBox.XLength > 20][0]
    lying = moved(rounded, orient.lay_flat(rounded, long_fillet))
    expect(abs(resting_height(lying)) < d.TOLERANCE,
           "a part laid on a fillet beside another rests on the bed, not above it")
    leaning = [f for f in lying.Faces if f.findPlane() is not None
               and -1 + d.TOLERANCE < f.normalAt(0, 0).z < -d.MIN_NORMAL_COMPONENT]
    built = geometry.build(lying, leaning[0], FinParams())
    expect(abs(resting_height(built.fins)) < d.TOLERANCE, "the fins of that part stand on the bed, not below it")


def check_chamfer_and_fillet():
    """A chamfer or a fillet chosen alone is laid onto the bed and carries the part."""
    box = Part.makeBox(BOX_SIDE, BOX_SIDE, BOX_SIDE)
    edge = [e for e in box.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]

    chamfered = box.makeChamfer(EDGE_ROUND, [edge])
    chamfer = [f for f in chamfered.Faces if abs(abs(f.normalAt(0, 0).z) - math.sqrt(0.5)) < 1e-6][0]
    on_chamfer = moved(chamfered, orient.lay_flat(chamfered, chamfer))
    expect(abs(on_chamfer.BoundBox.ZMin) < d.TOLERANCE and len(leaning_at(on_chamfer, 45)) == 2,
           "a box stands at 45 degrees on its chamfer")

    filleted = box.makeFillet(EDGE_ROUND, [edge])
    fillet = [f for f in filleted.Faces if f.findPlane() is None][0]
    on_fillet = moved(filleted, orient.lay_flat(filleted, fillet))
    expect(abs(on_fillet.BoundBox.ZMin) < d.TOLERANCE and len(leaning_at(on_fillet, 45)) == 2,
           "a box stands at 45 degrees on its fillet")
    try:
        orient.stand(filleted, fillet.Edges[0], d.TILT_ANGLE, fillet)
    except orient.OrientError as error:
        expect("rounded" in str(error), "an edge with a fillet is refused with a clear reason: %s" % error)
    else:
        raise AssertionError("a part was stood on an edge of a fillet")

    # The two faces beside the fillet, or beside a sharp edge: both end up equally steep.
    sides = [f for f in filleted.Faces if f.findPlane() is not None
             and any(e.isSame(other) for e in f.Edges for other in fillet.Edges)
             and abs(f.normalAt(0, 0).dot(edge.Curve.Direction)) < d.TOLERANCE]
    beside = moved(filleted, orient.rest_between(filleted, *sides))
    expect(abs(beside.BoundBox.ZMin) < d.TOLERANCE and len(leaning_at(beside, 45)) == 2
           and abs(beside.BoundBox.ZMax - on_fillet.BoundBox.ZMax) < d.TOLERANCE,
           "the two faces beside a fillet stand the box on it, as the fillet alone does")
    sharp = [f for f in box.Faces if any(e.isSame(edge) for e in f.Edges)]
    on_edge = moved(box, orient.rest_between(box, *sharp))
    expect(abs(on_edge.BoundBox.ZMin) < d.TOLERANCE and len(leaning_at(on_edge, 45)) == 2,
           "the two faces of a sharp edge stand the box on that edge")
    opposite = [f for f in box.Faces if f.BoundBox.ZLength < d.TOLERANCE]
    try:
        orient.rest_between(box, *opposite)
    except orient.OrientError as error:
        expect("opposite" in str(error), "two faces pointing opposite ways are refused: %s" % error)
    else:
        raise AssertionError("two opposite faces were accepted")

    # An L profile rounded in its inner corner: the part cannot rest on a hollow.
    notched = box.cut(Part.makeBox(BOX_SIDE / 2, BOX_SIDE, BOX_SIDE / 2, V(BOX_SIDE / 2, 0, BOX_SIDE / 2)))
    inner = [e for e in notched.Edges if abs(e.BoundBox.ZMin - BOX_SIDE / 2) < d.TOLERANCE
             and abs(e.BoundBox.XMin - BOX_SIDE / 2) < d.TOLERANCE and e.BoundBox.YLength > d.TOLERANCE][0]
    hollow = notched.makeFillet(EDGE_ROUND, [inner])
    concave = [f for f in hollow.Faces if f.findPlane() is None][0]
    try:
        orient.lay_flat(hollow, concave)
    except orient.OrientError as error:
        expect("cannot rest" in str(error), "an inner fillet cannot carry the part: %s" % error)
    else:
        raise AssertionError("a part was laid onto an inner fillet")
    inner_sides = [f for f in hollow.Faces if f.findPlane() is not None
                   and any(e.isSame(other) for e in f.Edges for other in concave.Edges)
                   and f.BoundBox.ZMin > d.TOLERANCE and f.BoundBox.XMin > d.TOLERANCE]
    try:
        orient.rest_between(hollow, *inner_sides[:2])
    except orient.OrientError as error:
        expect("cannot rest" in str(error), "the faces of an inner corner cannot carry the part: %s" % error)
    else:
        raise AssertionError("a part was stood between the faces of an inner corner")


def check_thickness():
    """1 mm up to 100 mm of height, then 1 mm per 100 mm, never thinner than two beads."""
    p = FinParams()
    base_height = d.FIN_THICKNESS_BASE_HEIGHT
    expect(math.isclose(geometry.thickness_for(p, base_height), d.FIN_THICKNESS_BASE)
           and math.isclose(geometry.thickness_for(p, 2 * base_height), 2 * d.FIN_THICKNESS_BASE),
           "the fin is 1 mm thick up to 100 mm and grows in proportion above")
    wide = FinParams(nozzle_diameter=WIDE_NOZZLE, bead_width=WIDE_BEAD)
    expect(math.isclose(geometry.thickness_for(wide, base_height), d.FIN_MIN_BEADS * WIDE_BEAD),
           "with wide beads the fin is at least two beads thick")


def check_one_corner(cube, face):
    """One fin on the left or the right end of the face, its tine flush with that end."""
    frame = face_frame.frame_of(cube, face)
    for placement, end in ((d.PLACEMENT_CORNER_LEFT, frame.along_min), (d.PLACEMENT_CORNER_RIGHT, frame.along_max)):
        result = geometry.build(cube, face, FinParams(placement=placement))
        ts = [v.Point.dot(frame.along) for tine in result.tines for v in tine.Vertexes]
        flush = min(ts) if placement == d.PLACEMENT_CORNER_LEFT else max(ts)
        expect(len(result.fins.Solids) == 1 and abs(flush - end) < d.TOLERANCE,
               "%s gives one fin, its tine flush with that end of the face" % placement)


def check_tine_ends(cube, face):
    """The end of every tine is measured on the part itself: on the face, or
    the tine clearance short of it, within the tolerance; one that misses the
    face or reaches into the part is said so."""
    box = Part.makeBox(BOX_SIDE, BOX_SIDE, BOX_SIDE)
    bottom = [f for f in box.Faces if f.BoundBox.ZMax < d.TOLERANCE][0]
    middle = BOX_SIDE / 2
    clearance = d.GAP / 2
    far = 2 * d.TINE_END_TOLERANCE

    def at(*depths):
        """Points under the middle of the bottom face, `depths` below it (mm,
        negative inside the box)."""
        return [V(middle + k, middle, -depth) for k, depth in enumerate(depths)]

    for points, gap, wanted, what in (
            (at(0, 0), 0.0, None, "on the face, no clearance"),
            (at(clearance, clearance), clearance, None, "the clearance short of it"),
            (at(clearance + d.TINE_END_TOLERANCE / 2), clearance, None, "within the tolerance"),
            (at(clearance, clearance + far), clearance, tine_rows.TINE_MISSES, "further off"),
            (at(clearance - far, clearance + far), clearance, tine_rows.TINE_CUTS_IN,
             "into the part, another further off"),
            ([V(BOX_SIDE + clearance + far, middle, -clearance)], clearance, tine_rows.TINE_MISSES,
             "past the end of the face")):
        found = tine_rows.tine_end_fault(bottom, points, gap)
        expect(found == wanted, "a tine end %s: %s" % (what, found))
        # Against all the faces of the box, of which the bottom alone is near: the same.
        found = tine_rows.tine_end_fault(box, points, gap)
        expect(found == wanted, "a tine end %s, against the whole box: %s" % (what, found))
    expect(tine_rows.tine_end_fault(box, [V(middle, middle, middle)], clearance) == tine_rows.TINE_CUTS_IN
           and tine_rows.tine_end_fault(box, [V(middle, middle, -BOX_SIDE)], clearance) == tine_rows.TINE_MISSES,
           "a point in the box of no face, deep in the part or far below it, is measured against all the faces")
    # A face on a torus has no box: it is measured for every point, alone and beside a flat face.
    ring = Part.makeTorus(RING[0], RING[1], V(0, 0, -BOX_SIDE))
    with_flat = Part.makeCompound([ring.Faces[0], bottom])
    for surface, what in ((ring, "a ring"), (with_flat, "a ring beside a flat face")):
        found = [tine_rows.tine_end_fault(surface, [V(sum(RING) + off, 0, -BOX_SIDE)], clearance)
                 for off in (clearance, clearance + far, clearance - far)]
        expect(found == [None, tine_rows.TINE_MISSES, tine_rows.TINE_CUTS_IN],
               "a tine end the clearance off %s, further off and nearer: %s" % (what, found))
    boxes = [box for _, box in shapes.boxed_faces(with_flat, clearance)]
    expect(boxes[0] is None and abs(boxes[1].ZMin + clearance) < d.TOLERANCE
           and abs(boxes[1].XMax - BOX_SIDE - clearance) < d.TOLERANCE
           and shapes.boxed_faces(Part.Compound([])) == [],
           "a face on a torus has no box, a flat face the one that touches it, wider by what is asked; "
           "a shape without a face has none")
    # A round part that carries a mesh: the BoundBox of its side stops short of it, the box that touches it not.
    radius, height = ENDS_ROUND
    round_part = Part.makeCylinder(radius, height)
    plain = round_part.copy()
    round_part.tessellate(ENDS_ROUND_MESH)
    side = next(f for f in round_part.Faces if isinstance(f.Surface, Part.Cylinder))

    def short_at(turn):
        """How far the BoundBox of the side stops short of it, `turn` degrees round the axis."""
        out = App.Rotation(V(0, 0, 1), turn).multVec(V(1, 0, 0))
        reach = side.BoundBox
        return radius - max(V(x, y, 0).dot(out) for x in (reach.XMin, reach.XMax) for y in (reach.YMin, reach.YMax))

    turn = max(APART_ROUND_TURNS, key=short_at)
    short = short_at(turn)
    out, half = radius + ENDS_ROUND_OFF, ENDS_ROUND_FLAT
    by_side = V(out, 0, height / 2)
    # Its corners in the order that turns its outward side to the point.
    flat = Part.Face(Part.makePolygon([V(out + ENDS_ROUND_CLEARANCE, y, height / 2 + z)
                                       for y, z in ((-half, -half), (-half, half), (half, half), (half, -half),
                                                    (-half, -half))]))
    flat.rotate(V(0, 0, 0), V(0, 0, 1), turn)
    by_side = App.Rotation(V(0, 0, 1), turn).multVec(by_side)
    found = [tine_rows.tine_end_fault(Part.makeCompound([shape, flat]), [by_side], ENDS_ROUND_CLEARANCE)
             for shape in (side, plain)]
    alone = tine_rows.tine_end_fault(flat, [by_side], ENDS_ROUND_CLEARANCE)
    expect(short > ENDS_ROUND_CLEARANCE + d.TINE_END_TOLERANCE + d.TOLERANCE + ENDS_ROUND_OFF
           and alone is None and found == [tine_rows.TINE_CUTS_IN] * 2,
           "a point %.2f mm off the side of a round part that carries a mesh, where the BoundBox of the side stops "
           "%.2f mm short of it, and the clearance off a flat face beside it, is too near the side: %s"
           % (ENDS_ROUND_OFF, short, found))

    def said(result):
        return [w for w in result.warnings if "miss the face" in w or "into the part" in w]

    # The ends measured as if every tine stopped short of the face or reached
    # into the part: the build names them and marks every fin and tine.
    real = geometry.tine_end_points
    for shift, words in ((TINE_END_SHIFT, "miss the face"), (-TINE_END_SHIFT, "into the part")):
        geometry.tine_end_points = lambda p, frame, *args, by=shift: [
            point + frame.normal() * by for point in real(p, frame, *args)]
        try:
            result = geometry.build(cube, face, FinParams())
        finally:
            geometry.tine_end_points = real
        found = [i for i, w in enumerate(result.warnings) if words in w]
        target = result.warning_targets[found[0]] if len(found) == 1 else None
        expect(target is not None and target.fins == result.numbers and len(target.tines) == len(result.tines),
               "tine ends %.1f mm off the face are named \"%s\", every fin and tine marked: %s"
               % (shift, words, result.warnings))

    def on_rim(shape):
        """`shape` stood on its rim by Quick fins, and its side leaning over the bed."""
        side = round_side_of(shape)
        plan = quick_stands.quick_plan(shape, [], [(shape.Faces[side], side)], FinParams(), d.TILT_ANGLE)
        stood = moved(shape, plan.change)
        return stood, stood.Faces[plan.number]

    # A solid from a mesh as the Part workbench makes it: Shape from Mesh,
    # Convert to Solid, Refine Shape.
    import Mesh
    sewn = Part.Shape()
    sewn.makeShapeFromMesh(Mesh.Mesh(cube.tessellate(TINE_END_MESH_DEFLECTION)).Topology, TINE_END_SEW_TOLERANCE)
    meshed = Part.makeSolid(Part.makeShell(sewn.Faces)).removeSplitter()
    tube = Part.makeCylinder(ROD_RADIUS, ROD_HEIGHT).cut(Part.makeCylinder(BORE_RADIUS, ROD_HEIGHT))
    split = orient.joined(split_cylinder(ROD_RADIUS, ROD_HEIGHT, BORE_RADIUS))
    for name, part, under, params in (
            ("the reference cube", cube, face, FinParams()),
            ("the reference cube with a tine clearance", cube, face, FinParams(tine_clearance=clearance)),
            ("a solid converted from a mesh", meshed, lower_left_face(meshed), FinParams()),
            ("the side of a tube on its rim", *on_rim(tube), FinParams()),
            ("the side of a split tube on its rim", *on_rim(split), FinParams())):
        result = geometry.build(part, under, params)
        expect(result.tines and not said(result), "every tine of %s ends on the face: %s" % (name, said(result)))


def check_tine_clearance(cube, face):
    """Tines end the clearance short of the face and are as much shorter; the
    fin stays at the gap. A clearance as large as the gap leaves no tine and
    is refused; tines too short for the slicer are warned about."""
    clearance = d.GAP / 2
    touching = geometry.build(cube, face, FinParams(tine_clearance=0.0))
    result = geometry.build(cube, face, FinParams(tine_clearance=clearance))
    distances = [tine.distToShape(face)[0] for tine in result.tines]
    expect(all(abs(distance - clearance) < d.TOLERANCE for distance in distances),
           "every tine ends %.3f mm short of the face: %s" % (clearance, distances))
    expect(all(abs(body.distToShape(face)[0] - d.GAP) < d.TOLERANCE for body in result.bodies),
           "the fin stays the gap from the face, whatever the clearance")
    expect(result.tines[0].Volume < touching.tines[0].Volume - d.TOLERANCE,
           "the tines are shorter by the clearance")
    short = [w for w in result.warnings if "tines are" in w]
    expect(short, "tines shortened below what the slicer prints are warned about: %s" % result.warnings)
    # The gap the warning names makes them long enough.
    named = float(re.search(r"A gap of ([0-9.]+) mm", short[0]).group(1))
    enough = geometry.build(cube, face, FinParams(tine_clearance=clearance, gap=named))
    expect(not [w for w in enough.warnings if "tines are" in w],
           "the gap of %.2f mm the warning names makes the tines long enough" % named)
    # A bead so wide that no gap taken makes them long enough: no gap named.
    wide = FinParams(nozzle_diameter=WIDE_NOZZLE, bead_width=WIDE_NOZZLE, layer_height=WIDE_LAYER,
                     first_layer_height=WIDE_LAYER)
    beyond = [w for w in geometry.build(cube, face, wide).warnings if "tines are" in w]
    expect(beyond and "narrower bead" in beyond[0] and "A gap of" not in beyond[0],
           "with a bead too wide for any gap taken, the warning asks for a narrower bead: %s" % beyond)
    expect(not [w for w in geometry.build(cube, face, FinParams()).warnings if "tines are" in w],
           "the tines of the built-in gap and clearance are long enough")
    for wrong, why in ((-clearance, "negative"), (d.GAP, "as large as the gap")):
        try:
            FinParams(tine_clearance=wrong).validate()
        except ParamError as error:
            expect("tine_clearance" in str(error), "a clearance %s is refused: %s" % (why, error))
        else:
            raise AssertionError("a tine clearance %s was accepted" % why)
    FinParams(gap=d.GAP_MAX).validate()
    try:
        FinParams(gap=d.GAP_MAX + d.GAP).validate()
    except ParamError as error:
        expect("gap" in str(error), "a gap past %.1f mm is refused, its tines too long: %s" % (d.GAP_MAX, error))
    else:
        raise AssertionError("a gap past the largest was accepted")


def check_shortened(cube, face):
    """With one tine grid for every fin: a fin whose top tine finds a hole ends at the tine below; a
    fin height given by hand stays."""
    frame = face_frame.frame_of(cube, face)
    normal = face.normalAt(0, 0)
    full = geometry.build(cube, face, FinParams(tine_restart=False))
    top_tine = full.tine_z[-1] + FinParams(tine_restart=False).tine_height / 2
    middle = (frame.along_min + frame.along_max) / 2
    on_face = frame.point(middle, frame.s_face(top_tine), top_tine)
    holed = cube.cut(Part.makeCylinder(RECESS_RADIUS, 2 * RECESS_RADIUS, on_face - normal * RECESS_RADIUS, normal))
    holed_face = lower_left_face(holed)
    shortened = geometry.build(holed, holed_face, FinParams(tine_restart=False))
    expect(math.isclose(shortened.height, full.tine_z[-2] + FinParams(tine_restart=False).tine_height),
           "the fin ends at its highest tine left, %.2f mm" % shortened.height)
    kept = geometry.build(holed, holed_face, FinParams(tine_restart=False, fin_height=full.height))
    expect(math.isclose(kept.height, full.height), "a fin height given by hand is kept")


def check_restart(cube, face):
    """With the tine grid restarted after a gap: a face that rises from the
    bed in one stretch keeps the one grid; above a hole the grid starts anew
    and its tines are spread to the top of the face, none over the hole."""
    restart, one_grid = FinParams(), FinParams(tine_restart=False)
    expect(restart.tine_restart and geometry.build(cube, face, restart).tine_z
           == geometry.build(cube, face, one_grid).tine_z,
           "a face from the bed up without a gap keeps the one tine grid")
    frame = face_frame.frame_of(cube, face)
    normal = face.normalAt(0, 0)
    middle = (frame.along_min + frame.along_max) / 2
    hole_z = geometry.build(cube, face, one_grid).tine_z[1] + one_grid.tine_height / 2
    on_face = frame.point(middle, frame.s_face(frame.bed_z + hole_z), frame.bed_z + hole_z)
    holed = cube.cut(Part.makeCylinder(RECESS_RADIUS, 2 * RECESS_RADIUS, on_face - normal * RECESS_RADIUS, normal))
    holed_face = lower_left_face(holed)
    spread = geometry.build(holed, holed_face, restart)
    gridded = geometry.build(holed, holed_face, one_grid)
    room = frame.room
    expect(not spread.dropped and gridded.dropped and spread.height > room - restart.layer_height - d.TOLERANCE,
           "above a hole the grid starts anew: no tine over it, the top tine at the top of the face: "
           "%.2f mm of %.2f" % (spread.height, room))
    own = geometry.build(holed, holed_face, restart, heights={spread.numbers[0]: spread.height})
    expect(spread.height > gridded.height and own.thickness == spread.thickness
           and math.isclose(own.foot_half_width, spread.foot_half_width),
           "a height of its own on a tine above those of the face gets the fin and foot it needs: %.2f mm"
           % own.foot_half_width)


def sunk_around(cube, face, low, high):
    """`cube` with `face` sunk SINK_DEPTH below `low` and above `high` (mm
    from the bed), and the stretch between as a face of its own."""
    frame = face_frame.frame_of(cube, face)
    normal = face.normalAt(0, 0)
    sunk = cube
    for bottom, top in ((-OUT_OF_REACH, low), (high, OUT_OF_REACH)):
        box = Part.makeBox(OUT_OF_REACH, OUT_OF_REACH, top - bottom,
                           V(-OUT_OF_REACH / 2, -OUT_OF_REACH / 2, frame.bed_z + bottom))
        layer = cube.common(box)
        sunk = sunk.cut(layer.cut(layer.translated(-normal * SINK_DEPTH)))
    stretch = next(f for f in sunk.Faces if f.normalAt(0, 0).getAngle(normal) < d.TOLERANCE
                   and abs(f.BoundBox.ZMin - frame.bed_z - low) < d.TOLERANCE)
    return sunk, stretch


def check_restart_above_fillet():
    """A face that starts above a fillet the part rests on: its first tine on
    the first layer from the lower edge of the face up, right above the
    fillet, and resting on the face."""
    p = FinParams()
    box = Part.makeBox(30, 20, 20)
    bottom = [e for e in box.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE]
    filleted = box.makeFillet(FILLET_RADIUS, bottom)
    fillet = [i for i, f in enumerate(filleted.Faces) if f.findPlane() is None][0]
    plan = quick_stands.quick_plan(filleted, [], [(filleted.Faces[fillet], fillet)], p, d.TILT_ANGLE)
    stood = moved(filleted, plan.change)
    face = stood.Faces[plan.number]
    frame = face_frame.frame_of(stood, face)
    floor = frame.face_bottom_z - frame.bed_z
    built = geometry.build(stood, face, p)
    expect(floor > d.TOLERANCE and abs(built.tine_z[0] - tine_rows._snap_up(p, floor)) < d.TOLERANCE
           and built.tine_z[0] < floor + p.layer_height and not built.dropped,
           "above a fillet the first tine starts on the first layer from the face up: %.2f over %.2f"
           % (built.tine_z[0], floor))


def check_restart_planned(cube, face):
    """With the restart each fin is planned on its own grid from the start:
    a short face high above the bed that the one grid misses gets tines, and
    a fin whose grid tines all lie over holes bridges them where it stands,
    instead of moving beside them."""
    restart, one_grid = FinParams(), FinParams(tine_restart=False)
    grid = geometry.build(cube, face, one_grid).tine_z
    sunk, short = sunk_around(cube, face, grid[1] + SINK_INSET, grid[2] - SINK_INSET)
    try:
        geometry.build(sunk, short, one_grid)
    except face_frame.FinError:
        missed = True
    else:
        missed = False
    above = geometry.build(sunk, short, restart)
    expect(missed and above.tines and not above.moved,
           "a short face between two grid tines, refused on one grid, gets %d tines with the restart"
           % len(above.tines))
    frame = face_frame.frame_of(cube, face)
    normal = face.normalAt(0, 0)
    middle = (frame.along_min + frame.along_max) / 2
    holed = cube
    for z in grid:
        centre = frame.bed_z + z + one_grid.tine_height / 2
        on_face = frame.point(middle, frame.s_face(centre), centre)
        holed = holed.cut(Part.makeCylinder(RECESS_RADIUS, 2 * RECESS_RADIUS, on_face - normal * RECESS_RADIUS,
                                            normal))
    holed_face = lower_left_face(holed)
    gridded = geometry.build(holed, holed_face, one_grid)
    bridged = geometry.build(holed, holed_face, restart)
    expect(gridded.moved and not bridged.moved and bridged.tines and not bridged.dropped,
           "a fin whose grid tines all lie over holes moves on one grid, and bridges them with the restart: %s"
           % bridged.touching_z)


def check_restart_narrow_lower_edge():
    """With the restart, fins on a face that starts above the bed at a narrow
    edge stand as far apart as on the one grid: the lowest tines of the face
    as a whole do not crowd them together. A prism whose end, the face, tapers
    to a short edge at the bottom, sheared so that its far end stands on the bed."""
    def on_face(up, along):
        return V(-up, along, up)

    half, end, widest, top = POINTED_HALF_WIDTH, POINTED_END_HALF_WIDTH, POINTED_WIDEST_AT, POINTED_TOP
    ring = [on_face(0, end), on_face(widest, half), on_face(top, half), on_face(top, -half), on_face(widest, -half),
            on_face(0, -end)]
    stood = Part.Face(Part.makePolygon(ring + ring[:1])).extrude(V(POINTED_DEPTH, 0, -POINTED_LIFT))
    stood.translate(V(0, 0, -stood.BoundBox.ZMin))
    face = lower_left_face(stood)
    three = {"placement": d.PLACEMENT_DISTRIBUTED, "fin_count": 3}
    restart = geometry.build(stood, face, FinParams(**three))
    grid = geometry.build(stood, face, FinParams(tine_restart=False, **three))
    expect(restart.numbers == grid.numbers == [1, 2, 3] and restart.positions == grid.positions,
           "three fins on a face narrow at its lower edge stand where the one grid has them: %s" % restart.positions)
    expect(restart.touching_z[2][0] < grid.touching_z[2][0],
           "the fin in the middle still reaches the lower edge: %s" % restart.touching_z[2])
    expect(all(len(restart.touching_z[n]) >= len(grid.touching_z[n])
               for n in restart.numbers) and not restart.moved,
           "each of them holds as much as on the one grid, none left out where the face is narrow: %s"
           % restart.touching_z)


def recessed_from_bed(cube, face, half_width, left, along=None):
    """`cube` with a recess across the middle of `face`, from the bed up to
    `left` mm below its top, centred at `along` on the face if given, and the
    largest piece of that face."""
    frame = face_frame.frame_of(cube, face)
    normal = face.normalAt(0, 0)
    middle = (frame.along_min + frame.along_max) / 2
    top = frame.face_top_z - frame.bed_z
    # The face runs along Y.
    centre_y = frame.point(middle if along is None else along, frame.s_face(frame.bed_z), frame.bed_z).y
    box = Part.makeBox(OUT_OF_REACH, 2 * half_width, top - left + OUT_OF_REACH,
                       V(-OUT_OF_REACH / 2, centre_y - half_width, frame.bed_z - OUT_OF_REACH))
    layer = cube.common(box)
    part = cube.cut(layer.cut(layer.translated(-normal * SINK_DEPTH)))
    return part, largest_facing(part, normal)


def check_restart_short_stretch(cube, face):
    """With the restart a fin left with a short stretch of the face under it,
    by a recess from the bed up, goes where its tines hold far more; moved by
    hand or on one grid it stays out of that. A height set by hand changes
    nothing about where it stands."""
    restart, one_grid = FinParams(placement=d.PLACEMENT_CENTER), FinParams(placement=d.PLACEMENT_CENTER,
                                                                           tine_restart=False)
    part, notched = recessed_from_bed(cube, face, SHORT_STRETCH_RECESS, SHORT_STRETCH_LEFT)

    def held(result, number):
        zs = result.touching_z[number]
        return max(zs) + restart.tine_height - min(zs)

    stayed = geometry.build(part, notched, restart, shifts={1: 0.0})
    moved_on = geometry.build(part, notched, restart)
    expect(not stayed.moved and moved_on.moved and held(moved_on, 1) >= d.BETTER_PLACE_HOLDS * held(stayed, 1),
           "a fin on a short stretch goes where its tines hold far more, from %.2f to %.2f mm, moved by %s"
           % (held(stayed, 1), held(moved_on, 1), moved_on.moved))
    for tine in moved_on.touching_z[1]:
        own = geometry.build(part, notched, restart, heights={1: tine + restart.tine_height})
        expect(own.starts == moved_on.starts and own.moved == moved_on.moved,
               "a fin that moved by itself stands there with a height of %.2f set by hand" % own.heights[1])
    # The place found can lie at exactly 0 along the face.
    shifted = part.translated(V(0, moved_on.starts[1], 0))
    at_zero = geometry.build(shifted, largest_facing(shifted, face.normalAt(0, 0)), restart)
    expect(at_zero.moved and abs(at_zero.starts[1]) < d.TOLERANCE and held(at_zero, 1) == held(moved_on, 1),
           "a fin goes to a place found at 0 along the face as to any other: %s" % at_zero.starts)
    # A fin on a corner, its tine over a recess up to a short stretch, a thin
    # wall of the face beside it, with far more to hold further along.
    corner = FinParams(placement=d.PLACEMENT_CORNER_LEFT)
    frame = face_frame.frame_of(cube, face)
    pit, pit_face = recessed_from_bed(cube, face, SHORT_STRETCH_RECESS, SHORT_STRETCH_LEFT,
                                      frame.along_min + CORNER_WALL + SHORT_STRETCH_RECESS)
    placed = geometry.build(pit, pit_face, corner)
    room = frame.room
    expect(not placed.moved and held(placed, placed.numbers[0]) * d.BETTER_PLACE_HOLDS <= room,
           "a fin on a corner stays there on a short stretch: %s" % placed.touching_z)
    plain = geometry.build(cube, face, restart)
    expect(not plain.moved, "a fin on a face without a recess stays at its planned place")
    expect(not geometry.build(part, notched, one_grid).moved, "on one grid a fin with a tine on the face stays")


def t_beam(sunk=False):
    """A T standing on its web, tilted TILT with its front face overhanging,
    and that face. Above the web a slot T_SLOT wide runs up the flange:
    through the T to its top, or with `sunk` SINK_DEPTH deep into its front,
    ending SHORT_STRETCH_LEFT below the top so the face stays one piece, the
    front of the web sunk with it but for a wall CORNER_WALL thin at either
    side."""
    web, flange = T_WEB / 2, T_FLANGE / 2
    outline = [V(0, -web, 0), V(0, web, 0), V(0, web, T_WEB_HIGH), V(0, flange, T_WEB_HIGH), V(0, flange, T_HIGH),
               V(0, -flange, T_HIGH), V(0, -flange, T_WEB_HIGH), V(0, -web, T_WEB_HIGH)]
    part = Part.Face(Part.makePolygon(outline + outline[:1])).extrude(V(T_DEEP, 0, 0))
    slot_from = T_WEB_HIGH + T_SLOT_ABOVE_WEB
    if sunk:
        pocket = web - CORNER_WALL
        recesses = [Part.makeBox(OUT_OF_REACH, 2 * pocket, slot_from, V(T_DEEP - SINK_DEPTH, -pocket, 0)),
                    Part.makeBox(OUT_OF_REACH, T_SLOT, T_HIGH - SHORT_STRETCH_LEFT - slot_from,
                                 V(T_DEEP - SINK_DEPTH, -T_SLOT / 2, slot_from))]
    else:
        recesses = [Part.makeBox(OUT_OF_REACH, T_SLOT, OUT_OF_REACH, V(-OUT_OF_REACH / 2, -T_SLOT / 2, slot_from))]
    for recess in recesses:
        part = part.cut(recess)
    part = tilted(part)
    return part, largest_facing(part, App.Rotation(V(0, 1, 0), TILT).multVec(V(1, 0, 0)))


def beside_slot(result):
    """Whether the one fin of `result` stands wholly beside the slot of t_beam()."""
    start = result.starts[1]
    return start + result.thickness <= -T_SLOT / 2 + d.TOLERANCE or start >= T_SLOT / 2 - d.TOLERANCE


def check_search_inset(cube, face):
    """A fin finding a place of its own keeps the end inset from either end
    of the face, as the fins planned there, so it does not end on a chamfer:
    a place only nearer an end than that is not found; with no inset it is."""
    p = FinParams()
    frame = face_frame.frame_of(cube, face)
    step = p.end_inset / 2
    middle = (frame.along_min + frame.along_max) / 2

    def near_an_end(t):
        return t < frame.along_min + p.end_inset - d.TOLERANCE or \
            t + step > frame.along_max - p.end_inset + d.TOLERANCE

    kept = geometry.nearest_place(frame, p.end_inset, near_an_end, middle, step, [])
    flush = geometry.nearest_place(frame, 0.0, near_an_end, middle, step, [])
    expect(kept is None and flush is not None,
           "a fin finding its own place stays %.2f mm from the ends of the face: %s, without the inset %s"
           % (p.end_inset, kept, flush))


def check_places_past_stretch():
    """A fin on the web of a T, the stretch every tine of the face shares,
    finds its place beside the slot above, past that stretch: with the
    restart one holding far more than its tines on the web, and on one grid,
    with the web sunk under it, one where a tine finds the face at all."""
    p = FinParams(placement=d.PLACEMENT_CENTER)
    part, front = t_beam()

    def held(result):
        zs = result.touching_z[1]
        return max(zs) + p.tine_height - min(zs)

    stayed = geometry.build(part, front, p, shifts={1: 0.0})
    found = geometry.build(part, front, p)
    expect(found.moved and beside_slot(found) and held(found) >= d.BETTER_PLACE_HOLDS * held(stayed),
           "a fin on the web of a T goes beside the slot above it, from %.2f to %.2f mm held, moved by %s"
           % (held(stayed), held(found), found.moved))
    sunk, sunk_front = t_beam(sunk=True)
    rested = geometry.build(sunk, sunk_front, FinParams(placement=d.PLACEMENT_CENTER, tine_restart=False))
    expect(rested.moved and beside_slot(rested) and rested.touching_z[1],
           "on one grid a fin on a sunk web goes beside the sunk slot above it, moved by %s" % rested.moved)


def check_moved_fins_feet():
    """Feet of fins that moved towards a neighbour stay clear of it: a foot is
    as wide as the closest fins standing where they ended up allow."""
    box = Part.makeBox(FEET_EDGE, FEET_EDGE, FEET_EDGE, V(-FEET_EDGE / 2, 0, -FEET_EDGE / 2))
    large = box.makeChamfer(CHAMFER, box.Edges)
    large.rotate(V(0, 0, 0), V(0, 1, 0), d.TILT_ANGLE)
    large.translate(V(0, 0, -large.BoundBox.ZMin))
    part, notched = recessed_from_bed(large, lower_left_face(large), FEET_RECESS, SHORT_STRETCH_LEFT)
    result = geometry.build(part, notched, FinParams(placement=d.PLACEMENT_DISTRIBUTED, fin_count=FEET_FINS))
    places = sorted(result.starts.values())
    least = min(b - a for a, b in zip(places, places[1:]))
    overlap = sum(one.common(other).Volume for i, one in enumerate(result.bodies) for other in result.bodies[i + 1:])
    expect(result.moved and overlap < d.TOLERANCE
           and 2 * result.foot_half_width + d.FOOT_CLEARANCE <= least + d.TOLERANCE,
           "fins that moved keep their feet apart: %.2f mm between them, feet %.2f mm wide, overlap %.3f mm3"
           % (least, 2 * result.foot_half_width, overlap))


def check_restart_names_what_fins_lack():
    """With the restart the warning names the tines a fin lacks, not those of
    the face as a whole: a face leaning aside as it rises, whose lowest tines
    share no stretch with the higher ones, under a fin high up on it."""
    ring = [V(0, -SKEWED_LOW, 0), V(0, SKEWED_LOW, 0), V(-SKEWED_WIDEST_AT, SKEWED_WIDE, SKEWED_WIDEST_AT),
            V(-POINTED_TOP, SKEWED_WIDE, POINTED_TOP), V(-POINTED_TOP, SKEWED_LOW + 1, POINTED_TOP),
            V(-SKEWED_WIDEST_AT, -SKEWED_LOW, SKEWED_WIDEST_AT)]
    part = Part.Face(Part.makePolygon(ring + ring[:1])).extrude(V(POINTED_DEPTH, 0, -POINTED_LIFT))
    part.translate(V(0, 0, -part.BoundBox.ZMin))
    face = lower_left_face(part)
    result = geometry.build(part, face, FinParams(placement=d.PLACEMENT_CENTER))
    expect(not any("narrower" in warning for warning in result.warnings),
           "tines no fin lacks are not named as left out: %s, the fin has %s" % (result.warnings, result.touching_z))


def check_restart_narrow(cube, face):
    """With the restart a fin on its own grid gets no tine where the face is
    narrower than the fin: a notch in the end of the face, beside the fin
    but clear of its tine, between two grid tines, over a fin whose grid
    restarts above a hole."""
    p, one_grid = FinParams(placement=d.PLACEMENT_ENDS), FinParams(tine_restart=False, placement=d.PLACEMENT_ENDS)
    frame = face_frame.frame_of(cube, face)
    normal = face.normalAt(0, 0)
    plain = geometry.build(cube, face, one_grid)
    t0, grid = min(plain.positions), plain.tine_z
    start = tine_rows.tine_start(p, t0, plain.thickness)

    def on_face(t, z):
        return frame.point(t, frame.s_face(frame.bed_z + z), frame.bed_z + z)

    low, high = grid[1] + p.tine_height + NOTCH_CLEAR, grid[2] - NOTCH_CLEAR
    # Between the side of the fin and its tine.
    inner = (t0 + start) / 2
    ring = [on_face(frame.along_min - NOTCH_CLEAR, low), on_face(inner, low), on_face(inner, high),
            on_face(frame.along_min - NOTCH_CLEAR, high)]
    notch = Part.Face(Part.makePolygon(ring + ring[:1])).translated(normal * NOTCH_CLEAR).extrude(
        -normal * 2 * NOTCH_CLEAR)
    hole_z = (grid[0] + p.tine_height + grid[1]) / 2
    centre = on_face(start + p.tine_width / 2, hole_z)
    part = cube.cut(notch).cut(Part.makeCylinder(PIN_HOLE_RADIUS, 2 * NOTCH_CLEAR, centre - normal * NOTCH_CLEAR,
                                                 normal))
    notched = largest_facing(part, normal)
    result = geometry.build(part, notched, p)
    first = result.numbers[0]
    beside = [z for z in result.touching_z[first] if z + p.tine_height > low + d.TOLERANCE and z < high - d.TOLERANCE]
    expect(not beside and any(z > high - d.TOLERANCE for z in result.touching_z[first]),
           "no tine where a notch makes the face narrower than the fin, the grid anew above it: %s"
           % result.touching_z[first])


def check_restart_flank_hole(cube, face):
    """With the restart a hole inside the face under the flank of a fin but
    clear of its tine costs no tine: the flank stands off the face, only the
    tines rest on it, and the width counts the outermost points of the face."""
    p = FinParams(fin_thickness=WIDE_FIN)
    frame = face_frame.frame_of(cube, face)
    normal = face.normalAt(0, 0)
    plain = geometry.build(cube, face, FinParams(tine_restart=False, fin_thickness=WIDE_FIN))
    t0, grid = plain.positions[0], plain.tine_z
    start = tine_rows.tine_start(p, t0, WIDE_FIN)

    def pin_hole(part, t, z, radius):
        centre = frame.point(t, frame.s_face(frame.bed_z + z), frame.bed_z + z)
        return part.cut(Part.makeCylinder(radius, 2 * NOTCH_CLEAR, centre - normal * NOTCH_CLEAR, normal))

    # A hole under the tine, between the two lowest grid tines, starts the grid anew.
    restarted = pin_hole(cube, start + p.tine_width / 2, (grid[0] + p.tine_height + grid[1]) / 2, PIN_HOLE_RADIUS)
    # Across the side of the fin, so a slice along that side would find a gap.
    flank = pin_hole(restarted, t0, (grid[1] + grid[2]) / 2, FLANK_HOLE_RADIUS)

    def own_grid(part):
        result = geometry.build(part, largest_facing(part, normal), p)
        return result.touching_z[result.numbers[0]]

    expect(own_grid(flank) == own_grid(restarted),
           "a hole under the flank, clear of the tine, costs no tine: %s" % own_grid(flank))


def check_wide_enough(cube, face):
    """wide_enough(), against its table, on the extents _extent_at() finds."""
    frame = face_frame.frame_of(cube, face)
    p, corner = FinParams(), FinParams(placement=d.PLACEMENT_CORNERS)
    thickness = geometry.thickness_for(p, 0.0)
    low, high = frame.along_min, frame.along_max
    reach = (thickness - p.tine_width) / 2
    notched = (low + thickness / 2, high)
    rows = [("the face wider than the fin", p, (low, high), low + thickness, True),
            ("a notch in the end of the face under the fin", p, notched, low, False),
            ("no face at that height", p, None, low, False),
            ("a corner fin past the end, its tine on the face", corner, (low, high), low - reach, True),
            ("a face as wide as the fin", p, (low, low + thickness), low, True)]
    for name, params, extent, t0, wanted in rows:
        expect(tine_rows.wide_enough(extent, params, t0, thickness) == wanted,
               "wide_enough(): %s -> %s" % (name, wanted))


def check_split_face():
    """A groove across the front splits it into two faces in one plane. The fin
    reaches over the gap and carries both; the tines over the gap are left out."""
    box = Part.makeBox(30, 20, 20)
    grooved = box.cut(Part.makeBox(30, GROOVE_DEPTH, GROOVE_WIDTH, V(0, 0, GROOVE_FROM)))
    edge = [e for e in grooved.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]
    standing = moved(grooved, orient.tilt(grooved, edge, d.TILT_ANGLE))
    front = [f for f in standing.Faces if f.findPlane() is not None
             and abs(f.normalAt(0, 0).z + math.sqrt(0.5)) < 1e-6 and abs(f.normalAt(0, 0).y) > 0.5]
    pieces = [f for f in front if abs(f.normalAt(0, 0).dot(f.Vertexes[0].Point)
                                      - front[0].normalAt(0, 0).dot(front[0].Vertexes[0].Point)) < d.TOLERANCE]
    lower = min(pieces, key=lambda f: f.BoundBox.ZMin)
    upper = max(pieces, key=lambda f: f.BoundBox.ZMin)
    expect(len(face_frame.support_of(standing, lower).Faces) == 2, "the two faces beside the groove form one support")
    result = geometry.build(standing, lower, FinParams())
    expect(max(result.tine_z) > upper.BoundBox.ZMin and any("recess" in w for w in result.warnings),
           "the fin reaches over the groove to the upper face, the tines over it are named: %s" % result.warnings)
    carried = face_frame.support_of(standing, lower).Faces
    hanging = overhanging(standing, supported=carried)
    expect(not any(standing.Faces[n - 1].isSame(upper) for n in hanging),
           "the face above the groove counts as supported")

    # Where fins over the groove would run into the part, they stand under the
    # selected face alone and carry only that one.
    reaching = geometry._build

    def running_into_part(part, face, support, p, tine_count, left_out, shifts, heights):
        if support is not face:
            raise face_frame.FinError("runs into the part")
        return reaching(part, face, support, p, tine_count, left_out, shifts, heights)

    geometry._build = running_into_part
    try:
        alone = geometry.build(standing, lower, FinParams())
    finally:
        geometry._build = reaching
    expect(len(alone.carried) == 1 and alone.carried[0].isSame(lower) and max(alone.tine_z) < upper.BoundBox.ZMin
           and any("runs into the part" in w for w in alone.warnings),
           "fins that cannot reach over the groove stand under the selected face alone, and say why")

    # A change by hand that does not fit over the groove is refused; built
    # under the face alone instead, a drag would change the faces carried.
    def refusing_by_hand(part, face, support, p, tine_count, left_out, shifts, heights):
        if support is not face:
            raise face_frame.HandEditError("fin 2 would pass fin 3")
        return reaching(part, face, support, p, tine_count, left_out, shifts, heights)

    geometry._build = refusing_by_hand
    try:
        geometry.build(standing, lower, FinParams())
    except face_frame.HandEditError as error:
        expect("would pass" in str(error), "a change by hand that does not fit over the groove is refused")
    else:
        raise AssertionError("a change by hand refused over the groove was built under the face alone")
    finally:
        geometry._build = reaching


    # Pieces beside each other along the face are faces of their own: the legs of
    # a U profile, the halves beside an upright slot. The fin stays under the
    # selected one, as without any other face in the plane.
    wide = Part.makeBox(WIDE_BOX, 20, 20)
    for name, cutter in (("U profile", Part.makeBox(WIDE_BOX / 3, 10, 20, V(WIDE_BOX / 3, 0, 0))),
                         ("upright slot", Part.makeBox(GROOVE_WIDTH, GROOVE_DEPTH, 20,
                                                       V(WIDE_BOX / 2, 0, 0)))):
        cut = wide.cut(cutter)
        bottom = max((e for e in cut.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE),
                     key=lambda e: e.Length)
        stood = moved(cut, orient.tilt(cut, bottom, d.TILT_ANGLE))
        side = [f for f in stood.Faces if f.findPlane() is not None
                and abs(f.normalAt(0, 0).z + math.sqrt(0.5)) < 1e-6 and f.normalAt(0, 0).y < -0.5]
        chosen = min(side, key=lambda f: f.BoundBox.XMin)
        alone = face_frame.frame_of(stood, chosen)
        built = geometry.build(stood, chosen, FinParams())
        expect(len(face_frame.support_of(stood, chosen).Faces) == 1
               and all(alone.along_min - d.TOLERANCE <= t <= alone.along_max for t in built.positions),
               "%s: the fin stays under the selected face" % name)
def check_quick_fins():
    """Quick fins: the face that takes fins best after standing on an edge, and
    the orientation that makes a chosen face lean over the bed."""
    p = FinParams()
    box = Part.makeBox(30, 20, 20)
    bottom = [e for e in box.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]
    standing = moved(box, orient.tilt(box, bottom, d.TILT_ANGLE))
    best = quick_stands.best_face(standing, p)
    leaning = [f for f in standing.Faces if abs(f.normalAt(0, 0).z + math.sqrt(0.5)) < 1e-6]
    expect(standing.Faces[best].Area == max(f.Area for f in leaning),
           "after standing on an edge the largest leaning face takes the fins")

    front = [i for i, f in enumerate(box.Faces) if f.BoundBox.YMax < d.TOLERANCE][0]
    change, edge = quick_stands.stand_for_face(box, front, p, d.TILT_ANGLE)
    leant = moved(box, change)
    expect(abs(leant.Faces[front].normalAt(0, 0).z + math.sqrt(0.5)) < 1e-6 and abs(edge.Length - 30) < d.TOLERANCE,
           "a chosen face is turned to lean 45 degrees over the bed, standing on its longest edge")
    expect(abs(resting_height(leant)) < d.TOLERANCE, "the part turned for that face rests on the bed")

    # A round flat face, sharp or with a fillet round it bulging past its rim:
    # leaned 45 degrees, the part resting on its lowest point, the face at the
    # bed with a sharp rim and just above it with the fillet.
    plain = Part.makeCylinder(LEAN_DISC_RADIUS, LEAN_DISC_HEIGHT)
    rounded = plain.makeFillet(LEAN_DISC_FILLET,
                               [e for e in plain.Edges if e.BoundBox.ZMin > LEAN_DISC_HEIGHT - d.TOLERANCE])
    for name, disc, above in (("sharp", plain, False), ("filleted", rounded, True)):
        top = [i for i, f in enumerate(disc.Faces)
               if f.findPlane() is not None and f.BoundBox.ZMin > LEAN_DISC_HEIGHT - d.TOLERANCE][0]
        change, edge = quick_stands.stand_for_face(disc, top, p, d.TILT_ANGLE)
        leant = moved(disc, change)
        gap = leant.Faces[top].BoundBox.ZMin - leant.BoundBox.ZMin
        expect(edge is None and abs(leant.Faces[top].normalAt(0, 0).z + math.sqrt(0.5)) < 1e-6
               and abs(resting_height(leant)) < d.TOLERANCE and (gap > d.TOLERANCE) == above,
               "a round face of a %s disc leans 45 degrees, the part resting on its lowest point, the face %.2f mm "
               "above the bed" % (name, gap))
    # The side view looks along the line the face was leaned about, the disc
    # lying flat or turned first: the 45 degrees in profile.
    # Turning a shape keeps the order of its faces.
    top = [i for i, f in enumerate(plain.Faces)
           if f.findPlane() is not None and f.BoundBox.ZMin > LEAN_DISC_HEIGHT - d.TOLERANCE][0]
    for name, turn in (("lying", 0.0), ("turned", LEAN_DISC_TURN)):
        disc = plain.copy()
        disc.rotate(V(0, 0, 0), LEAN_DISC_TURN_AXIS, turn)
        plan = quick_stands.quick_plan(disc, [], [(disc.Faces[top], top)], p, d.TILT_ANGLE)
        seen = orient.side_direction(plan.change, plan.edge, plan.beside, plan.line)
        # Seen along that line, the face leans across the view, in profile.
        normal = moved(disc, plan.change).Faces[top].normalAt(0, 0)
        expect(seen is not None and abs(abs(seen.dot(orient.LEAN_LINE)) - 1) < d.TOLERANCE
               and abs(normal.dot(seen)) < d.TOLERANCE,
               "the side view of a %s disc leaned on a round face looks along the line it leans about: %s"
               % (name, seen))
    tiny = Part.makeCylinder(TINY_LEAN_DISC_RADIUS, LEAN_DISC_HEIGHT)
    top = [i for i, f in enumerate(tiny.Faces)
           if f.findPlane() is not None and f.BoundBox.ZMin > LEAN_DISC_HEIGHT - d.TOLERANCE][0]
    try:
        quick_stands.stand_for_face(tiny, top, p, d.TILT_ANGLE)
    except face_frame.FinError as error:
        expect("cannot stand" in str(error), "a round face too small for fins is refused: %s" % error)
    else:
        raise AssertionError("fins were planned under a round face too small for them")


def check_quick_plan():
    """Quick fins with the tilt edge, a chamfer or a fillet chosen."""
    p = FinParams()
    box = Part.makeBox(30, 20, 20)
    front = [i for i, f in enumerate(box.Faces) if f.BoundBox.YMax < d.TOLERANCE][0]
    short = [e for e in box.Faces[front].Edges if abs(e.Length - 20) < d.TOLERANCE][0]
    plan = quick_stands.quick_plan(box, [(short, None)], [(box.Faces[front], front)], p, d.TILT_ANGLE)
    stood = moved(box, plan.change)
    on_it = [e for e in stood.Edges if abs(e.Length - 20) < d.TOLERANCE and e.BoundBox.ZMax < d.TOLERANCE]
    expect(plan.number == front and on_it and abs(stood.Faces[front].normalAt(0, 0).z + math.sqrt(0.5)) < 1e-6,
           "a face with one of its edges stands on that edge, the face leaning 45 degrees")
    other = [e for e in box.Edges if not any(e.isSame(x) for x in box.Faces[front].Edges)][0]
    try:
        quick_stands.quick_plan(box, [(other, None)], [(box.Faces[front], front)], p, d.TILT_ANGLE)
    except orient.OrientError as error:
        expect("not an edge" in str(error), "an edge of another face is refused: %s" % error)
    else:
        raise AssertionError("an edge of another face was taken")

    bottom_front = [e for e in box.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE]
    chamfered = box.makeChamfer(EDGE_ROUND, bottom_front)
    side = [i for i, f in enumerate(chamfered.Faces) if f.BoundBox.YMax < d.TOLERANCE and f.BoundBox.ZLength > 10][0]
    bevel = [i for i, f in enumerate(chamfered.Faces) if abs(f.normalAt(0, 0).z + math.sqrt(0.5)) < 1e-6][0]
    plan = quick_stands.quick_plan(chamfered, [], [(chamfered.Faces[side], side), (chamfered.Faces[bevel], bevel)],
                               p, d.TILT_ANGLE)
    resting = moved(chamfered, plan.change)
    expect(plan.number == side and abs(resting.Faces[bevel].normalAt(0, 0).z + 1) < 1e-6,
           "a face, then a chamfer beside it: the part rests on the chamfer, fins under the face")
    alone = quick_stands.quick_plan(chamfered, [], [(chamfered.Faces[bevel], bevel)], p, d.TILT_ANGLE)
    expect(quick_stands.is_chamfer(chamfered, chamfered.Faces[bevel]) and alone.number != bevel
           and abs(moved(chamfered, alone.change).Faces[bevel].normalAt(0, 0).z + 1) < 1e-6,
           "a chamfer alone, however wide, carries the part instead of taking the fins")
    expect(not quick_stands.is_chamfer(box, box.Faces[front]), "a side of a box is no chamfer")
    uneven = box.makeChamfer(EDGE_ROUND, 2 * EDGE_ROUND, bottom_front)
    slope = [f for f in uneven.Faces if f.findPlane() is not None and -0.99 < f.normalAt(0, 0).z < -0.01
             and -0.99 < f.normalAt(0, 0).y < -0.01]
    expect(len(slope) == 1 and quick_stands.is_chamfer(uneven, slope[0]),
           "a chamfer of unequal widths, not at 45 degrees, is a chamfer too")

    filleted = box.makeFillet(EDGE_ROUND, bottom_front)
    fillet = [i for i, f in enumerate(filleted.Faces) if f.findPlane() is None][0]
    plan = quick_stands.quick_plan(filleted, [], [(filleted.Faces[fillet], fillet)], p, d.TILT_ANGLE)
    expect(abs(resting_height(moved(filleted, plan.change))) < d.TOLERANCE and plan.number != fillet,
           "a fillet alone carries the part, the fins go under a leaning face")
    beside = [i for i, f in enumerate(filleted.Faces) if f.findPlane() is not None
              and any(e.isSame(x) for e in f.Edges for x in filleted.Faces[fillet].Edges)
              and abs(f.normalAt(0, 0).x) < d.TOLERANCE]
    plan = quick_stands.quick_plan(filleted, [], [(filleted.Faces[i], i) for i in beside], p, d.TILT_ANGLE)
    expect(len(plan.beside) == 2 and abs(resting_height(moved(filleted, plan.change))) < d.TOLERANCE,
           "the two faces beside a fillet carry the part")


def regular_prism(sides, across=20.0, length=60.0):
    """A regular prism on the XY plane, its axis along Z."""
    corners = [App.Vector(across * math.cos(2 * math.pi * i / sides), across * math.sin(2 * math.pi * i / sides), 0)
               for i in range(sides)]
    return Part.Face(Part.makePolygon(corners + corners[:1])).extrude(App.Vector(0, 0, length))


def sides_of(shape):
    """The numbers of the faces of `shape` standing along Z."""
    return [i for i, f in enumerate(shape.Faces)
            if f.findPlane() is not None and abs(f.normalAt(0, 0).z) < d.TOLERANCE]


def check_prism_side():
    """Quick fins with the side of a regular prism selected alone."""
    p = FinParams()
    up = App.Vector(0, 0, 1)
    hexagon = regular_prism(6)
    axis = quick_stands.prism_axis(hexagon, hexagon.Faces[sides_of(hexagon)[0]])
    expect(axis is not None and axis.cross(up).Length < d.TOLERANCE, "a side of a hexagon prism: the axis of the prism")
    octagon = regular_prism(8)
    expect(all(quick_stands.prism_axis(octagon, octagon.Faces[i]) is not None for i in sides_of(octagon)),
           "every side of an octagon prism belongs to the prism")

    box = Part.makeBox(30, 30, 60)
    expect(all(quick_stands.prism_axis(box, f) is None for f in box.Faces), "a box is no prism of this kind")
    triangle = regular_prism(3)
    expect(all(quick_stands.prism_axis(triangle, f) is None for f in triangle.Faces), "nor is a triangular prism")
    upright_edges = [e for e in box.Edges if e.BoundBox.ZLength > 1]
    one_chamfer = box.makeChamfer(5, upright_edges[:1])
    four_chamfers = box.makeChamfer(5, upright_edges)
    for shape, what in ((one_chamfer, "one chamfered edge"), (four_chamfers, "four chamfered edges")):
        expect(all(quick_stands.prism_axis(shape, f) is None for f in shape.Faces), "%s: no prism" % what)
        expect(any(quick_stands.is_chamfer(shape, f) for f in shape.Faces), "%s: the chamfer stays one" % what)
    uneven = Part.Face(Part.makePolygon([App.Vector(*c) for c in
                                         ((30, 0, 0), (20, 20, 0), (-10, 20, 0), (-20, 0, 0),
                                          (-10, -10, 0), (20, -10, 0), (30, 0, 0))])).extrude(App.Vector(0, 0, 60))
    expect(all(quick_stands.prism_axis(uneven, f) is None for f in uneven.Faces), "an uneven hexagon: no prism")
    half = regular_prism(6).cut(Part.makeBox(100, 100, 100, App.Vector(-50, 0, -20)))
    expect(all(quick_stands.prism_axis(half, f) is None for f in half.Faces), "half a hexagon: the ring does not close")

    def corner_off(off):
        """A hexagon prism with one corner off by `off` mm."""
        corners = [App.Vector(20 * math.cos(math.pi * i / 3), 20 * math.sin(math.pi * i / 3), 0) for i in range(6)]
        corners[0] += App.Vector(off, 0, 0)
        return Part.Face(Part.makePolygon(corners + corners[:1])).extrude(App.Vector(0, 0, 60))

    near = corner_off(0.01)
    expect(all(quick_stands.prism_axis(near, near.Faces[i]) is not None for i in sides_of(near)),
           "a corner off by 0.01 mm: still a regular prism")
    far = corner_off(1.0)
    expect(all(quick_stands.prism_axis(far, f) is None for f in far.Faces), "a corner off by 1 mm: an uneven prism")
    # A pocket in the side facing +Y, whose apothem is the flat at y = 20 * sin(60).
    flat = 20 * math.sin(math.pi / 3)
    pocketed = hexagon.cut(Part.makeBox(6, 6, 10, App.Vector(-3, flat - 3, 25)))
    in_pocket = [i for i in sides_of(pocketed) if len(pocketed.Faces[i].Wires) == 2]
    whole = [i for i in sides_of(pocketed) if abs(pocketed.Faces[i].Area - hexagon.Faces[sides_of(hexagon)[0]].Area)
             < d.TOLERANCE]
    expect(len(in_pocket) == 1 and quick_stands.prism_axis(pocketed, pocketed.Faces[in_pocket[0]]) is not None,
           "the side with a pocket in it is a side of the prism")
    expect(whole and all(quick_stands.prism_axis(pocketed, pocketed.Faces[i]) is not None for i in whole),
           "the other sides pass the pocket wall over")
    # Wide and shallow, so its walls turn on from the side by less than the next side.
    recess = Part.Face(Part.makePolygon([App.Vector(-6, flat, 25), App.Vector(6, flat, 25), App.Vector(0, flat - 2, 25),
                                         App.Vector(-6, flat, 25)])).extrude(App.Vector(0, 0, 10))
    slanted = hexagon.cut(recess)
    in_slanted = [i for i in sides_of(slanted) if len(slanted.Faces[i].Wires) == 2]
    expect(len(in_slanted) == 1 and quick_stands.prism_axis(slanted, slanted.Faces[in_slanted[0]]) is not None,
           "a recess with slanted walls inside a side: the walls are passed over")
    corners = [App.Vector(20 * math.cos(math.pi * i / 3), 20 * math.sin(math.pi * i / 3), 0) for i in range(6)]
    with_halves = corners[:1] + [(corners[0] + corners[1]) * 0.5] + corners[1:]
    halves = Part.Face(Part.makePolygon(with_halves + with_halves[:1])).extrude(App.Vector(0, 0, 60))
    expect(len(sides_of(halves)) == 7 and all(quick_stands.prism_axis(halves, halves.Faces[i]) is not None
                                              for i in sides_of(halves)),
           "a side split in halves along the axis counts as one, on either half")
    slotted = hexagon.cut(Part.makeBox(4, 3, 80, App.Vector(-2, flat - 2, -10)))
    expect(all(quick_stands.prism_axis(slotted, f) is None for f in slotted.Faces),
           "a slot along the whole of a side: the ring runs into it")

    def expect_upright(shape, what, number=None):
        """The first way stands `shape` on an end, the side selected leaning 45
        degrees with the fins under it; the part laid on the side stays a way."""
        number = sides_of(shape)[0] if number is None else number
        plans = list(quick_stands.quick_plans(shape, [], [(shape.Faces[number], number)], p, d.TILT_ANGLE))
        change = plans[0].change
        expect(plans[0].number == number, "%s: the fins under the side selected" % what)
        expect(abs(math.degrees(math.acos(abs(change.Rotation.multVec(up).z))) - 45) < 1e-3,
               "%s: the axis stands 45 degrees from the bed" % what)
        expect(abs(moved(shape, change).Faces[number].normalAt(0, 0).z + math.sqrt(0.5)) < 1e-6,
               "%s: the side leans 45 degrees over the bed" % what)
        expect(len(plans) > 1 and all(plan.number != number for plan in plans[1:]) and all(
            abs(moved(shape, plan.change).Faces[number].normalAt(0, 0).z + 1) < 1e-6 for plan in plans[1:]),
               "%s: laid on the side stays a way, the fins under another face" % what)

    expect_upright(hexagon, "sharp hexagon prism")
    expect_upright(octagon, "octagon prism")
    turned = hexagon.common(Part.makeCylinder(19, 60))
    expect(quick_stands.prism_axis(turned, turned.Faces[sides_of(turned)[0]]) is None,
           "corners turned off along the sides: no ring, stands as any face does")
    groove = Part.makeCylinder(40, 3, App.Vector(0, 0, 30)).cut(Part.makeCylinder(16, 3, App.Vector(0, 0, 30)))
    expect_upright(hexagon.cut(groove), "hexagon with a groove round it")
    round_ended = (Part.makeCone(17, 25, 8).fuse(Part.makeCylinder(25, 44, App.Vector(0, 0, 8)))
                   .fuse(Part.makeCone(25, 17, 8, App.Vector(0, 0, 52))).removeSplitter())
    shank = hexagon.common(round_ended)
    expect_upright(shank, "shank chamfered at both ends, the side with no straight edge there")
    expect_upright(hexagon.cut(Part.makeCylinder(5, 80, App.Vector(0, 0, -10))), "hexagon with a bore")
    expect_upright(pocketed, "the side with a pocket in it", in_pocket[0])
    expect_upright(slanted, "the side with a slanted recess in it", in_slanted[0])
    expect_upright(halves, "a side split in halves, one half selected")

    two_points = Part.makeCone(0, 30, 30).fuse(Part.makeCone(30, 0, 30, App.Vector(0, 0, 30))).removeSplitter()
    pointed = hexagon.common(two_points)
    number = sides_of(pointed)[0]
    plans = list(quick_stands.quick_plans(pointed, [], [(pointed.Faces[number], number)], p, d.TILT_ANGLE))
    expect(plans and all(plan.number != number for plan in plans),
           "no flat end to stand on: laid on the side, as a chamfer")


def check_quick_plans():
    """The other ways Quick fins can stand a part, for the task panel to step to."""
    p = FinParams()
    box = Part.makeBox(30, 20, 20)
    front = [i for i, f in enumerate(box.Faces) if f.BoundBox.YMax < d.TOLERANCE][0]
    plans = list(quick_stands.quick_plans(box, [], [(box.Faces[front], front)], p, d.TILT_ANGLE))
    first = quick_stands.quick_plan(box, [], [(box.Faces[front], front)], p, d.TILT_ANGLE)
    expect(len(plans) == len(box.Faces[front].Edges) and plans[0].edge.isSame(first.edge)
           and all(plan.number == front for plan in plans)
           and [plan.edge.Length for plan in plans] == sorted((plan.edge.Length for plan in plans), reverse=True)
           and all(not a.edge.isSame(b.edge) for i, a in enumerate(plans) for b in plans[i + 1:]),
           "a face alone stands on each of its edges, the longest first, the fins always under it")
    expect(all(abs(moved(box, plan.change).Faces[front].normalAt(0, 0).z + math.sqrt(0.5)) < 1e-6
               and abs(resting_height(moved(box, plan.change))) < d.TOLERANCE for plan in plans),
           "on every edge the face leans 45 degrees and the part rests on the bed")

    bottom = [e for e in box.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]
    plans = list(quick_stands.quick_plans(box, [(bottom, None)], [], p, d.TILT_ANGLE))
    stood = moved(box, plans[0].change)
    expect(len(plans) > 1 and len({plan.number for plan in plans}) == len(plans)
           and all(plan.change.isSame(plans[0].change, d.TOLERANCE) for plan in plans)
           and plans[0].number == quick_stands.best_face(stood, p)
           and [stood.Faces[plan.number].Area for plan in plans]
           == sorted((stood.Faces[plan.number].Area for plan in plans), reverse=True),
           "an edge stands one way, the fins under each face that takes them, the largest first")

    short = [e for e in box.Faces[front].Edges if abs(e.Length - 20) < d.TOLERANCE][0]
    plans = list(quick_stands.quick_plans(box, [(short, None)], [(box.Faces[front], front)], p, d.TILT_ANGLE))
    expect(len(plans) == 1, "a face with one of its edges stands one way only")


def bridge(hanging):
    """A pillar on the bed with a beam across its top and `hanging`, a solid
    under the far end of the beam: a bridge for islands to hang from."""
    pillar = Part.makeBox(ISLAND_PILLAR, ISLAND_DEPTH, ISLAND_TOP)
    beam = Part.makeBox(ISLAND_SPAN, ISLAND_DEPTH, ISLAND_BEAM, V(0, 0, ISLAND_UNDER))
    return pillar.fuse([beam, hanging]).removeSplitter()


def stacked_bottoms(first_layer, layer):
    """The heights of COMB_TEETH bottoms in layers one above the other, each
    clear of the middles of the layers."""
    return [overhang.layer_middle(ISLAND_LAYER + step, first_layer, layer) + CLEAR_OF_MIDDLE
            for step in range(COMB_TEETH)]


def calls_counted(name, run):
    """What overhang.<name>() is called with while `run` runs, a tuple for
    each call, in their order, and what `run` returns."""
    calls = []
    real = getattr(overhang, name)

    def counted(*args):
        calls.append(args)
        return real(*args)

    setattr(overhang, name, counted)
    try:
        result = run()
    finally:
        setattr(overhang, name, real)
    return calls, result


def cuts_counted(run):
    """The heights overhang.faces_at() is asked to cut at while `run` runs,
    each once for each time it is asked, in rising order, and what `run`
    returns. How often the kernel cuts for them tells kernel_cuts()."""
    calls, result = calls_counted("faces_at", run)
    return [z for _, heights, *_ in calls for z in sorted(set(heights))], result


def kernel_cuts(run):
    """How many cuts the kernel makes for the layers of a part while `run`
    runs (overhang._cut_out()), and what `run` returns."""
    calls, result = calls_counted("_cut_out", run)
    return len(calls), result


def cuts_due(shape, heights):
    """How many cuts the kernel is to make of `shape` for `heights`: one for
    each batch they are cut in (overhang._batches()), of as many as its
    faces allow (overhang.cuts_together())."""
    return len(list(overhang._batches(sorted(set(heights)), overhang.cuts_together(len(shape.Faces)))))


def check_faces_at():
    """The faces where several planes cut a shape, cut a few heights at a
    time: every kind of heights the tables of overhang._batches() and
    overhang.faces_at() name."""
    first, layer = d.FIRST_LAYER_HEIGHT, d.LAYER_HEIGHT
    cutter = overhang.SECTION_CUT_HEIGHT
    apart = [CUTS_LOW + step * layer for step in range(overhang.CUTS_MOST)]
    lowered = apart[1] - overhang.SUPPORT_CUT_DROP

    def batches(heights, most=overhang.CUTS_MOST):
        return list(overhang._batches(sorted(heights), most))

    expect(batches([]) == [] and batches(apart) == [apart]
           and batches(apart + [apart[-1] + layer]) == [apart, [apart[-1] + layer]]
           and batches(apart, CUTS_FEW) == [apart[start:start + CUTS_FEW] for start in range(0, len(apart), CUTS_FEW)],
           "heights a cutter and more apart are cut together, as many at a time as said and no more")
    near = batches(apart[:2] + [lowered, apart[0] + BESIDE])
    gaps = [later - earlier for batch in near for earlier, later in zip(batch, batch[1:])]
    expect(len(near) == 2 and all(gap >= cutter for gap in gaps),
           "two heights nearer than a cutter is high, as a middle and the cut lowered under it, or two a "
           "rounding apart, are never cut together: %s" % near)

    bottoms = stacked_bottoms(first, layer)
    teeth = [Part.makeBox(COMB_TOOTH, ISLAND_DEPTH, ISLAND_UNDER - ISLAND_LOW,
                          V(ISLAND_PILLAR + COMB_TOOTH * (1 + 2 * step), 0, bottom))
             for step, bottom in enumerate(bottoms)]
    comb = bridge(teeth[0].fuse(teeth[1:]))
    middles = [overhang.layer_middle(ISLAND_LAYER + step, first, layer) for step in range(COMB_TEETH + 1)]
    under_beam = ISLAND_UNDER
    asked = middles + [middles[1] - overhang.SUPPORT_CUT_DROP, under_beam, ISLAND_TOP + layer, middles[0]]

    def told(faces):
        return None if faces is None else (len(faces), round(sum(face.Area for face in faces), CUTS_DIGITS))

    alone = {z: told(overhang.layer_faces(comb, z)) for z in asked}
    single, together = calls_counted("layer_faces", lambda: overhang.faces_at(comb, asked))
    expect(overhang.faces_at(comb, []) == {} and sorted(together) == sorted(set(asked)) and len(single) == 1
           and all(told(together[z]) == alone[z] for z in asked) and told(together[ISLAND_TOP + layer]) == (0, 0.0)
           and told(together[under_beam])[0] == 1 + COMB_TEETH,
           "the faces of several heights cut together are those of each cut alone, each height once, the one "
           "too near another cut by itself, none "
           "above the part, and a face of the part lying in the plane of a height among those of that height")
    single, one = calls_counted("layer_faces", lambda: overhang.faces_at(comb, middles[:1]))
    expect(len(single) == 1 and told(one[middles[0]]) == alone[middles[0]], "one height is cut alone")

    most = overhang.CUT_FACES_MOST
    expect([overhang.cuts_together(count) for count in (1, most // overhang.CUTS_MOST, most // 2, most // 2 + 1, most)]
           == [overhang.CUTS_MOST, overhang.CUTS_MOST, 2, 1, 1],
           "a shape is cut at as many heights at a time as can be, at fewer with more faces, at two up to "
           "half the most faces times heights, and one by one past that")
    cut_out = overhang._cut_out

    def without(compounds):
        """overhang._cut_out() that gives `compounds`, called with what it is
        asked of, for the cutters of several heights, and cuts a single one."""
        def cut(shape, cutters):
            return compounds(shape, cutters) if cutters.ShapeType == "Compound" else cut_out(shape, cutters)
        return cut

    def raising(shape, cutters):
        raise Part.OCCError("no cut of several")

    try:
        overhang.CUT_FACES_MOST = 2 * len(comb.Faces)
        kernel, by_two = kernel_cuts(lambda: overhang.faces_at(comb, middles))
        expect(kernel == math.ceil(len(middles) / 2) and all(told(by_two[z]) == alone[z] for z in middles),
               "on a shape of half as many faces as a cut may take, two heights are cut at a time: %d cuts of "
               "the kernel for %d heights" % (kernel, len(middles)))
        overhang.CUT_FACES_MOST = len(comb.Faces) - 1
        kernel, each = kernel_cuts(lambda: overhang.faces_at(comb, middles))
        expect(kernel == len(middles) and all(told(each[z]) == alone[z] for z in middles),
               "on a shape of more faces than a cut of several is worth, every height is cut alone")
        overhang.CUT_FACES_MOST = most
        for failing, why in ((raising, "the kernel cannot make"), (lambda shape, cutters: None, "comes out null")):
            overhang._cut_out = without(failing)
            single, each = calls_counted("layer_faces", lambda: overhang.faces_at(comb, middles))
            expect(len(single) == len(middles) and all(told(each[z]) == alone[z] for z in middles),
                   "a cut of several that %s has its heights cut one by one" % why)
    finally:
        overhang.CUT_FACES_MOST = most
        overhang._cut_out = cut_out

    # One height at a time and several together find the same.
    stairs = stairs_under_slab(first, layer)
    together = (overhang.islands(comb, first, layer),
                find_bridges(stairs, first, layer, d.BEAD_WIDTH, limits.Limits()))
    try:
        overhang.CUTS_MOST = 1
        kernel, alone_found = kernel_cuts(lambda: (
            overhang.islands(comb, first, layer), find_bridges(stairs, first, layer, d.BEAD_WIDTH, limits.Limits())))
    finally:
        overhang.CUTS_MOST = CUTS_AS_SET

    def island_points(found):
        return sorted(tuple(round(value, CUTS_DIGITS) for value in island.point) for island in found)

    def bridge_spans(found):
        return [(spanning.faces, spanning.covered, round(spanning.span, CUTS_DIGITS), spanning.level)
                for spanning in found]

    expect(island_points(together[0]) == island_points(alone_found[0]) and len(together[0]) == COMB_TEETH
           and bridge_spans(together[1]) == bridge_spans(alone_found[1]) and together[1],
           "cut one height at a time or several together, the islands lie at the same points and the bridges "
           "span the same faces as far: %s, %s" % (island_points(together[0]), bridge_spans(together[1])))


def stairs_under_slab(first_layer, layer):
    """A slab on two piers with COMB_TEETH steps under it, side by side
    across the gap, each a layer higher than the last and clear of the
    middles of the layers."""
    bottoms = stacked_bottoms(first_layer, layer)
    width, height = GAP_CRITICAL / COMB_TEETH, bottoms[-1] + SLAB
    steps = [Part.makeBox(width, PIER[1], height - bottom, V(PIER[0] + step * width, 0, bottom))
             for step, bottom in enumerate(bottoms)]
    return piers(GAP_CRITICAL, height=height).fuse(steps).removeSplitter()


def check_cut_heights():
    """The layer a point starts to print in and the heights the layers are cut
    at, at every kind of height the tables of overhang.layer_of() and
    overhang.LayerCuts name, with the first layer as high as the others,
    higher and lower."""
    for first, layer in LAYERINGS:
        def cuts_of(*starts):
            return overhang.LayerCuts(list(starts), first, layer)

        def layer_of(height):
            return overhang.layer_of(height, first, layer)

        bed_most = first / 2 + d.TOLERANCE
        on_bed = (0.0, first / 2, bed_most - BESIDE)
        expect(all(layer_of(height) == 0 and cuts_of(*on_bed).at(height) is None for height in on_bed),
               "first layer %.2f mm: up to its middle and the tolerance above, the bed carries a point, and "
               "nothing is cut for it" % first)
        lowest = cuts_of(bed_most + BESIDE).at(bed_most + BESIDE)
        expect(lowest.number == 1 and lowest.here == overhang.layer_middle(1, first, layer)
               and lowest.below == first / 2,
               "first layer %.2f mm: just above that, a point starts in layer 1, carried by the first, which "
               "is cut at its middle, never lower: %s" % (first, lowest))
        for number in CUT_LAYERS:
            middle = overhang.layer_middle(number, first, layer)
            upper = overhang.layer_middle(number + 1, first, layer)
            lowered = middle - overhang.SUPPORT_CUT_DROP
            clear, higher = middle + CLEAR_OF_MIDDLE, upper + CLEAR_OF_MIDDLE
            above = [layer_of(middle + offset) for offset in
                     (-d.TOLERANCE + BESIDE, -d.TOLERANCE / 2, 0.0, d.TOLERANCE / 2, CLEAR_OF_MIDDLE)]
            below = [layer_of(middle + offset) for offset in
                     (-d.TOLERANCE - BESIDE, -1.5 * d.TOLERANCE, -CLEAR_OF_MIDDLE)]
            expect(above == [number + 1] * len(above) and below == [number] * len(below),
                   "first layer %.2f mm, middle of layer %d: from the tolerance below it a point counts to "
                   "the layer above, lower to that layer: %s, %s" % (first, number, above, below))
            plain = cuts_of().at(clear)
            expect(plain.number == number + 1 and plain.here == upper and plain.below == middle,
                   "first layer %.2f mm, middle of layer %d: with nothing starting near it, a layer is cut at "
                   "its middle and what carries it at the middle below, whether its height is among the "
                   "starts or not: %s" % (first, number, plain))
            near = [cuts_of(middle + offset).at(clear) for offset in
                    (-d.TOLERANCE + BESIDE, 0.0, overhang.NEAR_MIDDLE - BESIDE)]
            expect(all(at.here == upper and abs(at.below - lowered) < BESIDE for at in near),
                   "first layer %.2f mm, middle of layer %d: with a point starting near that middle, what "
                   "carries the layer above is cut the drop under it, for every point of that layer: %s"
                   % (first, number, near))
            farther = cuts_of(middle + overhang.NEAR_MIDDLE + BESIDE).at(clear)
            expect(farther.below == middle,
                   "first layer %.2f mm, middle of layer %d: a point starting farther above that middle leaves "
                   "the support of its layer at the middle itself: %s" % (first, number, farther))
            # Right where the layer changes, the tolerance below the middle: a
            # start seen a rounding below it lowers the layer above all the
            # same, for another copy that sees it a rounding above.
            edge = middle - d.TOLERANCE
            across = [cuts_of(edge + off).at(edge + BESIDE) for off in (-overhang.LAYER_EDGE / 2, 0.0, BESIDE)]
            expect(all(at.number == number + 1 and abs(at.below - lowered) < BESIDE for at in across),
                   "first layer %.2f mm, middle of layer %d: a point starting right where the layer changes "
                   "lowers the support of the layer above on whichever side of it a rounding puts it: %s"
                   % (first, number, across))
            lower = cuts_of(middle - 1.5 * d.TOLERANCE).at(clear)
            expect(lower.below == middle,
                   "first layer %.2f mm, middle of layer %d: a point starting more than that below the "
                   "middle, in the layer of it, leaves the layer above carried by the cut at the middle, "
                   "where its slice carries: %s" % (first, number, lower))
            apart = cuts_of(clear, higher)
            expect(apart.at(higher).number == apart.at(clear).number + 1
                   and apart.at(higher).below == apart.at(clear).here,
                   "first layer %.2f mm, middle of layer %d: the support of a layer is the cut of the layer "
                   "below, the very same height, where no point starts near it: %s, %s"
                   % (first, number, apart.at(clear), apart.at(higher)))


def check_starts():
    """What overhang.Starts tells of a shape, and when it asks the shape."""
    empty = overhang.Starts(Part.Shape())
    expect(empty.bed is None and empty.points == [] and empty.down == [] and empty.heights == [],
           "an empty shape has no bed, no lowest points, no faces facing down and no heights")
    table = piers(GAP_CRITICAL)
    under = next(number for number, face in enumerate(table.Faces, 1)
                 if face.BoundBox.ZLength < d.TOLERANCE and abs(face.BoundBox.ZMin - PIER[2]) < d.TOLERANCE)
    top = next(number for number, face in enumerate(table.Faces, 1)
               if abs(face.BoundBox.ZMin - (PIER[2] + SLAB)) < d.TOLERANCE)
    sampled, (meshed, starts) = calls_counted("facing_down", lambda: calls_counted(
        "_lowest_points", lambda: overhang.Starts(table)))
    expect(not sampled and not meshed, "a Starts never asked neither meshes its shape nor samples its faces")
    meshed, lowest = calls_counted("_lowest_points", lambda: dict(starts.lowest))
    expect(not meshed and abs(lowest[under] - PIER[2]) < d.TOLERANCE and top not in lowest,
           "asked for its faces alone it does not mesh: the underside of a slab on piers starts at its "
           "height, its top starts nothing: %s" % lowest)
    sampled, (meshed, heights) = calls_counted("facing_down", lambda: calls_counted(
        "_lowest_points", lambda: (starts.heights, starts.points, starts.down, starts.heights)[0]))
    expect(not sampled and len(meshed) == 1 and any(abs(height - PIER[2]) < d.TOLERANCE for height in heights),
           "asked for all, it meshes once and samples no face again; the height of the underside, which "
           "holds no lowest point, is among its heights: %d meshes" % len(meshed))
    starts.let_go()
    expect(starts.heights == heights, "let go of its shape, it still tells what it worked out")
    unasked = overhang.Starts(table)
    unasked.let_go()
    try:
        unasked.points
    except ValueError as error:
        expect("lend" in str(error), "let go of before it was asked, it says it needs a shape: %s" % error)
    else:
        raise AssertionError("Starts without a shape gave points")
    unasked.lend(table.copy())
    expect(len(unasked.points) == len(starts.points) and unasked.lowest == lowest,
           "lent another copy of the shape, it works out on that what it was not asked before")

    # The cuts of its layers, kept for the checks of the part to share.
    apart = [overhang.layer_middle(number, d.FIRST_LAYER_HEIGHT, d.LAYER_HEIGHT) for number in STOCK_LAYERS]
    stock = overhang.Starts(table)
    first_cuts, cut = kernel_cuts(lambda: stock.cuts(apart[:2]))
    kept_cuts, kept = kernel_cuts(lambda: stock.cuts(apart[:2]))
    more_cuts, more = kernel_cuts(lambda: stock.cuts(apart))

    def same_faces(given, as_before):
        return len(given) == len(as_before) and all(face.isSame(before) for face, before in zip(given, as_before))

    expect(first_cuts == 1 and kept_cuts == 0 and more_cuts == 1 and stock.cuts([]) == {}
           and all(same_faces(kept[z], cut[z]) and same_faces(more[z], cut[z]) for z in apart[:2])
           and len(more) == len(apart) and all(len(more[z]) == 2 for z in apart),
           "heights are cut together the first time they are asked, given as kept after, and of heights asked "
           "in part before only the others are cut: %d, %d and %d cuts of the kernel"
           % (first_cuts, kept_cuts, more_cuts))
    more[apart[0]].append(None)
    more[apart[1]].reverse()
    expect(all(kept[z] is not cut[z] and same_faces(stock.cuts([z])[z], cut[z]) for z in apart[:2]),
           "the lists of faces given are each its own: changed by a caller, what is kept stays as it was")
    stock.let_go()
    from_stock, _ = kernel_cuts(lambda: stock.cuts(apart))
    try:
        stock.cuts([apart[-1] + d.LAYER_HEIGHT])
    except ValueError as error:
        expect(from_stock == 0 and "lend" in str(error),
               "let go of its shape, it still gives the cuts it keeps, and says it needs a shape for another: "
               "%s" % error)
    else:
        raise AssertionError("Starts without a shape cut a height it did not keep")
    stock.lend(table.copy())
    on_copy, _ = kernel_cuts(lambda: stock.cuts([apart[-1] + d.LAYER_HEIGHT]))
    stock.drop_cuts()
    anew, _ = kernel_cuts(lambda: stock.cuts(apart))
    expect(on_copy == 1 and anew == 1,
           "lent another copy of the shape, it cuts what it lacks on that; its cuts dropped, it cuts anew")
    most = overhang.CUT_EDGES_KEPT
    one_height = sum(len(face.Edges) for face in cut[apart[0]])
    try:
        # Room for the faces of one height, not of two; then for none at all.
        overhang.CUT_EDGES_KEPT = one_height
        full = overhang.Starts(table)
        full.cuts(apart)
        beyond = [kernel_cuts(lambda: full.cuts(apart))[0] for _ in range(2)]
        lowest_kept, _ = kernel_cuts(lambda: full.cuts(apart[:1]))
        overhang.CUT_EDGES_KEPT = one_height - 1
        none = overhang.Starts(table)
        none.cuts(apart)
        nothing_kept = (none._cuts, none._edges_kept)
        # Without room, each check still cuts a height once: the islands, then the
        # bridges, of a block hanging from a beam, which is an island and carries a bridge.
        hung = bridge(Part.makeBox(ISLAND_BLOCK, ISLAND_DEPTH, ISLAND_UNDER - ISLAND_LOW,
                                   V(ISLAND_SPAN - ISLAND_BLOCK, 0, ISLAND_LOW)))
        bare = overhang.Starts(hung)
        first_check, (asked, _) = kernel_cuts(lambda: cuts_counted(
            lambda: overhang.islands(hung, d.FIRST_LAYER_HEIGHT, d.LAYER_HEIGHT, bare)))
        second_check, (asked_again, spans) = kernel_cuts(lambda: cuts_counted(lambda: find_bridges(
            hung, d.FIRST_LAYER_HEIGHT, d.LAYER_HEIGHT, d.BEAD_WIDTH, limits.Limits(), starts=bare)))
    finally:
        overhang.CUT_EDGES_KEPT = most
    expect(beyond == [1, 1] and lowest_kept == 0 and nothing_kept == ({}, 0),
           "a height whose faces would take what is kept past the most edges it may keep is given and not "
           "kept, cut anew each time, be it the first; what fitted before is still given")
    expect(len(spans) == 1 and first_check == cuts_due(hung, asked) > 0 and second_check == cuts_due(hung, asked_again)
           and len(asked_again) == len(set(asked_again)) > 0,
           "with no room to keep cuts, each check cuts the heights it asks for once: %d cuts for %d heights of "
           "the islands, %d for %d of the bridges" % (first_check, len(asked), second_check, len(asked_again)))

    # Faces kept are as they were cut once the islands and the bridges took them.
    shared = overhang.Starts(hung)
    overhang.islands(hung, d.FIRST_LAYER_HEIGHT, d.LAYER_HEIGHT, shared)

    def as_cut(starts):
        return {z: None if faces is None else [(face.hashCode(), round(face.Area, CUTS_DIGITS), face.BoundBox.ZMin)
                                               for face in faces] for z, faces in starts._cuts.items()}

    before = as_cut(shared)
    spans = find_bridges(hung, d.FIRST_LAYER_HEIGHT, d.LAYER_HEIGHT, d.BEAD_WIDTH, limits.Limits(), starts=shared)
    overhang.islands(hung, d.FIRST_LAYER_HEIGHT, d.LAYER_HEIGHT, shared)
    after = as_cut(shared)
    expect(len(spans) == 1 and all(after[z] == before[z] for z in before) and len(after) >= len(before) > 0,
           "the faces kept are as they were cut after the islands and the bridges took them: %d heights kept"
           % len(after))


def check_islands():
    """Where a part would start printing in the air, as a slicer finds it."""
    first, layer = d.FIRST_LAYER_HEIGHT, d.LAYER_HEIGHT
    box = Part.makeBox(30, 20, 20)
    expect(overhang.islands(box, first, layer) == [], "a box lying on the bed has no island")
    bottom = [e for e in box.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]
    standing = moved(box, orient.tilt(box, bottom, d.TILT_ANGLE))
    expect(overhang.islands(standing, first, layer) == [], "a box standing on an edge has no island")

    block_x = ISLAND_SPAN * 3 / 4
    block = Part.makeBox(ISLAND_BLOCK, ISLAND_DEPTH, ISLAND_UNDER - ISLAND_LOW,
                         V(block_x, 0, ISLAND_LOW))
    found = overhang.islands(bridge(block), first, layer)
    expect(len(found) == 1 and abs(found[0].point.z - ISLAND_LOW) < d.TOLERANCE
           and block_x - d.TOLERANCE <= found[0].point.x,
           "a block hanging under a bridge is one island, at its bottom: %s" % [i.point for i in found])
    piece = found[0].first.BoundBox if found and found[0].first else None
    expect(piece is not None and abs(piece.XLength - ISLAND_BLOCK) < d.TOLERANCE
           and abs(piece.ZMin - ISLAND_LOW) < d.TOLERANCE and piece.ZLength <= first + layer,
           "its first layer in the air is the whole bottom of the block, a layer thick: %s" % piece)
    # The layers are cut at their middles: a bottom right on one, beside it or
    # within the tolerance of it, is found all the same.
    middle = overhang.layer_middle(ISLAND_LAYER, first, layer)
    for low in (middle + offset for offset in MIDDLE_OFFSETS):
        hanging = Part.makeBox(ISLAND_BLOCK, ISLAND_DEPTH, ISLAND_UNDER - low, V(block_x, 0, low))
        found = overhang.islands(bridge(hanging), first, layer)
        expect(len(found) == 1 and abs(found[0].point.z - low) < d.TOLERANCE,
               "a block hanging with its bottom at %.5f mm, the middle of a layer at %.2f mm, is one island: %s"
               % (low, middle, [i.point for i in found]))
    second = Part.makeBox(ISLAND_SPAN / 8, ISLAND_DEPTH, ISLAND_UNDER - ISLAND_LOW,
                          V(ISLAND_SPAN * 3 / 8, 0, ISLAND_LOW))
    expect(len(overhang.islands(bridge(block.fuse(second)), first, layer)) == 2,
           "two blocks hanging side by side are two islands")
    # Blocks whose bottoms lie in layers one above the other, clear of their
    # middles: the cut of each layer is what carries the next, so each of
    # their layers is cut once, and the layer below the lowest. The underside
    # of the beam they hang from starts a layer of its own, far above.
    for first_height, layer_height in LAYERINGS:
        bottoms = stacked_bottoms(first_height, layer_height)
        teeth = [Part.makeBox(COMB_TOOTH, ISLAND_DEPTH, ISLAND_UNDER - ISLAND_LOW,
                              V(ISLAND_PILLAR + COMB_TOOTH * (1 + 2 * step), 0, bottom))
                 for step, bottom in enumerate(bottoms)]
        comb = bridge(teeth[0].fuse(teeth[1:]))
        kernel, (cut_at, hanging) = kernel_cuts(
            lambda: cuts_counted(lambda: overhang.islands(comb, first_height, layer_height)))
        for_teeth = [z for z in cut_at if z < ISLAND_UNDER - layer_height]
        expect(len(hanging) == COMB_TEETH and len(for_teeth) == COMB_TEETH + 1
               and kernel == cuts_due(comb, cut_at) < len(cut_at),
               "first layer %.2f mm: %d blocks hanging in layers one above the other are %d islands, found with "
               "each of their layers asked for once and the one below the lowest, in a cut of the kernel for "
               "each batch of them and no more: "
               "%d heights for them, %d cuts in all"
               % (first_height, COMB_TEETH, len(hanging), len(for_teeth), kernel))

    under = ISLAND_UNDER
    corners = [V(block_x, 0, under), V(ISLAND_SPAN, 0, under), V(block_x + ISLAND_SPAN / 8, 0, ISLAND_LOW)]
    ridge = Part.Face(Part.makePolygon(corners + corners[:1])).extrude(V(0, ISLAND_DEPTH, 0))
    found = overhang.islands(bridge(ridge), first, layer)
    expect(len(found) == 1 and abs(found[0].point.z - ISLAND_LOW) < d.TOLERANCE,
           "a ridge pointing down under a bridge is one island, on the ridge: %s" % [i.point for i in found])
    piece = found[0].first.BoundBox if found and found[0].first else None
    expect(piece is not None and abs(piece.YLength - ISLAND_DEPTH) < d.TOLERANCE
           and piece.XLength < 2 * layer and abs(piece.ZMin - ISLAND_LOW) < d.TOLERANCE,
           "its first layer in the air is a thin band along the whole ridge: %s" % piece)

    mushroom = Part.makeCylinder(ISLAND_STEM, ISLAND_TOP).fuse(
        Part.makeCylinder(ISLAND_CAP, ISLAND_BEAM, V(0, 0, ISLAND_TOP))).removeSplitter()
    expect(overhang.islands(mushroom, first, layer) == [], "the cap of a mushroom rests on its stem")
    holed = box.cut(Part.makeCylinder(ISLAND_STEM, 30, V(0, 10, 10), V(1, 0, 0)))
    expect(overhang.islands(holed, first, layer) == [], "the top of a hole through a box is no island")
    floating = Part.makeCompound([box, Part.makeBox(5, 5, 5, V(40, 0, ISLAND_LOW))])
    expect(len(overhang.islands(floating, first, layer)) == 1, "a solid floating above the bed is an island")
    low = Part.makeCompound([box, Part.makeBox(5, 5, 5, V(40, 0, first / 4))])
    expect(overhang.islands(low, first, layer) == [], "a lowest point in the first layer rests on the bed")
    expect(overhang.islands(Part.Shape(), first, layer) == [], "an empty shape has no island said, nothing raised")


def check_island_boxes():
    """The lowest points of a part and the sections of its layers, sorted by their boxes before
    the kernel is asked: the islands are those found asking it of every section."""
    first, layer = d.FIRST_LAYER_HEIGHT, d.LAYER_HEIGHT
    height = ISLAND_UNDER - ISLAND_LOW

    def told(found):
        return [(tuple(round(value, CUTS_DIGITS) for value in island.point),
                 None if island.first is None else round(island.first.Volume, CUTS_DIGITS)) for island in found]

    def unsorted(run):
        """What `run` returns with every section asked of the kernel, none turned away by its box."""
        real = overhang._holding, overhang._meeting
        overhang._holding = lambda boxes, x, y: list(range(len(boxes)))
        overhang._meeting = lambda boxes, box: list(range(len(boxes)))
        try:
            return run()
        finally:
            overhang._holding, overhang._meeting = real

    # Round teeth: the mesh of a round bottom has many lowest points, each of them a point to
    # start from, in layers one above the other.
    bottoms = stacked_bottoms(first, layer)
    teeth = [Part.makeCylinder(COMB_TOOTH / 2, ISLAND_UNDER - bottom,
                               V(ISLAND_PILLAR + COMB_TOOTH * (1.5 + 2 * step), ISLAND_DEPTH / 2, bottom))
             for step, bottom in enumerate(bottoms)]
    comb = bridge(Part.makeCompound(teeth))
    points = len(overhang.Starts(comb).points)
    asked, found = calls_counted("_overlap", lambda: overhang.islands(comb, first, layer))
    asked_all, found_all = unsorted(lambda: calls_counted("_overlap", lambda: overhang.islands(comb, first, layer)))
    expect(points > COMB_TEETH * COMB_TEETH and len(found) == COMB_TEETH and told(found) == told(found_all)
           and len(asked) <= len(asked_all),
           "round blocks hanging in layers one above the other, %d lowest points between them: the islands "
           "found with the boxes sorted are those found asking the kernel of every section, in the same "
           "order, with the same first layers: %s" % (points, told(found)))

    # A point in the box of a section, yet far from it: a small block in the corner of an L, both
    # hanging at one height. Whichever is come to first, each is an island at a point of its own.
    left = ISLAND_PILLAR + COMB_TOOTH
    angle = Part.makeBox(ISLAND_SPAN / 2, COMB_TOOTH, height, V(left, 0, ISLAND_LOW)).fuse(
        Part.makeBox(COMB_TOOTH, ISLAND_DEPTH, height, V(left, 0, ISLAND_LOW))).removeSplitter()
    small = Part.makeBox(COMB_TOOTH, COMB_TOOTH, height,
                         V(left + ISLAND_SPAN / 4, ISLAND_DEPTH - 2 * COMB_TOOTH, ISLAND_LOW))
    hung = bridge(Part.makeCompound([angle, small]))
    for order, what in ((list, "as they come"), (lambda points: list(reversed(points)), "the other way round")):
        starts = overhang.Starts(hung)
        starts._points = order(starts.points)
        found = overhang.islands(hung, first, layer, starts)
        on_own = [island.first is not None
                  and island.first.distToShape(Part.Vertex(island.point))[0] < d.TOLERANCE for island in found]
        areas = sorted(round(island.first.Volume / (island.first.BoundBox.ZLength or 1)) for island in found
                       if island.first is not None)
        expect(len(found) == 2 and all(on_own) and areas == sorted(round(each.Volume / height)
                                                                     for each in (angle, small)),
               "a small block in the corner of an L, its points in the box of the L yet far from it, the "
               "points taken %s: two islands, each at a point of its own: %s" % (what, told(found)))

    # The edges of a box count to it, as BoundBox has it; no boxes hold and meet nothing.
    box = App.BoundBox(0, 0, 0, 1, 1, 1)
    flat = overhang._flat([box])
    for x in (0.0, 1.0, 0.5, 1.0 + BESIDE, -BESIDE):
        expect((overhang._holding(flat, x, 0.5) == [0]) == box.isInside(V(x, 0.5, 0.5))
               and (overhang._holding(flat, 0.5, x) == [0]) == box.isInside(V(0.5, x, 0.5)),
               "a point at %r along a box from 0 to 1 lies in it as BoundBox says: %s"
               % (x, box.isInside(V(x, 0.5, 0.5))))
    for low in (1.0, 1.0 + BESIDE, 1.0 - BESIDE, -1.0, -1.0 - BESIDE):
        other = App.BoundBox(low, 0, 0, low + 1, 1, 1)
        expect((overhang._meeting(flat, overhang._flat([other])[0]) == [0]) == box.intersect(other),
               "a box from %r beside one from 0 to 1 meets it as BoundBox says: %s" % (low, box.intersect(other)))
    none = overhang._flat([])
    expect(none.shape == (0, 4) and overhang._holding(none, 0, 0) == [] and overhang._meeting(none, flat[0]) == []
           and overhang._holding(overhang._flat([box, box]), 0.5, 0.5) == [0, 1],
           "no boxes hold no point and meet no box; boxes holding a point are given by number, rising")


def check_first_layers():
    """The first layers of the islands of a part, cut out of it several in one cut."""
    first, layer = d.FIRST_LAYER_HEIGHT, d.LAYER_HEIGHT
    height = ISLAND_UNDER - ISLAND_LOW
    lefts = [ISLAND_PILLAR + COMB_TOOTH * (1 + 2 * step) for step in range(COMB_TEETH)]
    comb = bridge(Part.makeCompound([Part.makeBox(COMB_TOOTH, ISLAND_DEPTH, height, V(left, 0, ISLAND_LOW))
                                     for left in lefts]))

    def cut_out(run=lambda: overhang.islands(comb, first, layer)):
        """How many prisms each cut of the kernel is asked for, and the islands."""
        calls, found = calls_counted("_cut_within", run)
        return [len(batch) for _, batch in calls], found

    def whole(found):
        """Whether the islands lie at the blocks, in the order found, each with its first layer."""
        return (len(found) == COMB_TEETH and all(
            island.first is not None and abs(island.first.BoundBox.XLength - COMB_TOOTH) < d.TOLERANCE
            and abs(island.first.BoundBox.ZMin - ISLAND_LOW) < d.TOLERANCE
            and island.first.BoundBox.XMin - d.TOLERANCE <= island.point.x <= island.first.BoundBox.XMax + d.TOLERANCE
            for island in found))

    asked, found = cut_out()
    expect(asked == [COMB_TEETH] and whole(found),
           "blocks hanging side by side have their first layers cut in one cut of the kernel, each island its "
           "own, in the order found: %s prisms a cut, %s" % (asked, [i.first and i.first.BoundBox for i in found]))
    alone = [island.first.Volume for island in found if island.first is not None]

    real_most = overhang.FIRST_LAYERS_MOST
    overhang.FIRST_LAYERS_MOST = COMB_TEETH - 1
    try:
        asked, found = cut_out()
    finally:
        overhang.FIRST_LAYERS_MOST = real_most
    expect(asked == [COMB_TEETH - 1, 1] and whole(found),
           "more islands than are cut together are cut in several cuts, none of more: %s" % asked)

    # A cut of several the kernel cannot make: its islands are cut one by one.
    real = overhang._cut_within
    overhang._cut_within = lambda part, batch: real(part, batch) if len(batch) == 1 else None
    try:
        asked, found = cut_out()
    finally:
        overhang._cut_within = real
    expect(asked == [COMB_TEETH] + [1] * COMB_TEETH and whole(found)
           and all(abs(island.first.Volume - volume) < d.TOLERANCE for island, volume in zip(found, alone)),
           "a cut of several the kernel cannot make is taken one island at a time, each first layer as cut "
           "together: %s" % asked)
    overhang._cut_within = lambda part, batch: None
    try:
        found = overhang.islands(comb, first, layer)
    finally:
        overhang._cut_within = real
    expect(len(found) == COMB_TEETH and all(island.first is None for island in found),
           "islands the kernel cannot cut alone either are said without a first layer")

    # Straight from outlines: a prism holding nothing, a shell, an outline no prism is made of.
    box = Part.makeBox(ISLAND_BLOCK, ISLAND_DEPTH, ISLAND_BEAM)
    outline = [face for face in box.Faces if face.BoundBox.ZMax < d.TOLERANCE][0]
    beside = outline.translated(V(2 * ISLAND_BLOCK, 0, 0))
    asked, firsts = cut_out(lambda: overhang._first_layers(box, [(outline, 0, layer), (beside, 0, layer)]))
    expect(asked == [2] and firsts[0] is not None and abs(firsts[0].Volume - outline.Area * layer) < d.TOLERANCE
           and firsts[1] is None,
           "a prism holding nothing of the part gives no first layer and is not cut again alone, the one "
           "beside it is: %s cuts, %s" % (asked, firsts))
    asked, firsts = cut_out(lambda: overhang._first_layers(box.Shells[0], [(outline, 0, layer)]))
    expect(asked == [1] and firsts == [None], "a part that is a shell has no solid in a prism, so no first layer")
    asked, firsts = cut_out(lambda: overhang._first_layers(box, [(Part.Shape(), 0, layer), (outline, 0, layer)]))
    expect(asked == [1] and firsts[0] is None and firsts[1] is not None,
           "an outline no prism can be made of gives no first layer, the others are cut: %s" % firsts)
    expect(overhang._first_layers(box, []) == [] and cut_out(lambda: overhang._first_layers(box, []))[0] == [],
           "no island, nothing cut")

    # Prisms too near each other never share a cut: the same outline in neighbouring layers, whose prisms
    # reach the tolerance into each other, one beside another by less than the tolerance, and boxes that
    # overlap though the prisms do not.
    def batches(*prisms):
        return [[index for index, _ in batch]
                for batch in overhang._apart(list(enumerate(prisms)), overhang.FIRST_LAYERS_MOST)]

    lower, upper = overhang._prism(outline, 0, layer), overhang._prism(outline, layer, 2 * layer)
    far = overhang._prism(beside, 0, layer)
    near = overhang._prism(outline.translated(V(ISLAND_BLOCK + d.TOLERANCE / 2, 0, 0)), 0, layer)
    touching = overhang._prism(outline.translated(V(ISLAND_BLOCK, 0, 0)), 0, layer)
    clear = overhang._prism(outline.translated(V(ISLAND_BLOCK + 3 * d.TOLERANCE, 0, 0)), 0, layer)
    expect(batches() == [] and batches(lower, far) == [[0, 1]] and batches(lower, upper, far) == [[0, 2], [1]]
           and batches(lower, near) == [[0], [1]] and batches(lower, touching) == [[0], [1]]
           and batches(lower, clear) == [[0, 1]],
           "prisms far apart share a cut; one in the layer above another, one touching another or nearer "
           "than the tolerance waits for a later cut: %s, %s, %s, %s"
           % (batches(lower, upper, far), batches(lower, near), batches(lower, touching), batches(lower, clear)))


def check_printable_plans():
    """Quick fins offers the ways without islands, or the fewest first."""
    p = FinParams()
    box = Part.makeBox(30, 20, 20)
    front = [i for i, f in enumerate(box.Faces) if f.BoundBox.YMax < d.TOLERANCE][0]
    plans = list(quick_stands.quick_plans(box, [], [(box.Faces[front], front)], p, d.TILT_ANGLE))
    bottom = [e for e in box.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]
    alike = list(quick_stands.quick_plans(box, [(bottom, None)], [], p, d.TILT_ANGLE))
    real = overhang.islands
    try:
        for counts, wanted, what in (
                ([0, 2, 0, 1], [0, 2], "the ways without islands, in the order given"),
                ([3, 1, 2, 1], [1, 3, 2, 0],
                 "every way with islands: the fewest first, the order given among as many")):
            left = list(counts)
            overhang.islands = lambda *args, **kwargs: [V()] * left.pop(0)
            rated = analysis.printable_plans(box, plans, p)
            expect([plans.index(entry.plan) for entry in rated] == wanted
                   and all(len(entry.islands) == counts[plans.index(entry.plan)] for entry in rated), what)
        calls = []
        overhang.islands = lambda *args, **kwargs: calls.append(args) or [V()]
        rated = analysis.printable_plans(box, alike, p)
        expect(len(alike) > 1 and len(calls) == 1 and all(len(entry.islands) == 1 for entry in rated),
               "ways standing the part alike, the fins under other faces, are checked once for islands")
        del calls[:]
        expect(analysis.printable_plans(box, plans[:1], p) == [(plans[0], None, None, None)] and not calls,
               "one way is taken unchecked, its islands, overhangs and bridges None: there is no choice")
        overhang.islands = lambda *args, **kwargs: []
        real_rated = overhang.rated
        try:
            flat = [limits.UNPRINTABLE]
            overhang.rated = lambda *args, **kwargs: [(1, flat.pop(0))] if flat else []
            rated = analysis.printable_plans(box, plans, p)
            expect(plans.index(rated[0].plan) == 1 and len(rated) == len(plans) - 1,
                   "a way with a face too flat to print is left out while ways without are found")
        finally:
            overhang.rated = real_rated
    finally:
        overhang.islands = real
    sampled, rated = calls_counted("facing_down", lambda: analysis.rate_plans(box, alike, p))
    expect(len(rated) == len(alike) > 1 and len(sampled) == 1,
           "ways standing the part alike have its faces sampled once for all of them: %d ways, %d samplings"
           % (len(alike), len(sampled)))


def cut_centre(shape, height):
    """The centre of mass of `shape` below `height`, cut out by the kernel."""
    box = shape.BoundBox
    margin = CENTRE_CUT_MARGIN
    below = shape.common(Part.makeBox(box.XLength + 2 * margin, box.YLength + 2 * margin, height - box.ZMin + margin,
                                      V(box.XMin - margin, box.YMin - margin, box.ZMin - margin))).Solids
    volume = sum(solid.Volume for solid in below)
    moment = V()
    for solid in below:
        moment += solid.CenterOfMass * solid.Volume
    return moment * (1 / volume)


def check_centres():
    """The centres of mass the stability check works out on a mesh of the
    part lie where a cut by the kernel puts them."""
    for name, shape, tolerance in (("tilted cube", tilted_cube(), CENTRE_FLAT_TOLERANCE),
                                   ("slot on its end", slot_on_end(), CENTRE_CURVED_TOLERANCE)):
        below = stability._Below(shape)
        box = shape.BoundBox
        for share in CENTRE_SHARES:
            height = box.ZMin + share * box.ZLength
            off = (below.centre(height) - cut_centre(shape, height)).Length
            expect(off < tolerance, "%s: the centre of mass below %.0f %% of its height lies %.2g mm off the cut one"
                   % (name, 100 * share, off))
        above = box.ZMax + CENTRE_CUT_MARGIN
        whole = (below.centre(above) - cut_centre(shape, above)).Length
        expect(whole < tolerance, "%s: above it, the centre of the whole part, %.2g mm off" % (name, whole))
        expect(below.centre(box.ZMin - CENTRE_CUT_MARGIN) is None, "%s: below it, no centre" % name)
    expect(stability._Below(Part.Shape()).centre(1.0) is None, "an empty part has no centre")

    # A cube standing on an edge: below a height up to its middle lies a prism over a right-angled
    # triangle as high as that and twice as wide. Its middle goes through two edges and their corners.
    cube = Part.makeBox(EDGE, EDGE, EDGE)
    on_edge = cube.rotated(V(), V(0, 1, 0), -HALF_TURN / 4)
    on_edge.translate(V(0, 0, -on_edge.BoundBox.ZMin))
    middle = EDGE / math.sqrt(2)
    below = stability._Below(on_edge)
    for height in (middle / 2, middle - BESIDE, middle):
        volume, centre = below.sums(height)[0], below.centre(height)
        expect(abs(volume - EDGE * height * height) < CENTRE_FLAT_TOLERANCE * EDGE ** 2
               and abs(centre.z - 2 * height / 3) < CENTRE_FLAT_TOLERANCE
               and abs(centre.y - EDGE / 2) < CENTRE_FLAT_TOLERANCE and abs(centre.x) < CENTRE_FLAT_TOLERANCE,
               "a cube on an edge below %.5f mm, its middle through two edges at %.5f mm: a prism of %.4f mm3, "
               "its centre two thirds up: %.4f mm3, %s" % (height, middle, EDGE * height * height, volume, centre))
    upper = middle + BESIDE
    above = EDGE * (2 * middle - upper) ** 2
    expect(abs(below.sums(upper)[0] - (EDGE ** 3 - above)) < CENTRE_FLAT_TOLERANCE * EDGE ** 2,
           "just above its middle, the cube less the prism above: %.4f mm3" % below.sums(upper)[0])
    # A cube standing on a corner: below the three corners next to it lies a pyramid of three edges
    # of the cube, its centre three quarters up.
    diagonal = V(1, 1, 1)
    on_corner = cube.rotated(V(), diagonal.cross(V(0, 0, 1)), math.degrees(diagonal.getAngle(V(0, 0, 1))))
    on_corner.translate(V(0, 0, -on_corner.BoundBox.ZMin))
    corners = EDGE / math.sqrt(3)
    below = stability._Below(on_corner)
    for height in (corners / 2, corners - BESIDE, corners):
        volume, centre = below.sums(height)[0], below.centre(height)
        wanted = (height * math.sqrt(3)) ** 3 / 6
        expect(abs(volume - wanted) < CENTRE_FLAT_TOLERANCE * EDGE ** 2
               and abs(centre.z - 3 * height / 4) < CENTRE_FLAT_TOLERANCE,
               "a cube on a corner below %.5f mm, its three next corners at %.5f mm: a pyramid of %.4f mm3, its "
               "centre three quarters up: %.4f mm3, %s" % (height, corners, wanted, volume, centre))

    # Single triangles: what lies below a height adds what its pieces, cut out by hand and turning
    # as the triangle, add, whichever corner comes first; turned the other way they would take it off.
    def adds(*triangles):
        return stability._integrals(numpy.array(triangles, dtype=float)).sum(axis=0)

    def turned(corners):
        return [corners[turn:] + corners[:turn] for turn in range(3)]

    cases = (("one corner below a height, its level side above", [(0, 0, 0), (1, 0, 2), (0, 1, 2)],
              [[(0, 0, 0), (0.5, 0, 1), (0, 0.5, 1)]]),
             ("two corners below a height, its level side below", [(0, 0, 2), (1, 0, 0), (0, 1, 0)],
              [[(0.5, 0, 1), (1, 0, 0), (0, 1, 0)], [(0.5, 0, 1), (0, 1, 0), (0, 0.5, 1)]]),
             ("one corner below a height, one right on it and one above", [(0, 0, 0), (1, 0, 1), (0, 1, 2)],
              [[(0, 0, 0), (1, 0, 1), (0, 0.5, 1)]]))
    for what, triangle, below_height in cases:
        wanted = adds(*below_height)
        for corners in turned(triangle):
            found = stability._clipped(numpy.array([corners], dtype=float), 1)
            expect(numpy.isfinite(found).all() and numpy.abs(found - wanted).max() < d.TOLERANCE
                   and abs(wanted[0]) > d.TOLERANCE,
                   "a triangle with %s, starting at %s, adds what its part below adds, turning as it does: %s"
                   % (what, corners[0], [round(float(value), CUTS_DIGITS) for value in found]))
    expect(not stability._clipped(numpy.empty((0, 3, 3)), 1).any(), "no triangles add nothing")
    # A triangle touching a height from above, with a corner or a side, adds nothing below it.
    upright = Part.makeBox(EDGE, EDGE, EDGE, V(0, 0, EDGE))
    expect(abs(stability._Below(upright).sums(EDGE)[0]) < d.TOLERANCE
           and stability._Below(upright).centre(EDGE) is None,
           "a box standing on a height has nothing below it, the triangles of its sides touching the height "
           "from above left out")


def check_stability():
    """Whether a part stays standing while it is printed, layer by layer."""
    first, layer = d.FIRST_LAYER_HEIGHT, d.LAYER_HEIGHT
    box = Part.makeBox(30, 20, 20)
    flat = stability.check(box, [], first, layer, {})
    expect(flat is not None and not flat.tips and abs(flat.margin - 10) < STABLE_TOLERANCE
           and abs(flat.foot.x - 15) < STABLE_TOLERANCE and abs(flat.foot.y - 10) < STABLE_TOLERANCE,
           "a box lying on the bed stands, its plumb line in the middle: %s" % (flat,))
    # The same footprint, the centre of mass four times as high: the same
    # margin, a far smaller tipping angle, atan(margin / height).
    tall = stability.check(Part.makeBox(30, 20, TALL_BOX_HEIGHT), [], first, layer, {})
    expect(tall is not None and abs(tall.margin - flat.margin) < STABLE_TOLERANCE
           and abs(tall.angle - math.degrees(math.atan2(tall.margin, TALL_BOX_HEIGHT / 2))) < ANGLE_TOLERANCE
           and tall.angle < flat.angle,
           "a taller part on the same footprint has a smaller tipping angle: %.1f, %.1f degrees"
           % (tall.angle, flat.angle))

    # Flatter than deep, so standing on an edge at 45 degrees it leans to one side.
    slab = Part.makeBox(30, 20, 10)
    bottom = [e for e in slab.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]
    standing = moved(slab, orient.tilt(slab, bottom, d.TILT_ANGLE))
    alone = stability.check(standing, [], first, layer, {})
    expect(alone is not None and alone.tips and alone.height < standing.BoundBox.ZLength,
           "a slab standing on an edge without fins tips while it is printed: layer %s" % (alone and alone.layer))

    braced = stability.check(standing, [], first, layer, {}, STABLE_BRIM)
    expect(braced is not None and not braced.tips and abs(braced.margin - alone.profile[-1][1] - STABLE_BRIM) < 1
           and len(braced.footprint) > len(alone.footprint),
           "a wide brim holds the slab: its footprint grown by the brim, the margin by its width")
    reach = standing.BoundBox
    beside = Part.makeBox(reach.XLength, reach.YLength, first, V(reach.XMin, reach.YMin, 0))
    held = stability.check(standing, [(beside.translated(V(0, 0, 0)), 0.0)], first, layer, {})
    late = stability.check(standing, [(beside, reach.ZMax)], first, layer, {})
    expect(held is not None and not held.tips and late is not None and late.tips and late.layer == alone.layer,
           "a support under the whole part from the bed up holds it; one holding only from the top, too late")

    column = Part.makeBox(STABLE_BASE, STABLE_BASE, STABLE_HEIGHT)
    arm = Part.makeBox(STABLE_REACH, STABLE_BASE, STABLE_BASE, V(0, 0, STABLE_HEIGHT))
    leaning = column.fuse(arm).removeSplitter()
    tipped = stability.check(leaning, [], first, layer, {})
    expect(tipped is not None and tipped.tips and tipped.height > STABLE_HEIGHT and tipped.outward.x > 0.9,
           "a part growing out over its edge high up tips at a layer of the arm, outward along it: %s"
           % ((tipped and (tipped.layer, round(tipped.height, 2), tipped.outward)),))
    centres = {}
    stability.check(leaning, [], first, layer, centres)
    again = stability.check(leaning, [], first, layer, centres)
    expect(again == tipped, "the centres kept for a part are taken again, the result the same")
    heights = [height for height, _, _ in tipped.profile]
    expect(heights == sorted(heights) and tipped.profile[-1][1] < 0 < tipped.profile[0][1],
           "the profile runs from the bed up, from standing to tipping")
    cut = stability.section(leaning, tipped.height)
    expect(cut is not None and abs(cut.BoundBox.ZMin - tipped.height) < d.TOLERANCE
           and cut.Area > STABLE_BASE * STABLE_BASE,
           "the critical layer is cut out of the part at its height, the arm in it")
    # Cut exactly at the underside of a slab across two piers: the layer
    # below it, the tops of both piers.
    width, depth, height = PIER
    tops = stability.section(piers(GAP_CRITICAL), height)
    expect(tops is not None and len(tops.Faces) == 2 and abs(tops.Area - 2 * width * depth) < d.TOLERANCE,
           "a layer cut on the underside of a slab across two piers holds the tops of both: %.1f mm2"
           % (tops.Area if tops else 0.0))
    expect(stability.check(Part.Shape(), [], first, layer, {}) is None, "an empty part has no result")


def round_side_of(shape, radius=ROD_RADIUS):
    """The number of the curved side of `shape` with `radius`."""
    return [i for i, f in enumerate(shape.Faces)
            if orient.is_round_side(f) and abs(f.Surface.Radius - radius) < d.TOLERANCE][0]


def leans_by(shape, number, degrees):
    """Whether face `number` of `shape`, flat or round, leans `degrees` against the bed."""
    frame = face_frame.frame_of(shape, shape.Faces[number])
    return abs(frame.n_z + math.cos(math.radians(degrees))) < 1e-6


def check_split_side():
    """A side and a rim that a STEP file split in halves are found whole on
    the joined shape; a half ring of a split tube is found by a point on it,
    the seam between the halves is gone."""
    split = split_cylinder(ROD_RADIUS, ROD_HEIGHT, BORE_RADIUS)
    whole = orient.joined(split)
    half = [f for f in split.Faces if isinstance(f.Surface, Part.Cylinder) and f.Surface.Radius > BORE_RADIUS][0]
    arc = [e for e in split.Edges if isinstance(e.Curve, Part.Circle) and e.Curve.Radius > BORE_RADIUS][0]
    side, rim = orient.whole_of(whole, half), orient.whole_of(whole, arc)
    expect(orient.is_piece(half) and side is not None and orient.is_round_side(side)
           and rim is not None and orient.is_rim(rim) and abs(rim.Curve.Radius - ROD_RADIUS) < d.TOLERANCE,
           "half of a split side and of a split rim stand for the whole side and rim")
    ring = [f for f in split.Faces if f.findPlane() is not None][0]
    seam = [e for e in split.Edges if isinstance(e.Curve, Part.Line)
            and not any(e.isSame(m) for m in half.Edges) and e.BoundBox.XLength < d.TOLERANCE][0]
    found = orient.counterpart(ring, whole.Faces)
    expect(found is not None and found.findPlane() is not None and found.Area > ring.Area
           and orient.counterpart(seam, whole.Edges) is None,
           "a half ring of a split tube is found on the joined shape, the seam between the halves is not")
    rod = Part.makeCylinder(ROD_RADIUS, ROD_HEIGHT)
    box = Part.makeBox(BOX_SIDE, BOX_SIDE, BOX_SIDE)
    filleted = box.makeFillet(EDGE_ROUND, box.Edges[:1])
    fillet = [f for f in filleted.Faces if isinstance(f.Surface, Part.Cylinder)][0]
    expect(not orient.is_piece(rod.Faces[round_side_of(rod)])
           and orient.whole_of(orient.joined(filleted), fillet) is None,
           "a whole side is no piece, a fillet is a piece of no whole side")
    # Half a turn on top of a whole cylinder of the same radius joins with its
    # side, but runs only part of its length: no half of a split side.
    stepped = rod.fuse(Part.makeCylinder(ROD_RADIUS, ROD_HEIGHT / 2, V(0, 0, ROD_HEIGHT), V(0, 0, 1), HALF_TURN))
    top = [f for f in stepped.Faces if orient.is_piece(f)][0]
    expect(orient.whole_of(orient.joined(stepped), top) is None,
           "half a turn on top of a whole cylinder is no half of a split side")


def check_round_side():
    """A cylinder or tube stands on its rim, one fin under the lowest line of its curved side."""
    p = FinParams(placement=d.PLACEMENT_CENTER)
    rod = Part.makeCylinder(ROD_RADIUS, ROD_HEIGHT)
    tube = rod.cut(Part.makeCylinder(BORE_RADIUS, ROD_HEIGHT))
    lying = rod.copy()
    lying.rotate(V(0, 0, 0), V(1, 0, 0), 90)
    lying.translate(V(0, 0, ROD_RADIUS))
    # Mirrored, the side counts its parameter the other way round its axis.
    mirrored = rod.mirror(V(0, 0, 0), V(1, 0, 0))

    box = Part.makeBox(BOX_SIDE, BOX_SIDE, BOX_SIDE)
    filleted = box.makeFillet(EDGE_ROUND, box.Edges[:1])
    expect(orient.is_round_side(rod.Faces[round_side_of(rod)])
           and not any(orient.is_round_side(f) for f in filleted.Faces),
           "the side of a cylinder is a round side, a fillet is not")
    expect(any(orient.is_curved_side(f) for f in filleted.Faces), "a fillet is a curved side")

    for name, shape in (("cylinder", rod), ("tube", tube), ("cylinder on its side", lying),
                        ("mirrored cylinder", mirrored)):
        side = round_side_of(shape)
        rim = [e for e in shape.Faces[side].Edges if orient.is_rim(e)][0]
        for chosen, edges, faces in (("its rim", [(rim, None)], []), ("its side", [], [(shape.Faces[side], side)]),
                                     ("rim and side", [(rim, None)], [(shape.Faces[side], side)])):
            plan = quick_stands.quick_plan(shape, edges, faces, p, d.TILT_ANGLE)
            stood = moved(shape, plan.change)
            result = geometry.build(stood, stood.Faces[plan.number], p)
            expect(plan.number == side and leans_by(stood, side, d.TILT_ANGLE)
                   and abs(resting_height(stood)) < d.TOLERANCE,
                   "%s, %s chosen: it stands on the rim, the side leaning 45 degrees" % (name, chosen))
            expect(len(result.positions) == 1 and len(result.tines) > 1
                   and max(abs(t.distToShape(stood)[0] - p.clearance) for t in result.tines) < d.TOLERANCE
                   and result.fins.common(stood).Volume < d.TOLERANCE,
                   "%s, %s chosen: one fin, every tine ends on the side, none in it" % (name, chosen))
            expect(any("rim" in w for w in result.warnings),
                   "%s, %s chosen: a note gives the rim more hold on the bed" % (name, chosen))
            expect(abs(face_frame.side_angle(stood.Faces[side])) < d.TOLERANCE,
                   "%s, %s chosen: the fin stands at 0 degrees of the side" % (name, chosen))
        for degrees in ODD_TURNS:
            spun = shape.copy()
            spun.rotate(spun.Faces[side].Surface.Center, spun.Faces[side].Surface.Axis, degrees)
            plan = quick_stands.quick_plan(spun, [], [(spun.Faces[side], side)], p, d.TILT_ANGLE)
            expect(abs(face_frame.side_angle(moved(spun, plan.change).Faces[side])) < d.TOLERANCE,
                   "%s turned %g degrees about its axis first: the fin still stands at 0 degrees"
                   % (name, degrees))
            stood = moved(spun, plan.change)
            change = face_frame.turn_of(stood.Faces[side], face_frame.turn_mm(stood.Faces[side], ROUND_DEGREES))
            expect(abs(face_frame.side_angle(moved(stood, change).Faces[side])
                       - (face_frame.FULL_CIRCLE - ROUND_DEGREES)) < 1e-6,
                   "%s turned %g degrees the right way round: the fin stands that far back round the side"
                   % (name, ROUND_DEGREES))
        line = orient.side_direction(plan.change, rim)
        expect(line is not None and abs(abs(line.x) - 1) < 1e-6, "%s: seen from the side along its rim" % name)

    # The chamfer the note suggests: the part stands on it, also on both ends.
    for chamfered_ends in (1, 2):
        rims = [e for e in rod.Edges if orient.is_rim(e)]
        bottom_first = sorted(rims, key=lambda e: e.CenterOfMass.z)
        chamfered = rod.makeChamfer(EDGE_ROUND, bottom_first[:chamfered_ends])
        side = round_side_of(chamfered)
        plan = quick_stands.quick_plan(chamfered, [], [(chamfered.Faces[side], side)], p, d.TILT_ANGLE)
        stood = moved(chamfered, plan.change)
        cones = [f for f in stood.Faces if isinstance(f.Surface, Part.Cone)]
        expect(not any(plan.edge.isSame(e) for e in chamfered.Faces[side].Edges)
               and min(f.BoundBox.ZMin for f in cones) < d.TOLERANCE and leans_by(stood, side, d.TILT_ANGLE),
               "a cylinder chamfered on %d rim(s), its side chosen: it stands on a chamfer" % chamfered_ends)

    shaft = rod.fuse(Part.makeCylinder(BORE_RADIUS, ROD_RADIUS, V(0, 0, ROD_HEIGHT))).removeSplitter()
    for name, shape in (("a tube", tube), ("a shaft with a smaller step", shaft)):
        radii = [e.Curve.Radius for e in quick_stands.rims_on_axis(shape, shape.Faces[round_side_of(shape)])]
        expect(radii[:2] == [ROD_RADIUS, ROD_RADIUS] and radii[-1] == BORE_RADIUS,
               "%s tries the rims of its side before the smaller ones on its axis: %s" % (name, radii))
    # The thinner step below and a fillet round the free end: the rim at the
    # step cannot carry the part, the one of the fillet does, the fillet
    # bulging past it on the bed, and nothing stands on the thinner step.
    under = Part.makeCylinder(BORE_RADIUS, ROD_RADIUS, V(0, 0, -ROD_RADIUS))
    free_end = [e for e in rod.Edges if orient.is_rim(e) and e.BoundBox.ZMin > ROD_HEIGHT - d.TOLERANCE]
    rounded_end = rod.makeFillet(EDGE_ROUND, free_end).fuse(under).removeSplitter()
    side = round_side_of(rounded_end)
    plan = quick_stands.quick_plan(rounded_end, [], [(rounded_end.Faces[side], side)], p, d.TILT_ANGLE)
    stood = moved(rounded_end, plan.change)
    fillet = next(f for f in stood.Faces if isinstance(f.Surface, Part.Toroid))
    bed = resting_height(rounded_end)
    expect(abs(plan.edge.Curve.Radius - (ROD_RADIUS - EDGE_ROUND)) < d.TOLERANCE
           and abs(resting_height(fillet) - bed) < d.TOLERANCE
           and abs(resting_height(stood) - bed) < d.TOLERANCE and leans_by(stood, side, d.TILT_ANGLE),
           "a shaft thinner below, its side chosen: it stands on the fillet of its free end")
    # A chamfer on the free end, steeper or flatter than the side leans: a
    # straight one never reaches below the rim alone. Steep, the part stands
    # on the rim; flat, the edge to the side reaches lowest, and it cannot.
    free_rim = [e for e in rod.Edges if orient.is_rim(e) and e.BoundBox.ZMin > ROD_HEIGHT - d.TOLERANCE]
    for steep, axial, radial in ((True, CHAMFER_LONG, CHAMFER_SHORT), (False, CHAMFER_SHORT, CHAMFER_LONG)):
        chamfered = rod.makeChamfer(axial, radial, free_rim)
        cone = next(f for f in chamfered.Faces if isinstance(f.Surface, Part.Cone))
        small = min((e for e in cone.Edges if orient.is_rim(e)), key=lambda e: e.Curve.Radius)
        side = round_side_of(chamfered)
        try:
            stood = moved(chamfered, orient.stand_on_rim(chamfered, small, orient.side_tilt(d.TILT_ANGLE),
                                                         chamfered.Faces[side]))
        except orient.OrientError as error:
            expect(not steep and "cannot stand" in str(error),
                   "a rim with a flatter chamfer cannot carry the part: %s" % error)
        else:
            expect(steep and leans_by(stood, side, d.TILT_ANGLE),
                   "a rim with a steeper chamfer carries the part, its side leaning %g degrees" % d.TILT_ANGLE)
    # A knob on the end face: the poles of its sphere are degenerated edges,
    # whose curve FreeCAD cannot give; the rims are looked for past them.
    knob = Part.makeSphere(EDGE_ROUND, V(ROD_RADIUS / 2, 0, ROD_HEIGHT))
    knobbed = rod.fuse(knob)
    side = round_side_of(knobbed)
    edge = quick_stands.quick_plan(knobbed, [], [(knobbed.Faces[side], side)], p, d.TILT_ANGLE).edge
    expect(any(e.Degenerated for e in knobbed.Edges)
           and edge is not None and abs(edge.Curve.Radius - ROD_RADIUS) < d.TOLERANCE,
           "a cylinder with a knob on its end, its side chosen: it stands on its rim, past the poles of the knob")
    # A step whose angles count from elsewhere than those of the shaft.
    step = Part.makeCylinder(BORE_RADIUS, ROD_HEIGHT, V(0, 0, ROD_HEIGHT))
    step.rotate(V(0, 0, 0), UP, ODD_TURNS[0])
    stepped = rod.fuse(step)
    thin = round_side_of(stepped, BORE_RADIUS)
    plan = quick_stands.quick_plan(stepped, [], [(stepped.Faces[thin], thin)], p, d.TILT_ANGLE)
    expect(abs(face_frame.side_angle(moved(stepped, plan.change).Faces[thin])) < d.TOLERANCE,
           "the thinner side of a shaft chosen, the fin stands at 0 degrees of that side")

    arched = Part.Arc(V(0, 0, 0), V(ROD_RADIUS / 2, 0, ROD_RADIUS / 2), V(ROD_RADIUS, 0, 0)).toShape()
    flat_box = Part.makeBox(ROD_RADIUS, ROD_RADIUS, ROD_RADIUS)
    box_bottom = [e for e in flat_box.Edges if e.BoundBox.ZMax < d.TOLERANCE][0]
    rod_bottom = [e for e in rod.Edges if orient.is_rim(e) and e.BoundBox.ZMax < d.TOLERANCE][0]
    expect(not orient.on_bed(flat_box, arched) and orient.on_bed(flat_box, box_bottom)
           and orient.on_bed(rod, rod_bottom),
           "an arc arching up from its ends on the bed is not on the bed; a straight edge and a rim there are")

    side = round_side_of(rod)
    rim = [e for e in rod.Faces[side].Edges if orient.is_rim(e)][0]
    stood = moved(rod, orient.stand(rod, rim, ODD_TILT))
    expect(leans_by(stood, side, 90 - ODD_TILT), "a rim alone lifts its flat face by the tilt angle")
    stood = moved(rod, orient.stand(rod, rim, ODD_TILT, rod.Faces[side]))
    expect(leans_by(stood, side, ODD_TILT), "a rim with the side it bounds leans the side by the tilt angle")
    quick = moved(rod, quick_stands.quick_plan(rod, [(rim, None)], [], p, ODD_TILT).change)
    expect(leans_by(quick, side, ODD_TILT),
           "Quick fins on a rim alone leans the side by the tilt angle, as on the side")
    disc = Part.makeCylinder(ROD_RADIUS, DISC_HEIGHT)
    disc_rim = [e for e in disc.Edges if orient.is_rim(e)][0]
    for tilt in (ODD_TILT, d.TILT_ANGLE):
        plan = quick_stands.quick_plan(disc, [(disc_rim, None)], [], p, tilt)
        on_disc = moved(disc, plan.change)
        expect(orient.is_round_side(on_disc.Faces[plan.number]) and leans_by(on_disc, plan.number, tilt),
               "Quick fins on the rim of a disc at %g degrees puts the fins under its side, leaning so" % tilt)
    spread = geometry.build(stood, stood.Faces[side], FinParams(placement=d.PLACEMENT_ENDS))
    expect(len(spread.positions) == 1, "a round side takes one fin, whatever the placement")

    outside = round_side_of(tube)
    leaning_tube = moved(tube, quick_stands.quick_plan(tube, [], [(tube.Faces[outside], outside)], p,
                                                       d.TILT_ANGLE).change)
    for shape, number, why, label in ((rod, side, face_frame.NOT_OVERHANGING, "an upright cylinder"),
                                      (lying, round_side_of(lying), face_frame.HORIZONTAL_ROUND_SIDE,
                                       "a cylinder on its side"),
                                      (leaning_tube, round_side_of(tube, BORE_RADIUS), "inward",
                                       "the inside of a tube")):
        try:
            face_frame.frame_of(shape, shape.Faces[number])
        except face_frame.FinError as error:
            expect(why in str(error), "%s takes no fins: %s" % (label, error))
        else:
            raise AssertionError("%s took fins" % label)

    inner = [e for e in tube.Faces[round_side_of(tube, BORE_RADIUS)].Edges if orient.is_rim(e)][0]
    try:
        orient.stand(tube, inner, d.TILT_ANGLE)
    except orient.OrientError as error:
        expect("cannot stand" in str(error), "a tube cannot stand on its inner rim: %s" % error)
    else:
        raise AssertionError("a tube stood on its inner rim")

    plan = quick_stands.quick_plan(rod, [], [(rod.Faces[side], side)], p, d.TILT_ANGLE)
    stood = moved(rod, plan.change)
    frame = face_frame.frame_of(stood, stood.Faces[side])
    # Under the side alone, as before the fin followed the contour.
    alone = FinParams(placement=d.PLACEMENT_CENTER, follow_contour=False)
    whole = geometry.build(stood, stood.Faces[side], alone)
    middle_z = whole.tine_z[len(whole.tine_z) // 2]
    middle_tine = frame.bed_z + middle_z + p.tine_height / 2
    middle = (frame.along_min + frame.along_max) / 2
    on_side = frame.point(middle, frame.s_face(middle_tine), middle_tine)
    normal = frame.normal()
    bored = stood.cut(Part.makeCylinder(RECESS_RADIUS, 2 * RECESS_RADIUS, on_side - normal * RECESS_RADIUS, normal))
    pitted = geometry.build(bored, bored.Faces[round_side_of(bored)], alone)
    expect(len(pitted.tines) == len(whole.tines) - 1
           and any("%.1f mm" % middle_z in w for w in pitted.warnings),
           "under the side alone, the tine over a hole in the side is left out, with a warning: %s"
           % pitted.warnings)
    # Along the contour the hole, lower than the bridge, is bridged: no tine
    # over it and nothing said, the tines start anew right above it.
    spanned = geometry.build(bored, bored.Faces[round_side_of(bored)], p)
    hole_low, hole_high = middle_tine - RECESS_RADIUS, middle_tine + RECESS_RADIUS
    over = [t for t in spanned.tines if t.BoundBox.ZMax > hole_low and t.BoundBox.ZMin < hole_high
            and t.distToShape(bored)[0] > p.clearance + d.TINE_END_TOLERANCE]
    above = min(z for z in spanned.tine_z if frame.bed_z + z > hole_high - RECESS_RADIUS)
    expect(not over and not any("hole" in w for w in spanned.warnings)
           and frame.bed_z + above < hole_high + p.tine_spacing / 2,
           "along the contour, a hole in the side is bridged without a word, the next tine right above it: %s"
           % spanned.warnings)

    # Moved by hand, the fin stays under the lowest line and the part turns
    # under it: the hole goes the other way round, away from the fin.
    hole = [f for f in bored.Faces if isinstance(f.Surface, Part.Cylinder) and f.Surface.Radius == RECESS_RADIUS][0]
    turned = moved(bored, face_frame.turn_of(bored.Faces[round_side_of(bored)], ROUND_TURN))
    turned_hole = [f for f in turned.Faces if isinstance(f.Surface, Part.Cylinder)
                   and f.Surface.Radius == RECESS_RADIUS][0]
    went = (turned_hole.CenterOfMass - hole.CenterOfMass).dot(frame.along)
    shifted = geometry.build(turned, turned.Faces[round_side_of(turned)], alone, shifts={1: ROUND_TURN})
    expect(went < -ROUND_TURN / 2 and len(shifted.tines) == len(whole.tines),
           "the part turns under the fin moved %.0f mm, the hole goes %.1f mm the other way" % (ROUND_TURN, went))
    shown = shifted.starts[1] + shifted.thickness / 2 - shifted.face_start
    expect(abs(shown) < d.TOLERANCE and abs(shifted.radius - ROD_RADIUS) < d.TOLERANCE
           and shifted.fins.BoundBox.isInside(whole.fins.BoundBox.Center),
           "the fin stays under the lowest line, whatever it is asked to move by: the part turns instead")


def stood_on_free_rim(shape):
    """`shape` stood by Quick fins for the side of ROD_RADIUS, and the number
    of that side."""
    side = round_side_of(shape)
    plan = quick_stands.quick_plan(shape, [], [(shape.Faces[side], side)], FinParams(), d.TILT_ANGLE)
    return moved(shape, plan.change), side


def steepest_step(body, frame):
    """How far the side of `body` towards the part comes further in from one
    layer to the next, up the first OVERHANG_REACH mm (mm per OVERHANG_LAYER)."""
    box = body.BoundBox
    inner, worst = None, 0.0
    z = box.ZMin + OVERHANG_LAYER / 2
    while z < min(box.ZMin + OVERHANG_REACH, box.ZMax):
        points = [p for wire in body.slice(V(0, 0, 1), z) for p in wire.discretize(Deflection=OVERHANG_DEFLECTION)]
        # A layer with nothing of it between its foot and blade: all of it hangs.
        if not points:
            return OVERHANG_REACH
        here = min(point.dot(frame.out) for point in points)
        if inner is not None:
            worst = max(worst, inner - here)
        inner = here
        z += OVERHANG_LAYER
    return worst


def matrix_shapes():
    """The shapes of check_side_fin_matrix(), by name: each with the radius of
    the round side the fins stand under."""
    rod = Part.makeCylinder(ROD_RADIUS, ROD_HEIGHT)
    free_end = [e for e in rod.Edges if orient.is_rim(e) and e.BoundBox.ZMin > 1]
    upper = V(0, 0, ROD_HEIGHT)
    return {"rod": rod,
            "tube": rod.cut(Part.makeCylinder(BORE_RADIUS, ROD_HEIGHT)),
            "step near the fins": rod.fuse(Part.makeCylinder(STEPS_NEAR_FINS[1], ROD_HEIGHT, upper)).removeSplitter(),
            "flange": Part.makeCylinder(FLANGE_RADIUS, FLANGE_HEIGHT).fuse(
                Part.makeCylinder(ROD_RADIUS, ROD_HEIGHT, V(0, 0, FLANGE_HEIGHT))).removeSplitter(),
            "thin step": rod.fuse(Part.makeCylinder(THIN_STEP_RADIUS, ROD_HEIGHT, upper)).removeSplitter(),
            "cone": rod.fuse(Part.makeCone(ROD_RADIUS, CONE_TOP, CONE_HEIGHT, upper)).removeSplitter(),
            "fillet": rod.makeFillet(FILLET_RADIUS, free_end),
            "large fillet": rod.makeFillet(LARGE_FILLET_RADIUS, free_end)}


def fin_matrix_faults(name, stood, number, kind, degrees, thickness, side_tines, height=0.0):
    """What is wrong with the fins of `kind` under face `number` of `stood`, as
    lines of text: refused, overlapping or too close to the part, invalid, higher
    than they say or than asked of the rod, hanging over, fewer fins than asked
    for, with fewer tines than the fin alone, or side fins with other than
    `side_tines`: what a change costs them shows here."""
    asked = FinParams(placement=d.PLACEMENT_CENTER, round_fins=kind, round_fin_angle=degrees,
                      fin_thickness=thickness, fin_height=height)
    case = "%s, %s, %g degrees, %g mm thick, %g mm high: " % (name, kind, degrees, thickness, height)
    try:
        built = geometry.build(stood, stood.Faces[number], asked)
    except face_frame.FinError as error:
        return [case + "refused: %s" % error]
    faults = []
    planned = MATRIX_FIN_COUNTS[kind]
    if len(built.numbers) != planned:
        faults.append(case + "%d fins, %d asked for" % (len(built.numbers), planned))
    for fin in built.frames:
        if fin in built.numbers and len(built.touching_z[fin]) != side_tines:
            faults.append(case + "fin %d has %d tines, not %d" % (fin, len(built.touching_z[fin]), side_tines))
        if name == "rod" and height and abs(built.heights.get(fin, height) - height) > d.TOLERANCE:
            faults.append(case + "fin %d only %.1f mm high" % (fin, built.heights[fin]))
    if geometry.overlap_of(built.fins, stood) > d.TOLERANCE:
        faults.append(case + "reaches into the part")
    for position, fin in enumerate(built.numbers):
        body = built.bodies[position]
        closest = body.distToShape(stood)[0]
        if closest < asked.gap - GAP_ACROSS_FIN:
            faults.append(case + "fin %d %.3f off the part" % (fin, closest))
        if not body.isValid():
            faults.append(case + "fin %d invalid" % fin)
        above = body.BoundBox.ZMax - built.frame.bed_z - built.heights[fin]
        if above > HEIGHT_ACROSS_FIN:
            faults.append(case + "fin %d %.2f mm above its height" % (fin, above))
        # The fins are mirror images: one tells for both.
        if fin == 1:
            steep = steepest_step(body, built.frames[fin])
            if steep > OVERHANG_LAYER + GAP_ACROSS_FIN:
                faults.append(case + "fin %d hangs over by %.3f" % (fin, steep))
    alone = geometry.build(stood, stood.Faces[number], FinParams(placement=d.PLACEMENT_CENTER, fin_thickness=thickness,
                                                                 fin_height=height))
    middle = built.numbers.index(2) if kind == d.ROUND_FINS_THREE and 2 in built.numbers else None
    if middle is not None and len(built.touching_z[2]) < len(alone.touching_z[1]):
        faults.append(case + "the middle fin has %d tines, %d alone" % (len(built.touching_z[2]),
                                                                         len(alone.touching_z[1])))
    return faults


def check_side_fin_matrix():
    """Two and three fins under a round side, over shapes, angles and thicknesses
    at once, so what one change does to the others shows here: every one is
    built or says why, keeps the gap, is no higher than it says and hangs over
    nowhere. One fin under a part of a side above a groove keeps its tines
    whatever was built before.

    INPUTS this has to withstand:
      plain rod and tube                    ->  fins at the gap
      step ending near the plane of a fin   ->  built, at least the gap off
      thin step, cone, fillet               ->  built, at least the gap off
      thick fin, far round                  ->  the same
      a fin height above what stays clear   ->  side fins end lower, none left out
    """
    faults = []
    for name, shape in matrix_shapes().items():
        number = round_side_of(shape)
        plan = quick_stands.quick_plan(shape, [], [(shape.Faces[number], number)], FinParams(), d.TILT_ANGLE)
        stood = moved(shape, plan.change)
        cases = [(*case, 0.0) for case in MATRIX_CASES] + list(MATRIX_HIGH_CASES.get(name, ()))
        for (kind, degrees, thickness, height), side_tines in zip(cases, MATRIX_SIDE_TINES[name], strict=True):
            faults += fin_matrix_faults(name, stood, number, kind, degrees, thickness, side_tines, height)
    expect(not faults, "the matrix of side fins holds: %s" % "; ".join(faults))

    # A groove: the side above it, then below it, on one shaft, and the other way round.
    rod = Part.makeCylinder(ROD_RADIUS, 2 * ROD_HEIGHT)
    grooved_shaft = rod.cut(Part.makeCylinder(ROD_RADIUS + 1, GROOVE_WIDTH, V(0, 0, ROD_HEIGHT)).cut(
        Part.makeCylinder(BORE_RADIUS, GROOVE_WIDTH, V(0, 0, ROD_HEIGHT)))).removeSplitter()
    sides = sorted((k for k, f in enumerate(grooved_shaft.Faces)
                    if orient.is_round_side(f) and abs(f.Surface.Radius - ROD_RADIUS) < d.TOLERANCE),
                   key=lambda k: grooved_shaft.Faces[k].CenterOfMass.z)
    plan = quick_stands.quick_plan(grooved_shaft, [], [(grooved_shaft.Faces[sides[0]], sides[0])], FinParams(),
                                   d.TILT_ANGLE)
    stood = moved(grooved_shaft, plan.change)
    one = FinParams(placement=d.PLACEMENT_CENTER)
    counts = {}
    for order in (sides, sides[::-1]):
        contour.clear_kept()
        for number in order:
            counts.setdefault(number, []).append(len(geometry.build(stood, stood.Faces[number], one).tines))
    expect(all(len(set(found)) == 1 for found in counts.values()),
           "one fin keeps its tines whichever side of a groove is built first: %s" % counts)
    above = max(sides, key=lambda k: stood.Faces[k].CenterOfMass.z)
    full = geometry.build(stood, stood.Faces[above], one)
    start = full.frame.face_bottom_z - full.frame.bed_z
    expect(any(z >= start - d.TOLERANCE for z in full.touching_z[1])
           and min(full.touching_z[1]) < start + TINE_NEAR_START,
           "above a groove the fin holds right from the start of the side: %s from %.1f"
           % (sorted(full.touching_z[1])[:2], start))


def check_known_clear():
    """A fin clear of the part is measured once for its shape; one touching it
    is never taken as clear, the same shape beside another part or mirrored onto
    its corners is measured, and an overlap is refused however it came."""
    part = Part.makeBox(MESHED_BOX, MESHED_BOX, MESHED_BOX)
    other = Part.makeBox(MESHED_BOX, MESHED_BOX, 2 * MESHED_BOX)
    off = Part.makeBox(1, 1, 1, V(MESHED_BOX + MESHED_OFF, 0, 0))
    touching = Part.makeBox(1, 1, 1, V(MESHED_BOX, 0, 0))
    inside = Part.makeBox(1, 1, 1, V(1, 1, 1))
    above = Part.makeBox(1, 1, 1, V(0, 0, MESHED_BOX + MESHED_OFF))
    geometry._kept_clear.clear()
    expect(geometry._not_known_clear([off], part) == [], "a fin off the part: clear")
    unsure = geometry._not_known_clear([off, touching, inside], part)
    expect(len(unsure) == 2 and unsure[0].isSame(touching) and unsure[1].isSame(inside),
           "a fin touching or in the part: not clear")
    expect(len(geometry._kept_clear) == 3, "each shape measured once: %d" % len(geometry._kept_clear))
    expect(geometry._not_known_clear([above], part) == [] and len(geometry._not_known_clear([above], other)) == 1,
           "the same shape beside another part is measured again")
    # What is kept is what is answered: said otherwise there, the shape is not measured.
    geometry._kept_clear[(hash(shapes.shape_key(part)), shapes.shape_key(off))] = False
    expect(len(geometry._not_known_clear([off], part)) == 1, "a shape asked again is not measured again")

    # A piece measured by its body and the tines joined to it, one by one.
    def fin(body_at, tine_from):
        """A body from `body_at` on beside the box and a tine from `tine_from` to it, and the two fused."""
        body = Part.makeBox(1, 1, 1, V(body_at, 0, 0))
        tine = Part.makeBox(body_at - tine_from, 0.5, 0.5, V(tine_from, 0.25, 0.25))
        return body.fuse(tine).removeSplitter(), [body, tine]

    def unsure_of(piece, shapes):
        geometry._kept_clear.clear()
        return len(geometry._not_known_clear([piece], part, [shapes])), len(geometry._not_known_clear([piece], part))

    body_at = MESHED_BOX + MESHED_OFF
    cases = [("the tine ending short of the part", fin(body_at, MESHED_BOX + APART_TINE_OFF), 0),
             ("the tine touching the part", fin(body_at, MESHED_BOX), 1),
             ("the tine reaching into the part", fin(body_at, MESHED_BOX - APART_TINE_IN), 1),
             ("the body touching the part", fin(MESHED_BOX, MESHED_BOX - APART_TINE_IN), 1),
             ("the body in the part", fin(1.0, 1.0 - APART_TINE_IN), 1)]
    told = [(name, unsure_of(piece, shapes), expected) for name, (piece, shapes), expected in cases]
    expect(all(found == (expected, expected) for _, found, expected in told),
           "a fin by its body and its tine is told clear of the part as the fin whole: %s"
           % ", ".join("%s %s" % (name, "not clear" if found[0] else "clear") for name, found, _ in told))
    far_body = Part.makeBox(1, 1, 1, V(3 * MESHED_BOX, 0, 0))
    far_tine = Part.makeBox(1, 0.5, 0.5, V(3 * MESHED_BOX - 1, 0.25, 0.25))
    geometry._kept_clear.clear()
    expect(geometry._not_known_clear([far_body.fuse(far_tine)], part, [[far_body, far_tine]]) == [],
           "a tine with no face of the part near it is clear")
    # A part whose face has no box, on a torus: held against every tine.
    ring = Part.makeTorus(*RING)
    geometry._kept_clear.clear()
    told = []
    for tine_from in (sum(RING) + APART_TINE_OFF, sum(RING) - APART_TINE_IN):
        body = Part.makeBox(1, 1, 1, V(sum(RING) + MESHED_OFF, -0.5, -0.5))
        tine = Part.makeBox(sum(RING) + MESHED_OFF - tine_from, 0.5, 0.5, V(tine_from, -0.25, -0.25))
        piece = body.fuse(tine).removeSplitter()
        told.append((len(geometry._not_known_clear([piece], ring, [[body, tine]])),
                     ring.distToShape(piece)[0] <= d.TOLERANCE))
    expect(told == [(0, False), (1, True)],
           "a tine ending short of a ring is clear, one reaching into it is not, as the fin whole says: %s" % told)
    # A round part that carries a mesh: the BoundBox of its side stops short of it.
    radius, height = APART_ROUND
    round_part = Part.makeCylinder(radius, height)
    round_part.tessellate(APART_ROUND_MESH)
    side = next(face for face in round_part.Faces if isinstance(face.Surface, Part.Cylinder))

    def short_at(turn):
        """How far the BoundBox of the side stops short of it, `turn` degrees round the axis."""
        out = App.Rotation(V(0, 0, 1), turn).multVec(V(1, 0, 0))
        box = side.BoundBox
        return radius - max(V(x, y, 0).dot(out) for x in (box.XMin, box.XMax) for y in (box.YMin, box.YMax))

    turn = max(APART_ROUND_TURNS, key=short_at)
    short = short_at(turn)
    cut = short * APART_ROUND_CUT
    body = Part.makeBox(1, 1, 1, V(radius + 1, -0.5, height / 2))
    tine = Part.makeBox(1 + cut, 0.5, 0.5, V(radius - cut, -0.25, height / 2 + 0.25))
    for shape in (body, tine):
        shape.rotate(V(0, 0, 0), V(0, 0, 1), turn)
    piece = body.fuse(tine).removeSplitter()
    geometry._kept_clear.clear()
    apart = len(geometry._not_known_clear([piece], round_part, [[body, tine]]))
    geometry._kept_clear.clear()
    whole = len(geometry._not_known_clear([piece], round_part))
    expect(short > d.TOLERANCE and cut > d.TOLERANCE and (apart, whole) == (1, 1),
           "a tine cutting %.4f mm into a round part that carries a mesh, where its BoundBox stops %.4f mm short "
           "of it, is not taken for clear" % (cut, short))

    def bulging(x, tip):
        """A plate with one side an arc, from x, 0 to x, MESHED_BOX, bulging to tip."""
        far = MESHED_BOX - x
        edges = [Part.LineSegment(V(far, 0, 0), V(x, 0, 0)).toShape(),
                 Part.Arc(V(x, 0, 0), V(tip, MESHED_BOX / 2, 0), V(x, MESHED_BOX, 0)).toShape(),
                 Part.LineSegment(V(x, MESHED_BOX, 0), V(far, MESHED_BOX, 0)).toShape(),
                 Part.LineSegment(V(far, MESHED_BOX, 0), V(far, 0, 0)).toShape()]
        return Part.Face(Part.Wire(edges)).extrude(V(0, 0, 1))

    right = bulging(MESHED_BOX, MESHED_BOX + 1)
    left = bulging(0, -1)
    expect(shapes.shape_key(left) != shapes.shape_key(right), "mirrored onto the same corners: another key")
    expect(shapes.shape_key(right) == shapes.shape_key(right.copy()), "the same shape: the same key")
    expect(shapes.shape_key(Part.Compound([])), "an empty shape has a key too")
    block = Part.makeBox(1, 2, 1, V(MESHED_BOX + MESHED_OFF, MESHED_BOX / 2 - 1, 0))
    separate = FinParams(connection=d.CONNECTION_SEPARATE)
    geometry._kept_clear.clear()
    geometry.check(separate, block, [left], [])
    try:
        geometry.check(separate, block, [right], [])
        refused = False
    except face_frame.FinError:
        refused = True
    expect(refused, "the overlap of a fin mirrored from one that is clear is refused")


def check_meshed_distance():
    """The distance on a mesh says what the shape says, leaves the mesh of the
    shape as it was, where the islands and the centres of mass get theirs, and
    a part too large for it is searched exactly, to the same fins."""
    def cylinder():
        return Part.makeCylinder(ROD_RADIUS, ROD_HEIGHT)

    def triangles_after(shape):
        return len(shape.tessellate(d.ISLAND_MESH_DEFLECTION)[1])

    finer_first = cylinder()
    finer_first.tessellate(d.NEAR_MESH_DEFLECTION)
    usual = triangles_after(cylinder())
    expect(triangles_after(finer_first) > usual, "a finer mesh asked of a shape stays with it")
    meshed_first = cylinder()
    Meshed(meshed_first)
    expect(triangles_after(meshed_first) == usual, "the mesh for distances leaves the mesh of the shape alone")

    box = Part.makeBox(MESHED_BOX, MESHED_BOX, MESHED_BOX)
    near = Meshed(box)

    def rings(x, low=0.0, high=MESHED_BOX, y0=0.0, y1=MESHED_BOX):
        return [[V(x, y, low), V(x, y, high), V(x + 1, y, high), V(x + 1, y, low)] for y in (y0, y1)]

    far = 2 * MESHED_BOX
    off_face = rings(MESHED_BOX + MESHED_OFF)
    expect(abs(near.distance(off_face, far) - MESHED_OFF) < d.TOLERANCE, "a surface beside a face: its distance")
    beyond = rings(MESHED_BOX + MESHED_OFF, y0=MESHED_BOX + MESHED_OFF, y1=2 * MESHED_BOX)
    expect(abs(near.distance(beyond, far) - math.hypot(MESHED_OFF, MESHED_OFF)) < d.TOLERANCE,
           "a surface past an edge: the distance to that edge")
    expect(near.distance(off_face, MESHED_OFF / 2) == MESHED_OFF / 2, "further than asked: what was asked")
    middle = MESHED_BOX / 2
    inside = rings(middle, middle - 1, middle + 1, middle - 1, middle + 1)
    expect(near.distance(inside, MESHED_OFF) == MESHED_OFF, "deep inside it knows no inside: what was asked")
    twice = rings(MESHED_BOX + MESHED_OFF)
    twice[0].insert(1, twice[0][0])
    twice[1].insert(1, twice[1][0])
    expect(abs(near.distance(twice, far) - MESHED_OFF) < d.TOLERANCE, "points alike in a ring change nothing")


    asked_of = []

    class Stub:
        """A shape with the mesh it is given, or none where that is an error."""

        def __init__(self, mesh):
            self.mesh = mesh

        def copy(self):
            return self

        def tessellate(self, deflection):
            asked_of.append(deflection)
            if self.mesh is None:
                raise Part.OCCError("no mesh")
            return self.mesh

    expect(Meshed(Stub(None)).distance(off_face, MESHED_OFF / 2) == MESHED_OFF / 2,
           "a shape the kernel cannot mesh: nothing seen")
    corners = [V(0, 0, 0), V(1, 0, 0), V(2, 0, 0), V(0, 1, 0)]
    flat = Meshed(Stub((corners, [(0, 1, 2), (0, 1, 3)])))
    above = [[V(0, 0, 1), V(1, 0, 1), V(0, 1, 1)], [V(0, 0, 2), V(1, 0, 2), V(0, 1, 2)]]
    expect(len(flat.triangles.a) == 1 and abs(flat.distance(above, far) - 1) < d.TOLERANCE,
           "a triangle of the mesh without area is left out, the distance stays a number")
    expect(asked_of[-2:] == [d.NEAR_MESH_COARSE, d.NEAR_MESH_DEFLECTION], "a small mesh is made fine: %s" % asked_of)
    two_triangles = Stub((corners, [(0, 1, 3), (1, 2, 3)]))
    most = d.NEAR_MESH_MOST
    try:
        d.NEAR_MESH_MOST = 2
        expect(len(Meshed(two_triangles).triangles.a) == 2, "as many triangles as the limit: made fine")
        d.NEAR_MESH_MOST = 1
        asked_of.clear()
        try:
            Meshed(two_triangles)
            told = True
        except shapes.TooManyPairs:
            told = False
        expect(not told and asked_of == [d.NEAR_MESH_COARSE], "past the limit: no fine mesh made: %s" % asked_of)
    finally:
        d.NEAR_MESH_MOST = most

    contour.clear_kept()
    for size in range(1, shapes.MESHES_KEPT + 3):
        shapes.meshed_of(Part.makeBox(size, size, size))
    expect(len(shapes._kept_meshes) == shapes.MESHES_KEPT, "only the last meshes stay: %d" % len(shapes._kept_meshes))
    contour.clear_kept()
    expect(not shapes._kept_meshes, "the meshes kept go with the contours")

    def no_mesh(shape):
        raise AssertionError("asked for a mesh of %s" % shape)

    def out_of_memory(_):
        raise MemoryError

    class Sees:
        """A mesh that says the same distance of everything."""

        def __init__(self, distance):
            self.seen = distance

        def distance(self, _rings, _reach):
            return self.seen

    def side_fins(shape, asked, make):
        """The fins of `asked` under the round side of `shape`, the mesh coming from `make`."""
        number = round_side_of(shape)
        plan = quick_stands.quick_plan(shape, [], [(shape.Faces[number], number)], FinParams(), d.TILT_ANGLE)
        stood = moved(shape, plan.change)
        kept, geometry.meshed_of = geometry.meshed_of, make
        contour.clear_kept()
        geometry._kept_side_fins.clear()
        try:
            return geometry.build(stood, stood.Faces[number], asked)
        finally:
            geometry.meshed_of = kept

    def of_case(kind, degrees, thickness):
        return FinParams(placement=d.PLACEMENT_CENTER, round_fins=kind, round_fin_angle=degrees,
                         fin_thickness=thickness)

    side_fins(cylinder(), of_case(*MATRIX_CASES[0]), no_mesh)

    three = of_case(*MATRIX_CASES[3])
    filleted = matrix_shapes()["fillet"]
    by_mesh = side_fins(filleted, three, shapes.meshed_of)
    out = max(frame.flank_out for frame in by_mesh.frames.values())
    expect(out > FLANK_OUT_MOVED, "a side fin in front of a fillet stands further out: %.3f" % out)
    limit = d.NEAR_MOST_PAIRS
    d.NEAR_MOST_PAIRS = 0
    try:
        too_many = side_fins(filleted, three, shapes.meshed_of)
    finally:
        d.NEAR_MOST_PAIRS = limit
    most, d.NEAR_MESH_MOST = d.NEAR_MESH_MOST, 0
    try:
        too_large = side_fins(filleted, three, shapes.meshed_of)
    finally:
        d.NEAR_MESH_MOST = most
    for reason, exact in (("too many pairs", too_many), ("too large for a mesh", too_large),
                          ("no memory", side_fins(filleted, three, out_of_memory)),
                          ("the mesh sees no place", side_fins(filleted, three, lambda _: Sees(0.0))),
                          ("the mesh sees one at 0", side_fins(filleted, three, lambda _: Sees(far)))):
        expect(exact.touching_z == by_mesh.touching_z
               and abs(exact.fins.Volume - by_mesh.fins.Volume) < MESHED_VOLUME_APART,
               "%s: the same fins, searched exactly" % reason)

    tried = []

    def no_room(_):
        tried.append(1)
        raise MemoryError

    kept, shapes.Meshed = shapes.Meshed, no_room
    contour.clear_kept()
    try:
        for _ in range(2):
            try:
                shapes.meshed_of(box)
                expect(False, "no room for a mesh: not told")
            except shapes.TooManyPairs:
                pass
    finally:
        shapes.Meshed = kept
        contour.clear_kept()
    expect(len(tried) == 1, "no room for a mesh is not tried again: %d" % len(tried))


def check_settled_clear():
    """Asked from a guess, the search ends where it would without one, and asks
    little where the guess is right."""
    resolution, most = SETTLE_RESOLUTION, SETTLE_MOST
    for limit, guess, expected in ((1.7, 1.7, 1.7), (1.7, 1.69, 1.7), (1.7, 1.75, 1.7), (1.7, 0.2, 1.7),
                                   (1.7, 3.0, 1.7),
                                   (0.0, 1.0, 0.0), (0.0, 0.0, 0.0), (1.995, 1.9, 1.995), (3.0, 1.0, None),
                                   (3.0, 2.0, None)):
        asked = []

        def clear(value, limit=limit, asked=asked):
            asked.append(value)
            return value >= limit

        found = geometry._settled_clear(clear, guess, most, resolution)
        expect(found is None if expected is None
               else found == expected or 0 <= found - expected <= resolution + d.TOLERANCE and found <= most,
               "from %g, clear from %g: %s, not %s" % (guess, limit, found, expected))
    asked = []
    geometry._settled_clear(lambda value: asked.append(value) or value >= 1.7, 1.7, most, resolution)
    expect(len(asked) == 2, "a right guess is asked twice: %d" % len(asked))
    expect(geometry._settled_clear(lambda value: False, 1.0, 0.0, resolution) is None,
           "no room and not clear at 0: None")


def check_cut_at_height():
    """A flank cut off at the height of its fin never folds back and is no higher."""
    height, low = 10.0, 3.0
    just_under = height - geometry.FLANK_TOP_HAIR / 2
    for flank, unchanged in (([(1, 9), (2, 5)], True), ([(1, height), (2, 5)], True), ([(1, 11), (2, 5)], False),
                             ([(1, 12), (1, 11), (2, 5)], False), ([(1, 12), (1.5, just_under), (2, 5)], False),
                             ([(1, 12), (1.5, height), (2, 5)], False), ([(1, 9.9), (1.5, 11), (2, 5)], False),
                             ([(1, 12), (2, 11)], False)):
        cut = geometry._cut_at_height(flank, height, low)
        heights = [z for _, z in cut]
        expect(len(cut) == len(flank) and max(heights) <= height and heights[-1] >= low
               and all(a > b for a, b in zip(heights, heights[1:])) and (cut == flank) == unchanged,
               "%s cut at %g falls without folding: %s" % (flank, height, cut))


def check_three_round_fins():
    """Three fins under a whole round side: the one under the lowest line as it
    stands alone, one parallel on each side, clear of the part, their tines
    ending on it across their whole width, overlapping feet joined for export."""
    one = FinParams(placement=d.PLACEMENT_CENTER)
    three = FinParams(placement=d.PLACEMENT_CENTER, round_fins=d.ROUND_FINS_THREE)
    expect(FinParams().round_fins == d.ROUND_FINS_ONE and FinParams().round_fin_angle == d.ROUND_FIN_ANGLE,
           "new fins stand under a round side alone, the side fins 30 degrees round if asked for")
    for wrong in (0.0, -1.0, d.ROUND_FIN_ANGLE_MIN / 2, d.ROUND_FIN_ANGLE_MAX + 1):
        try:
            FinParams(round_fin_angle=wrong).validate()
            expect(False, "a side fin angle of %g is refused" % wrong)
        except ParamError:
            expect(True, "a side fin angle of %g is refused" % wrong)
    rod = Part.makeCylinder(ROD_RADIUS, ROD_HEIGHT)
    tube = rod.cut(Part.makeCylinder(BORE_RADIUS, ROD_HEIGHT))
    step = rod.fuse(Part.makeCylinder(STEP_RADIUS, ROD_HEIGHT, V(0, 0, ROD_HEIGHT))).removeSplitter()
    for name, shape in (("cylinder", rod), ("tube", tube), ("shaft with a step", step)):
        stood, side = stood_on_free_rim(shape)
        alone = geometry.build(stood, stood.Faces[side], one)
        result = geometry.build(stood, stood.Faces[side], three)
        pitch = face_frame.beside_lowest(ROD_RADIUS, d.ROUND_FIN_ANGLE)
        expect(result.numbers == [1, 2, 3] and result.planned == 3
               and abs(result.positions[1] - alone.positions[0]) < d.TOLERANCE
               and abs(result.positions[2] - result.positions[1] - pitch) < d.TOLERANCE
               and abs(result.positions[1] - result.positions[0] - pitch) < d.TOLERANCE,
               "%s: three fins, a radius share apart, the middle one where it stands alone" % name)
        expect(abs(result.bodies[1].Volume - alone.bodies[0].Volume) < 1e-6
               and result.touching_z[2] == alone.touching_z[1],
               "%s: the middle fin of three is the fin alone" % name)
        expect(all(tine.isValid() and tine.Volume > 0 for tine in result.tines),
               "%s: every tine is a valid solid, also with a slanted end" % name)
        off = max(abs(tine.distToShape(stood)[0] - three.clearance) for tine in result.tines)
        expect(off < d.TINE_END_TOLERANCE, "%s: every tine ends the clearance off the part, off by %.4f" % (name, off))
        if shape is not step:
            own = result.frames[3]
            low, high = tine_rows.side_tine(three, own, result.positions[2], result.thickness, result.touching_z[3][0])
            t_from, s_from = (low[0][0] + low[1][0]) / 2, (low[0][1] + low[1][1]) / 2
            t_to, s_to = low[3]
            z_first = own.bed_z + result.touching_z[3][0]
            flank_there = geometry.flank_at(three, own, z_first + three.tine_height / 2) + tine_rows.flank_bend(
                own, result.positions[2] + result.thickness / 2)
            run = (flank_there - s_from) / (s_to - s_from)
            at_flank = t_from + run * (t_to - t_from)
            expect(abs(at_flank - (result.positions[2] + result.thickness / 2)) < TINE_MIDDLE_TOLERANCE,
                   "%s: a tine of a side fin leaves it in the middle of its thickness, off by %.3f"
                   % (name, at_flank - (result.positions[2] + result.thickness / 2)))
            middle = (own.along_min + own.along_max) / 2
            height = own.bed_z + result.touching_z[3][0] + three.tine_height / 2
            axis_s = own.s_face(height) - own.radius / own.n_out
            aim = (s_to - s_from) * (middle - t_from) - (t_to - t_from) * (axis_s - s_from)
            expect(t_to < t_from and s_to < s_from and abs(aim) < AIM_TOLERANCE,
                   "%s: a tine of a side fin runs level straight at the axis, off by %.5f" % (name, aim))
        expect(result.fins.common(stood).Volume < d.TOLERANCE, "%s: no fin reaches into the part" % name)
        steep = max(steepest_step(result.bodies[k], result.frames[n]) for k, n in ((0, 1), (2, 3)))
        expect(steep <= OVERHANG_LAYER + GAP_ACROSS_FIN,
               "%s: no layer of a side fin hangs past the one below by more than 45 degrees: %.3f" % (name, steep))
        nearest = min(body.distToShape(stood)[0] for body in result.bodies)
        # Near the outer edge of a side fin the gap is as near the inner one.
        outer = result.positions[2] + result.thickness - PLANE_INSIDE
        ring = [result.frame.point(outer, s, z) for s, z in ((-BIG, -BIG), (BIG, -BIG), (BIG, BIG), (-BIG, BIG))]
        plane = Part.Face(Part.makePolygon(ring + ring[:1]))
        at_outer = result.bodies[2].common(plane).distToShape(stood)[0]
        # A step asks the whole fin to stand a little further out.
        expect(abs(at_outer - three.gap) < GAP_ACROSS_FIN or (shape is step and at_outer > three.gap),
               "%s: the side fin keeps the gap across its thickness too: %.3f at its outer edge" % (name, at_outer))
        expect(nearest > three.gap - d.CONTOUR_TOLERANCE - GAP_ACROSS_FIN,
               "%s: the side fins keep the gap from the side: %.3f" % (name, nearest))
        lowest = min(result.touching_z[1])
        expect(lowest > min(result.touching_z[2]) and result.touching_z[1] == result.touching_z[3],
               "%s: the side fins start to hold higher up, alike: from %.2f mm" % (name, lowest))
        expect(not any("miss" in w or "reach more" in w for w in result.warnings),
               "%s: no tine said to miss or cut in: %s" % (name, result.warnings))
        for number, kept in ((2, [1, 3]), (1, [2, 3])):
            fewer = geometry.build(stood, stood.Faces[side], three, left_out=[number])
            expect(fewer.numbers == kept and fewer.planned == 3,
                   "%s: fin %d removed, the others stay in their places" % (name, number))
        moved_fin = geometry.build(stood, stood.Faces[side], three, shifts={1: SIDE_FIN_MOVE, 2: SIDE_FIN_MOVE})
        expect(abs(moved_fin.positions[0] - result.positions[0] - SIDE_FIN_MOVE) < d.TOLERANCE
               and abs(moved_fin.positions[1] - result.positions[1]) < d.TOLERANCE
               and moved_fin.positions[2] == result.positions[2],
               "%s: a side fin moved by hand stands there, the one under the lowest line stays" % name)
        off = max(abs(tine.distToShape(stood)[0] - three.clearance) for tine in moved_fin.tines)
        expect(off < d.TINE_END_TOLERANCE and moved_fin.fins.common(stood).Volume < d.TOLERANCE,
               "%s: moved, its tines end the clearance off the part, off by %.4f" % (name, off))
        too_far = face_frame.beside_lowest(ROD_RADIUS, d.ROUND_FIN_ANGLE_MAX) - pitch + SIDE_FIN_MOVE
        try:
            geometry.build(stood, stood.Faces[side], three, shifts={3: too_far})
            expect(False, "%s: a side fin moved past the furthest angle is refused" % name)
        except face_frame.HandEditError:
            expect(True, "%s: a side fin moved past the furthest angle is refused" % name)

    two = FinParams(placement=d.PLACEMENT_CENTER, round_fins=d.ROUND_FINS_TWO)
    for name, shape in (("cylinder", rod), ("tube", tube), ("shaft with a step", step)):
        stood, side = stood_on_free_rim(shape)
        alone = geometry.build(stood, stood.Faces[side], one)
        result = geometry.build(stood, stood.Faces[side], two)
        pitch = face_frame.beside_lowest(ROD_RADIUS, d.ROUND_FIN_ANGLE)
        expect(result.numbers == [1, 2] and result.planned == 2
               and abs(result.positions[0] - alone.positions[0] + pitch) < d.TOLERANCE
               and abs(result.positions[1] - alone.positions[0] - pitch) < d.TOLERANCE,
               "%s: two fins, one on each side of the lowest line, none under it" % name)
        off = max(abs(tine.distToShape(stood)[0] - two.clearance) for tine in result.tines)
        expect(off < d.TINE_END_TOLERANCE and result.fins.common(stood).Volume < d.TOLERANCE,
               "%s: two fins, every tine ends the clearance off the part, off by %.4f" % (name, off))
        expect(min(result.touching_z[1]) > min(alone.touching_z[1]),
               "%s: two fins start to hold higher up than the one under the lowest line" % name)
        over = geometry.build(stood, stood.Faces[side], two, shifts={1: pitch})
        expect(over.numbers == [1, 2] and abs(over.positions[0] - alone.positions[0]) < d.TOLERANCE
               and over.fins.common(stood).Volume < d.TOLERANCE,
               "%s: of two fins one moved under the lowest line stands there, clear of the part" % name)
    # Thick fins and thin rods: the flank stays at the gap between its planes too.
    for radius, thickness, degrees, kind in ((10.0, 3.0, 30.0, d.ROUND_FINS_THREE),
                                             (10.0, 2.0, 45.0, d.ROUND_FINS_THREE),
                                             (20.0, 4.0, 30.0, d.ROUND_FINS_THREE),
                                             (5.0, 2.0, 30.0, d.ROUND_FINS_TWO),
                                             (3.0, 0.0, 45.0, d.ROUND_FINS_THREE), (2.5, 0.0, 45.0, d.ROUND_FINS_TWO)):
        thick_rod = Part.makeCylinder(radius, ROD_HEIGHT)
        number = round_side_of(thick_rod, radius)
        thick_plan = quick_stands.quick_plan(thick_rod, [], [(thick_rod.Faces[number], number)], one, d.TILT_ANGLE)
        thick_stood = moved(thick_rod, thick_plan.change)
        asked = FinParams(placement=d.PLACEMENT_CENTER, round_fins=kind, round_fin_angle=degrees,
                          fin_thickness=thickness)
        built = geometry.build(thick_stood, thick_stood.Faces[number], asked)
        closest = min(body.distToShape(thick_stood)[0] for body in built.bodies)
        expect(abs(closest - asked.gap) < d.CONTOUR_TOLERANCE + d.TOLERANCE,
               "R %g, fin %g mm thick, %g degrees, %s: the gap holds, %.4f at its closest"
               % (radius, built.thickness, degrees, kind, closest))
    # Standing on a fillet: the fin does not follow it down to its foot.
    bottom_rim = [e for e in rod.Edges if orient.is_rim(e) and e.BoundBox.ZMax < 1]
    filleted = rod.makeFillet(FILLET_RADIUS, bottom_rim)
    number = round_side_of(filleted)
    fillet = next(k for k, f in enumerate(filleted.Faces) if isinstance(f.Surface, Part.Toroid))
    plain_plan = quick_stands.quick_plan(filleted, [], [(filleted.Faces[number], number),
                                                        (filleted.Faces[fillet], fillet)], one, d.TILT_ANGLE)
    on_fillet = moved(filleted, plain_plan.change)
    for params in (one, three):
        built = geometry.build(on_fillet, on_fillet.Faces[number], params)
        line = built.frame.contour
        start = built.frame.face_bottom_z - built.frame.bed_z
        slope = -built.frame.n_z / built.frame.n_out
        lower = [height for height in line.heights if height < start - d.TOLERANCE]
        expect(lower and not any(line.rests(height, height) for height in lower)
               and all(abs(line.flank(height) - (line.flank(start) - (start - height) * slope)) < GAP_ACROSS_FIN
                       for height in lower),
               "standing on a fillet the fin goes on in the line of the side down to its foot, no tine on the fillet")
    # Standing on a chamfer higher than the closest tine spacing, or one just
    # short of CONTOUR_OWN_PART: a chamfer still, not a thinner part, and no
    # tine rests on it.
    closest = FinParams(placement=d.PLACEMENT_CENTER, tine_spacing=one.least_tine_spacing)
    for axial, params in ((CHAMFER_LONG, closest), (CHAMFER_TALL, one)):
        chamfered = rod.makeChamfer(axial, CHAMFER_SHORT, bottom_rim)
        cone = next(f for f in chamfered.Faces if isinstance(f.Surface, Part.Cone))
        small = min((e for e in cone.Edges if orient.is_rim(e)), key=lambda e: e.Curve.Radius)
        number = round_side_of(chamfered)
        on_chamfer = moved(chamfered, orient.stand_on_rim(chamfered, small, orient.side_tilt(d.TILT_ANGLE),
                                                          chamfered.Faces[number]))
        built = geometry.build(on_chamfer, on_chamfer.Faces[number], params)
        start = built.frame.face_bottom_z - built.frame.bed_z
        lower = [height for height in built.frame.contour.heights if height < start - d.TOLERANCE]
        expect(lower and not any(built.frame.contour.rests(height, height) for height in lower),
               "standing on a chamfer %g mm long, tine spacing %.1f mm: no tine on the chamfer"
               % (axial, params.tine_spacing))
    # A rib beside the wall of a side fin, high up: moving out gains nothing there.
    stood, side = stood_on_free_rim(rod)
    free = geometry.build(stood, stood.Faces[side], three)
    wall = free.positions[2] - RIB_OFF_WALL - RIB_WIDTH
    level = free.heights[3] * RIB_HEIGHT_SHARE
    low, high = free.frame.bed_z + level, free.frame.bed_z + level + RIB_WIDTH
    start = free.frame.s_face(low) - RIB_INTO_PART
    rib = free.frame.section(wall, [(start, low), (start + RIB_LENGTH, low), (start + RIB_LENGTH, high), (start, high)],
                             RIB_WIDTH)
    ribbed = stood.fuse(rib).removeSplitter()
    number = round_side_of(ribbed)
    lowered = geometry.build(ribbed, ribbed.Faces[number], three)
    expect(lowered.heights[3] < level and lowered.heights[3] < free.heights[3] and lowered.heights[1] > level
           and any("end lower" in w for w in lowered.warnings),
           "a rib beside its wall: that side fin ends below it, said so, the other stays: %.1f, %.1f"
           % (lowered.heights[3], lowered.heights[1]))
    # A shaft whose thin step ends the side fins lower than the fin between them.
    thin_step = rod.fuse(Part.makeCylinder(THIN_STEP_RADIUS, ROD_HEIGHT, V(0, 0, ROD_HEIGHT))).removeSplitter()
    stood, side = stood_on_free_rim(thin_step)
    free = geometry.build(stood, stood.Faces[side], three)
    side_top = free.frames[1].room
    middle_top = free.frame.room
    expect(side_top < middle_top, "the side fins end lower on a thin step than the fin between them")
    high = (side_top + middle_top) / 2
    capped = geometry.build(stood, stood.Faces[side], FinParams(placement=d.PLACEMENT_CENTER, fin_height=high,
                                                                round_fins=d.ROUND_FINS_THREE))
    expect(abs(capped.heights[2] - high) < d.TOLERANCE and capped.heights[1] <= side_top + d.TOLERANCE
           and capped.heights[3] <= side_top + d.TOLERANCE and any("end below" in w for w in capped.warnings),
           "a fin height above the side fins: they end at their contour, said so, the middle one keeps it")

    stood, side = stood_on_free_rim(rod)
    rectangle = geometry.build(stood, stood.Faces[side],
                               FinParams(placement=d.PLACEMENT_CENTER, round_fins=d.ROUND_FINS_THREE,
                                         foot_shape=d.FOOT_RECTANGLE))
    expect(rectangle.fins.common(stood).Volume < d.TOLERANCE
           and rectangle.frames[3].flank_out < FLANK_OUT_LITTLE,
           "a rectangular foot beside the lowest line clears the part, the flank at most a little further out")
    whole = geometry.build(stood, stood.Faces[side], three).fins
    joined = geometry.joined(whole)
    overlap = sum(a.common(b).Volume for k, a in enumerate(whole.Solids) for b in whole.Solids[k + 1:])
    expect(overlap > d.TOLERANCE and len(joined.Solids) == 1 and joined.isValid()
           and abs(joined.Volume - (sum(s.Volume for s in whole.Solids) - overlap)) < JOINED_VOLUME_TOLERANCE,
           "overlapping feet join into one valid solid, the overlap counted once")
    expect(len(whole.Solids) == 3, "the fins stay apart in the document, to be picked and removed")
    apart = Part.makeCompound([Part.makeBox(1, 1, 1), Part.makeBox(1, 1, 1, V(5, 0, 0))])
    expect(geometry.joined(apart) is apart, "solids apart are not joined")
    touching = Part.makeCompound([Part.makeBox(1, 1, 1), Part.makeBox(1, 1, 1, V(1, 0, 0))])
    expect(geometry.joined(touching) is touching, "solids that only touch are not joined")
    some = Part.makeCompound([Part.makeBox(2, 1, 1), Part.makeBox(2, 1, 1, V(1, 0, 0)),
                              Part.makeBox(1, 1, 1, V(9, 0, 0))])
    expect(len(geometry.joined(some).Solids) == 2, "of three solids the two that overlap join, the third stays")

    try:
        geometry.build(stood, stood.Faces[side], FinParams(placement=d.PLACEMENT_CENTER, follow_contour=False,
                                                           round_fins=d.ROUND_FINS_THREE))
        expect(False, "three fins without the contour are refused")
    except face_frame.FinError as error:
        expect("Follow the contour" in str(error), "three fins without the contour say to follow it: %s" % error)
    thin = Part.makeCylinder(THIN_ROD_RADIUS, ROD_HEIGHT)
    thin_side = round_side_of(thin, THIN_ROD_RADIUS)
    thin_plan = quick_stands.quick_plan(thin, [], [(thin.Faces[thin_side], thin_side)], one, d.TILT_ANGLE)
    stood_thin = moved(thin, thin_plan.change)
    try:
        geometry.build(stood_thin, stood_thin.Faces[thin_side], three)
        expect(False, "three fins on a thin rod are refused")
    except face_frame.FinError as error:
        expect("do not fit" in str(error), "three fins on a thin rod do not fit: %s" % error)

    slot = slot_on_end()
    built = []
    for number in [i for i, f in enumerate(slot.Faces) if orient.is_curved_side(f)]:
        try:
            built.append(geometry.build(slot, slot.Faces[number], three))
        except face_frame.FinError:
            pass
    expect(built and all(len(result.positions) == 1 for result in built),
           "part of a side keeps its one fin with three asked for")


def flank_slopes(result, p):
    """How far the flank of `result` runs inward per mm up, its steepest."""
    outline = result.frame.contour.outline(p.foot_height, result.height)
    return max((s_low - s_high) / (z_high - z_low)
               for (s_high, z_high), (s_low, z_low) in zip(outline, outline[1:]) if z_high > z_low)


def check_contour_pieces():
    """The pieces of a cut as arrays (contour._Pieces): how far out they reach
    at a height, which piece lies outermost with its value, and where the
    run between two samples is lifted: every row of its tables."""
    radius, share, tolerance = 0.2, d.CONTOUR_SHARE, d.TOLERANCE
    heights = [0.0, 1.0, 2.0]

    def open_piece(start, end):
        """A piece of an open loop, which tells neither its side nor a mitre."""
        return (start, end, 0.0, 0.0, None)

    def reach(pieces, z, around=radius):
        """How far out `pieces` reach at height z, asked of every piece."""
        made = contour._Pieces(pieces, around)
        return made.reach(made.stretches(heights), contour._stretch(heights, z), z)

    def close(value, wanted):
        return value is not None and abs(value - wanted) < tolerance

    sloping, level = open_piece((0.0, 0.0), (1.0, 1.0)), open_piece((0.0, 1.0), (2.0, 1.0))
    expect(close(reach([sloping], 0.5), 0.5 + radius * math.sqrt(2)) and close(reach([sloping], 0.5, 0.0), 0.5),
           "at a height on a sloping piece the reach is the point on its line, the radius out along its "
           "normal; with no radius the point of the piece itself: %s, %s"
           % (reach([sloping], 0.5), reach([sloping], 0.5, 0.0)))
    expect(close(reach([level], 1.0), 2.0 + radius) and close(reach([level], 1.0 + radius), 2.0)
           and close(reach([level], 1.0 - radius), 2.0),
           "at the height of a level piece the reach is its outer end and the radius; the radius above "
           "and below it, where its two lines lie, its outer end: %s, %s, %s"
           % (reach([level], 1.0), reach([level], 1.0 + radius), reach([level], 1.0 - radius)))
    expect(reach([level], 1.0 + radius + BESIDE + tolerance) is None and reach([level], 0.5) is None
           and reach([], 1.0) is None,
           "above or below every piece by more than the radius, and of no pieces, there is no reach")
    point = open_piece((1.0, 1.0), (1.0, 1.0))
    made = contour._Pieces([point], radius)
    expect(close(reach([point], 1.0), 1.0 + radius) and not made.has_line.any(),
           "a piece without length reaches the radius round its one point and has no line: %s"
           % reach([point], 1.0))
    told = ((0.0, 0.0), (0.0, 2.0), 0.0, 0.0, (1.0, 0.0))
    away = ((0.0, 0.0), (0.0, 2.0), 0.0, 0.0, (-1.0, 0.0))
    lines = [int(contour._Pieces([piece], radius).has_line.sum()) for piece in (told, sloping, level)]
    expect(lines == [1, 1, 2] and close(reach([told], 1.0), radius) and close(reach([away], 1.0), -radius),
           "a piece of a loop that tells its side has one line, out of the part, a sloping piece of an open "
           "loop one, a level one two; between its ends an upright piece reaches to its line, the radius to "
           "the side its loop calls out of the part, be that out or in: %s, %s, %s"
           % (lines, reach([told], 1.0), reach([away], 1.0)))

    # Which piece lies outermost at a height, and what it tells: three pieces reaching as far out at
    # most, so they stay in the order given, at one height each within the tolerance of the next and
    # the last more than that past the first.
    def crossing(at_half):
        """A piece from the bed up to (2, 1) that lies `at_half` out at half a mm up."""
        return open_piece((2 * at_half - 2.0, 0.0), (2.0, 1.0))

    near, middle, far = (crossing(1.0 + step * tolerance) for step in (0.0, 0.8, 1.6))
    tells = {near[0]: -3.0, middle[0]: -2.0, far[0]: -1.0}
    halves = [0.0, 0.5, 1.0]

    def facing(*pieces):
        return contour._Pieces(list(pieces), 0.0).facing(halves, lambda piece: tells[piece[0]])[1]

    up, down, alone, short = facing(near, middle, far), facing(far, middle, near), facing(middle), facing(far, near)
    expect(close(up[0], 1.0 + 1.6 * tolerance) and up[1] == -3.0 and close(down[0], 1.0 + 1.6 * tolerance)
           and down[1] == -2.0,
           "three pieces at a height, each within the tolerance of the next: taken from the nearest up, the "
           "smallest value of all three is kept; from the furthest down, the nearest is more than the "
           "tolerance short and left out: %s, %s" % (up, down))
    expect(alone == (alone[0], -2.0) and close(alone[0], 1.0 + 0.8 * tolerance) and short[1] == -1.0
           and facing(near, far)[1] == -1.0,
           "one piece at a height gives its reach and its value; a piece more than the tolerance short of "
           "the furthest gives nothing, and one further than those before by more takes over with its "
           "value alone: %s, %s, %s" % (alone, short, facing(near, far)))
    # Many pieces at one height, reaching about as far, in no order: what is kept is what taking
    # them one after the other keeps, by the rule as it reads.
    many = [crossing(1.0 + tolerance * 2.5 * math.sin(7.0 * k)) for k in range(4 * contour.FIRST_BLOCK)]
    values = {piece[0]: math.cos(3.0 * k) for k, piece in enumerate(many)}
    reach_at_half, kept = None, None
    for piece in many:
        r, value = (piece[0][0] + 2.0) / 2, values[piece[0]]
        if reach_at_half is None or r > reach_at_half + tolerance:
            reach_at_half, kept = r, value
        elif r >= reach_at_half - tolerance:
            reach_at_half, kept = max(r, reach_at_half), min(value, kept)
    found = contour._Pieces(many, 0.0).facing(halves, lambda piece: values[piece[0]])[1]
    expect(len(set(values)) == len(many) and close(found[0], reach_at_half) and found[1] == kept,
           "%d pieces at one height, reaching about as far in no order: the reach and the value kept are "
           "those of taking them one after the other: %s, wanted %s" % (len(many), found, (reach_at_half, kept)))
    expect(contour._Pieces([], 0.0).facing(halves, lambda piece: 0.0) == [None] * 3
           and contour._Pieces([crossing(1.0)], 0.0).facing([2.0, 3.0, 4.0], lambda piece: 0.0) == [None] * 3,
           "no piece at a height, no reach there")

    # The run between two samples, lifted where a corner between them reaches past it.
    wall = open_piece((0.0, 0.0), (0.0, 2.0))

    def lifted(*pieces):
        made = contour._Pieces(list(pieces), 0.0)
        reaches = made.reaches(heights)
        return reaches, made.lifted(reaches, heights)

    def ledge(out):
        """A level piece half a mm up, from the wall `out` out."""
        return open_piece((0.0, 0.5), (out, 0.5))

    smooth, corner = lifted(wall), lifted(wall, ledge(2.0))
    expect(smooth == ([0.0] * 3, [0.0] * 3) and corner[0] == [0.0] * 3 and corner[1] == [2.0, 2.0, 0.0],
           "a smooth contour is lifted nowhere; a ledge between two samples lifts both to where it reaches, "
           "the sample above them stays: %s" % (corner,))
    expect(lifted(wall, ledge(share))[1] == [0.0] * 3
           and lifted(wall, ledge(share + BESIDE))[1][:2] == [share + BESIDE] * 2,
           "a corner past the run between two samples by the share lifts nothing, one past it by more does")
    started = lifted(open_piece((0.0, 0.3), (0.0, 2.0)))
    empty = contour._Pieces([], radius)
    expect(started == ([None, 0.0, 0.0], [0.0] * 3)
           and lifted(open_piece((0.0, 1.3), (0.0, 2.0))) == ([None, None, 0.0], [None, 0.0, 0.0])
           and empty.reaches(heights) == [None] * 3 and empty.lifted([None] * 3, heights) == [None] * 3,
           "a sample without a reach, below where the contour starts, gets the most the pieces reach in the "
           "stretch above it; one with nothing in either stretch beside it stays without; of no pieces "
           "nothing reaches and nothing is lifted: %s" % (started,))

    # Many pieces, most of them at the back: those not asked add nothing.
    back = [open_piece((-5.0 - k * 0.01, 0.0), (-5.0 - k * 0.01, 2.0)) for k in range(3 * contour.FIRST_BLOCK)]
    front = [wall, ledge(2.0)]
    asked = []
    real = contour._Pieces._between

    def counted(self, numbers, low, high):
        asked.append(len(numbers))
        return real(self, numbers, low, high)

    contour._Pieces._between = counted
    try:
        behind = lifted(*(back + front))
    finally:
        contour._Pieces._between = real
    expect(behind == corner and sum(asked) < len(back),
           "with hundreds of pieces behind the front the reach and the lift are those of the front alone, "
           "and most of those behind are not asked: %d askings of %d pieces" % (sum(asked), len(back) + 2))


def check_contour():
    """Under a whole round side the fin follows the contour of the part up to
    its top: over a step to a thinner part, a groove and a curved outline;
    tines rest only where the part faces down; a tube holds it
    at its front wall."""
    p = FinParams(placement=d.PLACEMENT_CENTER)
    alone = FinParams(placement=d.PLACEMENT_CENTER, follow_contour=False)
    inward = 1 / math.tan(math.radians(d.FIN_FLANK_ANGLE))
    rod = Part.makeCylinder(ROD_RADIUS, ROD_HEIGHT)
    step = rod.fuse(Part.makeCylinder(STEP_RADIUS, ROD_HEIGHT, V(0, 0, ROD_HEIGHT))).removeSplitter()
    stood, side = stood_on_free_rim(step)
    short = geometry.build(stood, stood.Faces[side], alone)
    tall = geometry.build(stood, stood.Faces[side], p)
    # The stretch on the thinner part: the first above the top of the side
    # with room for a tine.
    side_top = short.frame.face_top_z - short.frame.bed_z
    thinner = min(low for low, high in tall.frame.contour.bands()
                  if low > side_top and high - low >= p.tine_height)
    upper = [z for z in tall.tine_z if z >= thinner - d.TOLERANCE]
    expect(tall.height > short.height + ROD_HEIGHT / 2 and upper
           and upper[0] < thinner + p.layer_height + d.TOLERANCE,
           "along the contour the fin reaches up the thinner part, its tines starting anew at its bottom: "
           "%.1f mm high, %.1f under the side alone" % (tall.height, short.height))
    again = geometry.build(stood, stood.Faces[side], FinParams(placement=d.PLACEMENT_CENTER, fin_height=short.height))
    other = geometry.build(stood, stood.Faces[side], FinParams(placement=d.PLACEMENT_CENTER, contour_bridge=1.0))
    wider = geometry.build(stood, stood.Faces[side], FinParams(placement=d.PLACEMENT_CENTER,
                                                                contour_gap=2 * p.contour_gap))
    expect(again.frame.contour is tall.frame.contour and other.frame.contour is not tall.frame.contour
           and wider.frame.contour.flank_at != tall.frame.contour.flank_at,
           "the contour is worked out once for the part as it stands, again for another bridge or gap without "
           "tines")
    expect(flank_slopes(tall, p) <= inward + d.TOLERANCE,
           "the flank follows the step, inward no steeper than %g degrees allow" % d.FIN_FLANK_ANGLE)
    expect(all(abs(tine.distToShape(stood)[0] - p.clearance) < d.TINE_END_TOLERANCE for tine in tall.tines) and not [
        w for w in tall.warnings if "rim" not in w],
           "every tine rests on the part, none on the end face of the step looking up: %s" % tall.warnings)
    # The end face of the step, looking up: the larger gap kept from its
    # middle, under the fin.
    end_face = next(f for f in stood.Faces if f.findPlane() is not None and f.normalAt(0, 0).z > d.TOLERANCE
                    and abs(f.Area - math.pi * (ROD_RADIUS ** 2 - STEP_RADIUS ** 2)) < d.TOLERANCE)
    normal = end_face.normalAt(0, 0)
    towards = tall.frame.out - normal * tall.frame.out.dot(normal)
    towards.normalize()
    middle_of_end = end_face.CenterOfMass + towards * (ROD_RADIUS + STEP_RADIUS) / 2
    expect(min(body.distToShape(Part.Vertex(middle_of_end))[0] for body in tall.bodies)
           >= p.contour_gap - d.TOLERANCE,
           "over the end face of the step, looking up, the fin keeps %.2f mm from it" % p.contour_gap)
    # A chamfer on the edge of the step stands upright once the side leans:
    # no tine on it, and the gap where the tines rest, not the larger one.
    edge = [e for e in step.Edges if orient.is_rim(e) and abs(e.Curve.Radius - ROD_RADIUS) < d.TOLERANCE
            and e.BoundBox.ZMin > ROD_HEIGHT - d.TOLERANCE]
    stood, side = stood_on_free_rim(step.makeChamfer(CHAMFER_SHORT, edge))
    edged = geometry.build(stood, stood.Faces[side], p)
    cone = next(f for f in stood.Faces if isinstance(f.Surface, Part.Cone))
    expect(min(body.distToShape(cone)[0] for body in edged.bodies) < p.contour_gap - d.TOLERANCE,
           "along an upright chamfer on the edge of the step the fin keeps the gap, not %.2f mm" % p.contour_gap)

    # Stood on the free rim of the thinner part, fins for the side of the
    # thicker one: the side starts above the bed, and the fin follows the
    # thinner part below it, its tines resting there, as on a step above.
    thin_rim = next(e for e in step.Edges if orient.is_rim(e) and abs(e.Curve.Radius - STEP_RADIUS) < d.TOLERANCE
                    and e.BoundBox.ZMin > 2 * ROD_HEIGHT - d.TOLERANCE)
    side = round_side_of(step)
    plan = next(plan for plan in quick_stands.quick_plans(step, [(thin_rim, None)], [], p, d.TILT_ANGLE)
                if plan.number == side)
    stood = moved(step, plan.change)
    below = geometry.build(stood, stood.Faces[side], p)
    side_start = below.frame.face_bottom_z - below.frame.bed_z
    under = [z for z in below.touching_z[1] if z + p.tine_height <= side_start]
    expect(side_start > ROD_HEIGHT / 2 and len(under) > 1,
           "on the thinner part below the side the fin follows it, tines resting there: %d below %.1f mm"
           % (len(under), side_start))
    # Just past CONTOUR_OWN_PART of the thinner part carrying tines, the fin
    # follows it; just short of it, it goes on in the line of the side.
    for height, follows in ((THIN_PART_CARRIES, True), (THIN_PART_SHORT, False)):
        short_step = rod.fuse(Part.makeCylinder(STEP_RADIUS, height, V(0, 0, ROD_HEIGHT))).removeSplitter()
        short_rim = next(e for e in short_step.Edges if orient.is_rim(e)
                         and abs(e.Curve.Radius - STEP_RADIUS) < d.TOLERANCE
                         and e.BoundBox.ZMin > ROD_HEIGHT + height - d.TOLERANCE)
        side = round_side_of(short_step)
        plan = next(plan for plan in quick_stands.quick_plans(short_step, [(short_rim, None)], [], p, d.TILT_ANGLE)
                    if plan.number == side)
        stood = moved(short_step, plan.change)
        below = geometry.build(stood, stood.Faces[side], p)
        side_start = below.frame.face_bottom_z - below.frame.bed_z
        under = [z for z in below.touching_z[1] if z + p.tine_height <= side_start]
        expect(bool(under) == follows,
               "a thinner part %g mm high below the side: the fin %s, %d tines below %.1f mm"
               % (height, "follows it" if follows else "goes on in the line of the side", len(under), side_start))

    # A groove round the middle of the shaft, lower than the bridge: spanned,
    # unless the bridge is 0.
    middle = ROD_HEIGHT / 2
    ring = Part.makeCylinder(ROD_RADIUS, GROOVE_LENGTH, V(0, 0, middle)).cut(
        Part.makeCylinder(ROD_RADIUS - GROOVE_DEPTH, GROOVE_LENGTH, V(0, 0, middle)))
    grooved_rod = rod.cut(ring)
    stood, side = stood_on_free_rim(grooved_rod)
    bridged = geometry.build(stood, stood.Faces[side], p)
    # The gap kept as small over the lower wall of the groove, which looks up.
    followed = geometry.build(stood, stood.Faces[side], FinParams(placement=d.PLACEMENT_CENTER, contour_bridge=0.0,
                                                                  contour_gap=FinParams().gap))
    into = max(spanned - inside for spanned, inside
               in zip(bridged.frame.contour.flank_at, followed.frame.contour.flank_at))
    expect(not [w for w in bridged.warnings if "rim" not in w] and into > GROOVE_DEPTH / 2
           and flank_slopes(followed, p) <= inward + d.TOLERANCE,
           "a groove lower than the bridge is spanned without a word; with the bridge 0 the flank goes into it")

    # A pocket in the side, longer than the bridge, that no tine rests in:
    # the flank runs straight past it on the side, the tines go on above.
    stood, side = stood_on_free_rim(rod)
    frame = face_frame.frame_of(stood, stood.Faces[side])
    normal, along = frame.normal(), frame.along
    up_side = normal.cross(along)
    length, width, depth = POCKET_SIZE
    middle_z = frame.bed_z + ROD_HEIGHT / 2
    centre = frame.point((frame.along_min + frame.along_max) / 2, frame.s_face(middle_z), middle_z)
    corner = centre - along * (width / 2) - up_side * (length / 2) - normal * depth
    pocket = Part.makeBox(width, length, 2 * depth)
    pocket.Placement = App.Placement(App.Matrix(along.x, up_side.x, normal.x, corner.x,
                                                along.y, up_side.y, normal.y, corner.y,
                                                along.z, up_side.z, normal.z, corner.z, 0, 0, 0, 1))
    pocketed = stood.cut(pocket)
    past = geometry.build(pocketed, pocketed.Faces[round_side_of(pocketed)], p)
    plain = geometry.build(stood, stood.Faces[side], p)
    # Neither in nor out, also at the edges of the pocket: no wedge there.
    off = [a - b for a, b in zip(past.frame.contour.flank_at, plain.frame.contour.flank_at)]
    expect(min(off) > -d.TOLERANCE and max(off) < d.TOLERANCE and not [w for w in past.warnings if "rim" not in w]
           and len(past.tines) < len(plain.tines),
           "a pocket longer than the bridge with no tine in it is spanned: the flank as without it, %.3f to %.3f "
           "mm off, and nothing said" % (min(off), max(off)))

    # A curved outline on top of the cylinder, narrowing slower than the side
    # leans: the fin follows it, its tines on it.
    profile = Part.BSplineCurve()
    profile.interpolate([V(radius, 0, ROD_HEIGHT * (1 + k / (len(SPLINE_RADII) - 1)))
                         for k, radius in enumerate(SPLINE_RADII)])
    top = profile.EndPoint
    outline = Part.Wire([Part.LineSegment(V(0, 0, ROD_HEIGHT), profile.StartPoint).toShape(), profile.toShape(),
                         Part.LineSegment(top, V(0, 0, top.z)).toShape(),
                         Part.LineSegment(V(0, 0, top.z), V(0, 0, ROD_HEIGHT)).toShape()])
    vase = Part.Face(outline).revolve(V(0, 0, 0), UP, face_frame.FULL_CIRCLE)
    curved = rod.fuse(Part.Solid(Part.Shell(vase.Faces)) if not vase.Solids else vase).removeSplitter()
    stood, side = stood_on_free_rim(curved)
    along = geometry.build(stood, stood.Faces[side], p)
    rim_top = geometry.build(stood, stood.Faces[side], alone).height
    expect(along.height > rim_top + ROD_HEIGHT / 2
           and not [w for w in along.warnings if "rim" not in w],
           "along a curved outline the fin goes on up, every tine resting on it: %.1f mm over %.1f"
           % (along.height, rim_top))

    # A chamfer on both rims: the part stands on one, the other on top stands
    # upright once the side leans 45 degrees and needs no tine.
    chamfered = rod.makeChamfer(CHAMFER_SHORT, [e for e in rod.Edges if orient.is_rim(e)])
    stood, side = stood_on_free_rim(chamfered)
    upright = geometry.build(stood, stood.Faces[side], p)
    side_top = geometry.build(stood, stood.Faces[side], alone).frame.face_top_z - upright.frame.bed_z
    expect(max(upright.tine_z) + p.tine_height <= side_top + d.TOLERANCE
           and max(z for z in upright.touching_z[1]) + p.tine_height <= side_top + d.TOLERANCE,
           "no tine on the chamfer on top, which stands upright: tines up to %.1f mm, side up to %.1f"
           % (max(upright.touching_z[1]) + p.tine_height, side_top))

    # A tube: its front wall alone, the fin ends at its front top edge.
    tube = rod.cut(Part.makeCylinder(BORE_RADIUS, ROD_HEIGHT))
    stood, side = stood_on_free_rim(tube)
    front = geometry.build(stood, stood.Faces[side], p)
    edge = geometry.build(stood, stood.Faces[side], alone).frame.face_top_z - front.frame.bed_z
    expect(front.height <= edge + p.tine_height,
           "a tube holds the fin at its front wall, up to its front top edge, not over the bore: %.1f mm, edge %.1f"
           % (front.height, edge))

    # A gap without tines smaller than the gap keeps the gap there.
    stood, side = stood_on_free_rim(step)
    smaller = geometry.build(stood, stood.Faces[side], FinParams(placement=d.PLACEMENT_CENTER, contour_gap=p.gap / 2))
    same = geometry.build(stood, stood.Faces[side], FinParams(placement=d.PLACEMENT_CENTER, contour_gap=p.gap))
    expect(smaller.frame.contour.flank_at == same.frame.contour.flank_at,
           "a gap without tines smaller than the gap is taken, the gap kept over faces looking up")
    try:
        FinParams(contour_bridge=-1.0).validate()
    except ParamError as error:
        expect("contour_bridge" in str(error), "a negative bridge is refused: %s" % error)
    else:
        raise AssertionError("a negative contour bridge was accepted")


def check_part_of_side():
    """The half round end of a slot takes one fin under its lowest line, and a
    counter fin goes under it or under the end face leaning the other way."""
    p = FinParams(placement=d.PLACEMENT_CENTER)
    slot = slot_on_end()
    halves = [i for i, f in enumerate(slot.Faces) if orient.is_curved_side(f)]
    expect(len(halves) == 2 and not any(orient.is_round_side(slot.Faces[i]) for i in halves),
           "a slot has two half round ends, neither a whole round side")
    taking, refused = [], []
    for number in halves:
        try:
            face_frame.frame_of(slot, slot.Faces[number])
        except face_frame.FinError as error:
            refused.append(str(error))
        else:
            taking.append(number)
    expect(len(taking) == 1 and len(refused) == 1 and "lowest line" in refused[0],
           "the lower half round end takes fins, the upper one does not reach round to its lowest line: %s"
           % refused)
    half = taking[0]
    frame = face_frame.frame_of(slot, slot.Faces[half])
    result = geometry.build(slot, slot.Faces[half], FinParams(placement=d.PLACEMENT_ENDS))
    expect(frame.round_side and not frame.whole_side and len(result.positions) == 1 and len(result.tines) > 1
           and max(abs(t.distToShape(slot)[0] - p.clearance) for t in result.tines) < d.TOLERANCE
           and result.fins.common(slot).Volume < d.TOLERANCE,
           "the half round end takes one fin, whatever the placement, every tine ends on it, none in it")
    expect(not any("rim" in w for w in result.warnings), "a slot does not stand on a rim: no note on one")
    shifted = geometry.build(slot, slot.Faces[half], p, shifts={1: ROUND_TURN})
    expect(shifted.fins.BoundBox.isInside(result.fins.BoundBox.Center)
           and abs(shifted.starts[1] - result.starts[1]) < d.TOLERANCE,
           "the fin under a half round end stays under its lowest line, a shift by hand moves it nowhere")

    end = geometry.opposite_faces(slot, slot.Faces[half])
    expect(end and end[0].findPlane() is not None, "the end face leans the other way from the half round end")
    end_number = [i for i, f in enumerate(slot.Faces) if f.isSame(end[0])][0]
    geometry.build(slot, end[0], p)
    counter = geometry.opposite_faces(slot, slot.Faces[end_number])
    expect(any(f.isSame(slot.Faces[half]) for f in counter),
           "under the end face, the half round end is offered for the counter fin")
    # The end face narrows to its round ends at the bottom and the top: moved
    # past the stretch its narrowest tine allows, the fin keeps tines where
    # the face is wide enough under it: on one grid some are left out and named,
    # with the restart they are spread over that height alone.
    for restart in (True, False):
        q = FinParams(placement=d.PLACEMENT_CENTER, tine_restart=restart)
        planned = geometry.build(slot, end[0], q)
        aside = geometry.build(slot, end[0], q, shifts={1: SLOT_ASIDE})
        expect(SLOT_ASIDE > planned.frame.along_max
               and 0 < len(aside.tines) and (restart or len(aside.tines) < len(planned.tines))
               and any("narrower" in w for w in aside.warnings) != restart,
               "restart %s: a fin moved %.0f mm along the end face of a slot keeps its tines where the face is "
               "wide enough: %s" % (restart, SLOT_ASIDE, aside.warnings))
        try:
            geometry.build(slot, end[0], q, shifts={1: SLOT_PAST_SIDE})
        except face_frame.FinError as error:
            expect("narrower" in str(error),
                   "restart %s: a fin moved past the side of the end face is too narrow there: %s" % (restart, error))
        else:
            raise AssertionError("restart %s: a fin moved past the side of the end face of a slot was built" % restart)


def check_left_out(cube, face):
    """Fins removed by hand are not built; the others stay where they were."""
    three = FinParams(placement=d.PLACEMENT_DISTRIBUTED, fin_count=3)
    whole = geometry.build(cube, face, three)
    middle_gone = geometry.build(cube, face, three, left_out=(2,))
    expect(whole.numbers == [1, 2, 3] and middle_gone.numbers == [1, 3]
           and middle_gone.positions == [whole.positions[0], whole.positions[2]],
           "the middle fin removed by hand leaves the outer two where they were")
    try:
        geometry.build(cube, face, three, left_out=(1, 2, 3))
    except face_frame.FinError as error:
        expect("every fin is removed" in str(error), "removing every fin is refused: %s" % error)
    else:
        raise AssertionError("fins were built with every fin removed")


def check_fin_at(cube, face):
    """A fin drawn at another height, as the task panel shows one that cannot
    stand there, has the faces of the fin built, its flank along the face."""
    p = FinParams()
    built = geometry.build(cube, face, p)
    number = built.numbers[0]

    def planes(shapes):
        """The directions the flat faces of `shapes` face, rounded to compare."""
        return {tuple(round(c, NORMAL_DECIMALS) for c in f.normalAt(*f.ParameterRange[::2]))
                for shape in shapes for f in shape.Faces if f.findPlane() is not None}

    same = geometry.fin_at(p, built, number, built.heights[number])
    expect(abs(same[0].Volume - built.bodies[0].Volume) < d.TOLERANCE and len(same) == 1 + len(built.tines),
           "drawn at its own height, the fin is the one built, with its tines")
    for height, why in ((built.heights[number] + ABOVE_FACE, "far above the face"),
                        (built.tine_z[0], "at the bottom of its first tine")):
        drawn = geometry.fin_at(p, built, number, height)
        expect(planes(drawn[:1]) <= planes(built.bodies[:1])
               and abs(drawn[0].BoundBox.ZMax - (cube.BoundBox.ZMin + height)) < d.TOLERANCE,
               "drawn %s, the fin is as high, its faces turned as those of the fin built" % why)
    expect(len(geometry.fin_at(p, built, number, built.tine_z[0])) == 1,
           "drawn no higher than the bottom of its first tine, the fin has no tines")
    for height in (p.foot_height / 2, 0.0):
        low = geometry.fin_at(p, built, number, height)[0]
        expect(p.foot_height > 0 and low.isValid() and len(low.Solids) == 1
               and abs(low.BoundBox.ZMax - (cube.BoundBox.ZMin + p.foot_height)) < d.TOLERANCE,
               "drawn %.2f mm high, below the top of its foot, the fin is a whole solid as high as its foot"
               % height)


def check_merged_clearance(cube, face):
    """Fins merged into the part reach it through their tines: a tine
    clearance would leave them loose, so it is not applied."""
    merged = FinParams(connection=d.CONNECTION_MERGED, tine_clearance=MERGED_CLEARANCE)
    result = geometry.build(cube, face, merged)
    expect(merged.clearance == 0 and merged.tine_length == merged.gap
           and min(t.distToShape(cube)[0] for t in result.tines) < d.TOLERANCE,
           "merged fins keep their tines on the face, whatever the tine clearance")


def check_moved_fins(cube, face):
    """Fins moved along the face and set to their own height by hand."""
    three = FinParams(placement=d.PLACEMENT_DISTRIBUTED, fin_count=3)
    whole = geometry.build(cube, face, three)
    moved_one = geometry.build(cube, face, three, shifts={1: SHIFT})
    edge = whole.edges[1]
    expect(abs(edge.z - whole.heights[1] / 2) < d.TOLERANCE
           and whole.bodies[0].distToShape(Part.Vertex(edge))[0] < d.TOLERANCE,
           "the handles go on the middle of the upright outer edge of the fin: %s" % edge)
    expect(abs(moved_one.starts[1] - (whole.starts[1] + SHIFT)) < d.TOLERANCE
           and moved_one.starts[2] == whole.starts[2],
           "a fin moved by hand moves alone, the others stay")
    try:
        gap = whole.starts[2] - whole.starts[1]
        geometry.build(cube, face, three, shifts={1: gap})
    except face_frame.FinError as error:
        expect("closer than" in str(error), "a fin moved onto its neighbour is refused: %s" % error)
    else:
        raise AssertionError("a fin was moved onto its neighbour")
    try:
        geometry.build(cube, face, three, shifts={1: 2 * gap})
    except face_frame.FinError as error:
        expect("would pass" in str(error) and isinstance(error, face_frame.HandEditError),
               "a fin moved past its neighbour is refused as a change by hand: %s" % error)
    else:
        raise AssertionError("a fin was moved past its neighbour")
    low = whole.tine_z[0] + FinParams().tine_height
    lowered = geometry.build(cube, face, three, heights={2: low})
    middle = lowered.bodies[1].BoundBox
    expect(abs(middle.ZMax - low) < d.TOLERANCE and abs(lowered.bodies[0].BoundBox.ZMax - whole.height) < d.TOLERANCE,
           "a fin set lower by hand stands at its own height, the others keep theirs")
    try:
        geometry.build(cube, face, three, heights={2: whole.tine_z[0] / 2})
    except face_frame.FinError as error:
        expect("lower than its first tine" in str(error), "a fin below its first tine is refused: %s" % error)
    else:
        raise AssertionError("a fin lower than its first tine was built")


def check_recesses(cube, face):
    """With one tine grid for every fin: tines over a recess or a hole in the
    face are left out with a warning; a fin none of whose tines finds the face
    moves beside it, or is left out where nowhere takes it."""
    frame = face_frame.frame_of(cube, face)
    normal = face.normalAt(0, 0)
    middle = (frame.along_min + frame.along_max) / 2
    middle_z = geometry.build(cube, face, FinParams(tine_restart=False)).tine_z[1]
    middle_tine = middle_z + FinParams(tine_restart=False).tine_height / 2

    on_face = frame.point(middle, frame.s_face(middle_tine), middle_tine)
    pit = Part.makeCylinder(RECESS_RADIUS, 2 * RECESS_RADIUS, on_face - normal * RECESS_RADIUS, normal)
    pitted = cube.cut(pit)
    result = geometry.build(pitted, lower_left_face(pitted), FinParams(tine_restart=False))
    named = "tines at %.1f mm" % middle_z
    expect(len(result.tines) == 2 and any(named in w for w in result.warnings),
           "the tine over a hole in the face is left out, the warning names its height: %s" % result.warnings)
    left_out = result.dropped[0].BoundBox.Center.z if len(result.dropped) == 1 else None
    expect(left_out is not None and abs(left_out - middle_tine) < FinParams(tine_restart=False).tine_height,
           "the tine left out is handed back as a shape, for the red mark")
    # The tine over the hole is no step for the height of the fin; the one
    # beyond it is, also while the fin stands lower than the hole.
    zs = result.tine_z
    number = result.numbers[0]
    expect(result.touching_z[number] == [zs[0], zs[2]],
           "the heights a fin can end with a tine leave out the tine over the hole: %s" % result.touching_z)
    lower = geometry.build(pitted, lower_left_face(pitted), FinParams(tine_restart=False),
                           heights={number: zs[0] + FinParams(tine_restart=False).tine_height})
    expect(lower.touching_z[number] == [zs[0], zs[2]],
           "a fin lower than the hole still names the tine beyond it as a step: %s" % lower.touching_z)

    # A hole under only half of the tine: it would hang free there, so it is left out too.
    beside = frame.point(middle + RECESS_RADIUS, frame.s_face(middle_tine), middle_tine)
    half = cube.cut(Part.makeCylinder(RECESS_RADIUS, 2 * RECESS_RADIUS, beside - normal * RECESS_RADIUS, normal))
    partly = geometry.build(half, lower_left_face(half), FinParams(tine_restart=False))
    expect(len(partly.tines) == 2, "a tine only partly over a hole is left out as well")

    # A groove running up the face under the middle one of three fins: that fin has no tine left.
    three = FinParams(tine_restart=False, placement=d.PLACEMENT_DISTRIBUTED, fin_count=3)
    spread = geometry.build(cube, face, three)
    centre = tine_rows.tine_start(three, spread.positions[1], spread.thickness) + three.tine_width / 2

    over_middle = grooved(cube, face, centre)
    moved = geometry.build(over_middle, lower_left_face(over_middle), three)
    expect(moved.numbers == [1, 2, 3] and moved.positions[1] != spread.positions[1]
           and moved.positions == sorted(moved.positions)
           and any("fin 2 by" in w for w in moved.warnings),
           "a fin over a groove moves beside it, between its neighbours, the warning says by how much: %s"
           % moved.warnings)
    centred = grooved(cube, face, middle)
    alone = geometry.build(centred, lower_left_face(centred),
                           FinParams(tine_restart=False, placement=d.PLACEMENT_CENTER))
    expect(len(alone.positions) == 1 and any("fin 1 by" in w for w in alone.warnings),
           "one fin in the middle over a groove moves beside it: %s" % alone.warnings)


def check_overhangs(cube, face):
    """Overhang detection on simple and less simple bodies."""
    expect(overhanging(Part.makeBox(30, 10, 10)) == [], "a box lying on the bed has no overhang")
    found = overhanging(cube, [face])
    expect(found == [], "the reference cube with a fin has no overhang: %s" % found)

    upright = Part.makeCylinder(5, 20)
    expect(overhanging(upright) == [], "an upright cylinder has no overhang")
    lying = Part.makeCylinder(5, 20, V(0, 0, 5), V(1, 0, 0))
    curved = [i for i, f in enumerate(lying.Faces, 1) if f.findPlane() is None]
    expect(overhanging(lying) == curved, "a cylinder on its side overhangs with its curved face")

    expect(overhanging(pyramid(PYRAMID_STEEP)) == [], "a pyramid on its base has no overhang")
    flat = pyramid(PYRAMID_FLAT, apex_down=True)
    sides = overhanging(flat)
    expect(len(sides) == 4, "a flat pyramid on its apex overhangs with all four sides: %s" % sides)
    edge = pyramid(PYRAMID_BASE / 2, apex_down=True)
    expect(overhanging(edge) == [], "sides at exactly %.0f degrees do not count" % d.OVERHANG_ANGLE)
    supported = [flat.Faces[i - 1] for i in sides[:2]]
    expect(len(overhanging(flat, supported)) == 2, "faces carried by fins do not count")

    try:
        geometry.build(lying, lying.Faces[curved[0] - 1], FinParams())
    except face_frame.FinError as error:
        expect(face_frame.HORIZONTAL_ROUND_SIDE in str(error),
               "fins under a cylinder resting on its side are refused: %s" % error)
    else:
        raise AssertionError("fins were built under a cylinder resting on its side")
    ball = Part.makeSphere(ROD_RADIUS)
    try:
        geometry.build(ball, ball.Faces[0], FinParams())
    except face_frame.FinError as error:
        expect("not planar" in str(error), "fins under a curved face other than a cylinder are refused: %s" % error)
    else:
        raise AssertionError("fins were built under a sphere")
    try:
        orient.tilt(upright, upright.Edges[0], d.TILT_ANGLE)
    except orient.OrientError as error:
        expect("straight" in str(error), "a cylinder cannot stand on its round edge: %s" % error)
    else:
        raise AssertionError("a cylinder was stood on its round edge")

    # Tilted less than the limit, the base still lies too flat; a fin under it settles that.
    standing = pyramid(PYRAMID_STEEP)
    base_edge = [e for e in standing.Edges if e.BoundBox.ZMax < d.TOLERANCE][0]
    standing.Placement = orient.tilt(standing, base_edge, PYRAMID_TILT).multiply(standing.Placement)
    expect(abs(standing.BoundBox.ZMin) < d.TOLERANCE, "a pyramid stands on a base edge")
    base = [i for i, f in enumerate(standing.Faces, 1) if len(f.Edges) == 4]
    expect(overhanging(standing) == base, "tilted by %.0f degrees its base overhangs" % PYRAMID_TILT)
    expect(overhanging(standing, [standing.Faces[base[0] - 1]]) == [],
           "with a fin under the base the tilted pyramid has no overhang")


def bossed_cube(*bosses):
    """The tilted cube with upright bosses BOSS_HEIGHT high standing out of the
    face the fins go under, in its middle, as (radius, mm along the cube)."""
    plain = Part.makeBox(EDGE, EDGE, EDGE, V(-EDGE / 2, 0, -EDGE / 2))
    shape = plain.makeChamfer(CHAMFER, plain.Edges)
    for radius, along in bosses:
        shape = shape.fuse(Part.makeCylinder(radius, BOSS_HEIGHT, V(0, along, -EDGE / 2), V(0, 0, -1)))
    return tilted(shape.removeSplitter())


def check_boss_on_face():
    """A boss standing out of the face where a fin is planned sends it aside
    to the nearest place clear of it, or leaves it out where none is; a fin
    moved onto it by hand is refused; a plain face has nothing in front."""
    cube = tilted_cube()
    expect(geometry.in_front_of(cube, face_frame.frame_of(cube, lower_left_face(cube))) is None,
           "nothing of the plain cube stands out in front of its face")
    one = FinParams(placement=d.PLACEMENT_CENTER)
    for restart in (False, True):
        for radius in BOSS_RADII:
            bossed = bossed_cube((radius, EDGE / 2))
            params = FinParams(placement=d.PLACEMENT_CENTER, tine_restart=restart)
            built = geometry.build(bossed, lower_left_face(bossed), params)
            closest = min(body.distToShape(bossed)[0] for body in built.bodies)
            expect(built.moved and any("clear of the part" in w for w in built.warnings)
                   and closest >= params.gap - d.TOLERANCE,
                   "restart %s, a boss of %g mm: the fin moves aside by %.1f mm, %.2f mm off the part"
                   % (restart, radius, list(built.moved.values())[0], closest))
    bossed = bossed_cube((BOSS_RADII[0], BOSS_BESIDE))
    try:
        geometry.build(bossed, lower_left_face(bossed), one, shifts={1: BOSS_SHIFT})
    except face_frame.HandEditError as error:
        expect("run into the part" in str(error), "a fin moved by hand onto a boss is refused: %s" % error)
    else:
        raise AssertionError("a fin moved by hand onto a boss was built")
    bossed = bossed_cube((BOSS_WIDE, EDGE / 2))
    try:
        geometry.build(bossed, lower_left_face(bossed), one)
    except face_frame.FinError as error:
        expect("under every fin" in str(error), "a boss over the whole face leaves no place: %s" % error)
    else:
        raise AssertionError("fins were built over a boss covering the face")
    bossed = bossed_cube((BOSS_MIDDLE, EDGE / 2))
    spread = FinParams(placement=d.PLACEMENT_DISTRIBUTED, fin_count=3)
    three = geometry.build(bossed, lower_left_face(bossed), spread)
    expect(len(three.positions) == 2 and any("no place beside it is clear" in w for w in three.warnings),
           "a boss as wide as the middle of the face leaves the middle one of three fins out: %s" % three.warnings)
    # Their feet, planned again without the fin left out, keep clear of the boss.
    closest = min(body.distToShape(bossed)[0] for body in three.bodies)
    expect(closest >= spread.gap - d.TOLERANCE,
           "the two fins left beside the boss keep the gap, feet and all: %.2f mm" % closest)


def check_straight_faces():
    """The cuts through one planar face of straight edges are worked out from its
    corners and are what the kernel cuts; every other face, and a cut through a
    corner or along an edge, is left to the kernel."""
    lean = App.Rotation(V(1, 0, 0), STRAIGHT_LEAN)

    def face_of(*rings):
        """A leaning face with the first of `rings`, lists of (x, y), as its outline and the others as holes."""
        faces = [Part.Face(Part.makePolygon([lean.multVec(V(x, y, 0)) for x, y in ring + ring[:1]])) for ring in rings]
        return faces[0].cut(faces[1:]).Faces[0] if len(faces) > 1 else faces[0]

    frame = types.SimpleNamespace(along=V(1, 0, 0), bed_z=0.0)
    cuts = {"span": 0, "bands": 0}
    real_span, real_bands = tine_rows._span_cut, tine_rows._bands_cut

    def span_cut(*args):
        cuts["span"] += 1
        return real_span(*args)

    def bands_cut(*args):
        cuts["bands"] += 1
        return real_bands(*args)

    def same(one, other):
        """Whether two answers, None, a pair or a list of pairs, agree within STRAIGHT_SAME."""
        if one is None or other is None:
            return one is None and other is None
        flat = [list(numpy.ravel(found)) for found in (one, other)]
        return len(flat[0]) == len(flat[1]) and all(abs(a - b) <= STRAIGHT_SAME for a, b in zip(*flat))

    wide, high, step = STRAIGHT_WIDE, STRAIGHT_HIGH, STRAIGHT_STEP
    (near, far), (lower, upper) = STRAIGHT_HOLE_ACROSS, STRAIGHT_HOLE_UP
    rectangle = [(0, 0), (wide, 0), (wide, high), (0, high)]

    def hole(low, up):
        """The square hole, from `low` to `up` up the face."""
        return [(near, low), (far, low), (far, up), (near, up)]

    faces = [("a rectangle", face_of(rectangle), 1),
             ("a slanted quad", face_of([(0, 0), (wide, 0), *STRAIGHT_SLANTED_TOP]), 1),
             ("a triangle", face_of([(0, 0), (wide, 0), (STRAIGHT_TIP, high)]), 1),
             ("an L", face_of([(0, 0), (wide, 0), (wide, lower), (step, lower), (step, high), (0, high)]), 1),
             ("a U lying on its side", face_of([(0, 0), (wide, 0), (wide, lower), (step, lower), (step, upper),
                                                (wide, upper), (wide, high), (0, high)]), 2),
             ("a rectangle with a square hole", face_of(rectangle, hole(lower, upper)), 2)]
    tine_rows._span_cut, tine_rows._bands_cut = span_cut, bands_cut
    try:
        for name, face, most in faces:
            top = face.BoundBox.ZMax
            heights = [top * share for share in STRAIGHT_SHARES] + [-STRAIGHT_PAST, top + STRAIGHT_PAST]
            places = STRAIGHT_PLACES
            cuts["span"] = cuts["bands"] = 0
            spans = [tine_rows._span_at(face, frame, height) for height in heights]
            bands = [tine_rows._bands_at(frame, face, t) for t in places]
            worked_out = dict(cuts)
            expect(not worked_out["span"] and not worked_out["bands"]
                   and all(same(found, real_span(face, frame, height)) for found, height in zip(spans, heights))
                   and all(same(found, real_bands(frame, face, t)) for found, t in zip(bands, places))
                   and max(len(found) for found in bands) == most and spans[-1] is None and bands[-1] == [],
                   "%s: %d widths and %d cuts along a fin worked out as the kernel cuts them, no cut made, up to %d "
                   "stretches, none past the face" % (name, len(spans), len(bands), max(len(found) for found in bands)))
        # What is left to the kernel: counted, and answered as it answers.
        plain = faces[0][1]
        notched = faces[4][1]
        round_hole = plain.cut(Part.Face(Part.Wire(Part.makeCircle(
            STRAIGHT_ROUND_HOLE, lean.multVec(V(wide / 2, high / 2, 0)), lean.multVec(V(0, 0, 1)))))).Faces[0]
        curved = Part.makeCylinder(*STRAIGHT_CURVED).Faces[0]
        two = Part.makeCompound([plain, plain.translated(V(wide, 0, 0))])
        top = plain.BoundBox.ZMax
        left = [("a corner at the height", lambda: tine_rows._span_at(plain, frame, top), "span"),
                ("an edge at the height", lambda: tine_rows._span_at(plain, frame, 0.0), "span"),
                ("a corner nearer the height than CORNER_NEAR_CUT",
                 lambda: tine_rows._span_at(plain, frame, top - tine_rows.CORNER_NEAR_CUT / 2), "span"),
                ("an edge along the cut", lambda: tine_rows._bands_at(frame, notched, step), "bands"),
                ("a corner in the cut", lambda: tine_rows._bands_at(frame, plain, wide), "bands"),
                ("a round hole, the width", lambda: tine_rows._span_at(round_hole, frame, top / 2), "span"),
                ("a round hole, along a fin", lambda: tine_rows._bands_at(frame, round_hole, wide / 2), "bands"),
                ("a face that is not planar",
                 lambda: tine_rows._span_at(curved, frame, STRAIGHT_CURVED[1] / 2), "span"),
                ("two faces, the width", lambda: tine_rows._span_at(two, frame, top / 2), "span"),
                ("two faces, along a fin", lambda: tine_rows._bands_at(frame, two, wide / 2), "bands")]
        for name, ask, kind in left:
            cuts["span"] = cuts["bands"] = 0
            found = ask()
            expect(cuts[kind] == 1, "%s: cut by the kernel (%s)" % (name, found))
        expect(tine_rows._straight_outline(curved) is None and tine_rows._straight_outline(two) is None
               and tine_rows._straight_outline(round_hole) is None
               and [len(ring) for ring in tine_rows._straight_outline(faces[5][1])] == [4, 4],
               "only one planar face of straight edges has corners to cut by, a hole as a ring of its own")
        # A straight edge held as a spline is not a line: left to the kernel.
        corners = [lean.multVec(V(x, y, 0)) for x, y in rectangle]
        a, b = corners[3], corners[0]
        spline = Part.BSplineCurve()
        spline.interpolate([a, (a + b) / 2, b])
        sides = [Part.makeLine(one, other) for one, other in zip(corners, corners[1:])] + [spline.toShape()]
        splined = Part.Face(Part.Wire(sides))
        cuts["span"] = 0
        found = tine_rows._span_at(splined, frame, top / 2)
        expect(tine_rows._straight_outline(splined) is None and cuts["span"] == 1
               and same(found, tine_rows._span_at(plain, frame, top / 2)),
               "a straight edge held as a spline is left to the kernel, with the same width: %s" % (found,))
    finally:
        tine_rows._span_cut, tine_rows._bands_cut = real_span, real_bands
    # A stretch ending on a layer boundary: the same tines as by the cut.
    rise = math.sin(math.radians(STRAIGHT_LEAN))
    holed = face_of(rectangle, hole(*(layers * STRAIGHT_LAYER / rise for layers in STRAIGHT_HOLE_LAYERS)))
    params = FinParams(layer_height=STRAIGHT_LAYER, tine_restart=True)
    asked = (params, frame, holed, STRAIGHT_FIN_AT, d.FIN_THICKNESS_BASE, holed.BoundBox.ZMax, None)
    worked_out = tine_rows.restarted_tines(*asked)
    real = tine_rows._bands_at
    tine_rows._bands_at = tine_rows._bands_cut
    try:
        cut = tine_rows.restarted_tines(*asked)
    finally:
        tine_rows._bands_at = real
    ends = tine_rows._bands_at(frame, holed, STRAIGHT_BANDS_AT)
    expect(worked_out == cut and worked_out and len(ends) == 2
           and abs(ends[0][1] / STRAIGHT_LAYER - round(ends[0][1] / STRAIGHT_LAYER)) < d.TOLERANCE,
           "a stretch ending on a layer boundary, at %.4f mm: the same %d tines worked out as by the cut"
           % (ends[0][1], len(worked_out or [])))


def check_enclosed():
    """Which points lie inside a solid is told on its mesh as the kernel tells
    it, and not told where the mesh cannot know; the kernel is asked of those
    alone, and a search finds what it found without the mesh."""
    edge, margin = ENCLOSED_EDGE, d.ENCLOSED_MARGIN
    radius, height, bore = ENCLOSED_TUBE
    inner = edge - 2 * ENCLOSED_WALL
    cube = Part.makeBox(edge, edge, edge)
    hollow = cube.cut(Part.makeBox(inner, inner, inner, V(ENCLOSED_WALL, ENCLOSED_WALL, ENCLOSED_WALL)))
    tube = Part.makeCylinder(radius, height).cut(Part.makeCylinder(bore, height))

    def kernel(solid, point):
        return solid.isInside(point, d.TOLERANCE, False)

    askew = tube.rotated(V(0, 0, 0), V(*ENCLOSED_ASKEW[0]), ENCLOSED_ASKEW[1])
    for name, solid in (("a cube", cube), ("a hollow cube", hollow), ("a tube", tube), ("a tube askew", askew)):
        mesh = shapes.enclosed_of(solid)
        box = solid.BoundBox
        axes = [numpy.linspace(low - ENCLOSED_PAST, high + ENCLOSED_PAST, ENCLOSED_GRID)
                for low, high in ((box.XMin, box.XMax), (box.YMin, box.YMax), (box.ZMin, box.ZMax))]
        grid = [V(x, y, z) for x in axes[0] for y in axes[1] for z in axes[2]]
        told = mesh.told(grid)
        wrong = sum(found is not None and found != kernel(solid, point) for found, point in zip(told, grid))
        known = sum(found is not None for found in told)
        expect(mesh.closed and not wrong and 2 * known > len(grid) and True in told and False in told,
               "%s: %d of %d points told on the mesh, %d of them other than the kernel tells" %
               (name, known, len(grid), wrong))

    mesh = shapes.Enclosed(askew)
    aimed = math.ceil(math.sqrt(len(mesh.a) / shapes.ENCLOSED_PER_CELL))
    cells = [mesh._grid(axes) for axes in shapes.ENCLOSED_RAYS]
    named_most = shapes.ENCLOSED_CELL_NAMINGS * len(mesh.a)
    expect(all(grid.count < aimed and (len(grid.triangles) <= named_most or grid.count == 1) for grid in cells),
           "the long triangles of a tube askew are sorted into a coarser grid than aimed at, %s cells a side "
           "instead of %d" % ([grid.count for grid in cells], aimed))
    mesh = shapes.enclosed_of(cube)
    deep = V(*(edge * share for share in ENCLOSED_DEEP))
    centre = V(edge / 2, edge / 2, edge / 2)
    expect(mesh.told([deep, V(deep.x, deep.y, -ENCLOSED_PAST), centre]) == [True, False, None] and mesh.told([]) == [],
           "a point deep in a cube is inside, one below it outside, its centre, every ray from which runs "
           "through a diagonal of a face, not told; no points, no answers")
    by_wall = [V(deep.x, deep.y, edge + side * off * margin) for off in ENCLOSED_OFF_UNTOLD for side in (-1, 1)]
    clear = [V(deep.x, deep.y, edge + side * ENCLOSED_OFF_TOLD * margin) for side in (-1, 1)]
    expect(mesh.told(by_wall) == [None] * len(by_wall) and mesh.told(clear) == [True, False],
           "points within the margin of a face of the cube, on either side, are not told of; %g margins off they are"
           % ENCLOSED_OFF_TOLD)
    expect(shapes.enclosed_of(hollow).told([V(*(edge * share for share in ENCLOSED_IN_HOLLOW))]) == [False],
           "a point in the hollow of a cube is outside it")
    # A round hollow: the triangles cut into the bore, a point just in it is not said to be inside.
    turn, up = math.radians(ENCLOSED_TUBE_AT[0]), height * ENCLOSED_TUBE_AT[1]

    def in_tube(off):
        return V((bore + off) * math.cos(turn), (bore + off) * math.sin(turn), up)

    mesh = shapes.enclosed_of(tube)
    in_bore = [in_tube(-off * margin) for off in ENCLOSED_OFF_UNTOLD]
    expect(mesh.told(in_bore) == [None] * len(in_bore)
           and mesh.told([in_tube(-ENCLOSED_OFF_TOLD * margin), in_tube(ENCLOSED_OFF_TOLD * margin)]) == [False, True],
           "points in the bore of a tube within the margin of its wall are not told of; %g margins off it they are "
           "outside, as far in the wall inside" % ENCLOSED_OFF_TOLD)
    # No closed mesh, or none at all: nothing told.
    shell = Part.Shell(cube.Faces[:-1])
    most, triangles = d.ENCLOSED_MOST, len(shapes.Enclosed(cube).a)
    try:
        d.ENCLOSED_MOST = triangles
        just_fits = shapes.enclosed_of(cube)
        d.ENCLOSED_MOST = triangles - 1
        too_large = shapes.enclosed_of(cube)
    finally:
        d.ENCLOSED_MOST = most
    try:
        shapes.mesh_arrays(cube, d.ENCLOSED_DEFLECTION, most=triangles - 1)
        counted = False
    except shapes.TooManyPairs:
        counted = True
    expect(not shapes.Enclosed(shell).closed and shapes.Enclosed(shell).told([deep]) == [None]
           and shapes.Enclosed(cube.Faces[0]).told([deep]) == [None],
           "a cube with a face missing and a single face tell of no point")
    expect(just_fits is not None and too_large is None and counted
           and len(shapes.mesh_arrays(cube, d.ENCLOSED_DEFLECTION, most=triangles)[1]) == triangles,
           "a solid of as many triangles as the most has a mesh, with one more it has none, told as it is meshed")

    # A solid settled with its mesh, or without one: the kernel is asked of what the mesh does not tell of alone.
    real_inside, real_enclosed, real_clock = geometry._inside, geometry.enclosed_of, geometry._clock
    worth, slow = d.ENCLOSED_WORTH, d.ENCLOSED_KERNEL_SLOW
    calls, meshes = [], []
    geometry._inside = lambda solid, point: calls.append(1) or real_inside(solid, point)

    def standing(solid, with_mesh=None):
        """`solid` as _any_inside() knows it, afresh: asking still, or settled with its mesh or without one."""
        geometry._kept_solids_in.clear()
        found = geometry._solids_in(solid)[0]
        if with_mesh is not None:
            found.settled, found.mesh = True, real_enclosed(solid) if with_mesh else None
        return found

    def any_inside(solid, points, with_mesh=True):
        """What _any_inside() says and how often it asked the kernel for it."""
        del calls[:]
        standing(solid, with_mesh)
        return geometry._any_inside(solid, points), len(calls)

    class Clock:
        """A clock that goes on by `took` seconds over each call of the kernel timed by it."""

        def __init__(self):
            self.now, self.took, self.read = 0.0, 0.0, 0

        def __call__(self):
            self.read += 1
            if self.read % 2 == 0:
                self.now += self.took
            return self.now

    clock = Clock()

    def settled(solid, took):
        """`solid` asked of a point the kernel takes `took` for until it is settled, and of how many."""
        found = standing(solid)
        clock.took = took
        del calls[:], meshes[:]
        while not found.settled and len(calls) < ENCLOSED_ASKED_MOST:
            geometry._any_inside(solid, [in_bore[1]])
        return found, len(calls)

    try:
        outside = V(deep.x, deep.y, -ENCLOSED_PAST)
        expect([any_inside(cube, points) for points in ([], [outside], [deep], [outside, deep])]
               == [(False, 0), (False, 0), (True, 0), (True, 0)]
               and any_inside(tube, [in_tube(-ENCLOSED_OFF_TOLD * margin)]) == (False, 0),
               "no points, points outside the box, points the mesh tells of: the kernel is not asked")
        in_wall = in_tube(ENCLOSED_OFF_TOLD * margin)
        expect(any_inside(cube, [by_wall[2], outside]) == (True, 1) and any_inside(tube, [in_bore[1]]) == (False, 1)
               and any_inside(cube, [deep, by_wall[2]]) == (True, 0)
               and any_inside(cube, [by_wall[2], deep], with_mesh=False) == (True, 1)
               and any_inside(tube, [in_bore[1], in_wall], with_mesh=False) == (True, 2),
               "a point the mesh does not tell of is asked of the kernel, unless another is told to be inside; "
               "without a mesh each is asked until one is inside")

        # How a solid is settled, on a clock of the test: once, by what the kernel took until then.
        geometry._clock = clock
        geometry.enclosed_of = lambda solid: meshes.append(1) or real_enclosed(solid)
        took = slow * ENCLOSED_QUICK_SHARE
        found, asked = settled(tube, took)
        clock.took, read = worth, clock.read
        later = geometry._any_inside(tube, [in_bore[1], in_wall])
        expect(asked == math.ceil(worth / took) and found.mesh is None and not meshes and later
               and clock.read == read,
               "a quick kernel: settled after %d points, as many as take what a mesh is worth, without a mesh; "
               "none is made when it turns slow after, and it is timed no more" % asked)
        took = slow * ENCLOSED_SLOW_SHARE
        found, asked = settled(tube, took)
        del calls[:]
        read = clock.read
        on_mesh = geometry._any_inside(tube, [in_tube(-ENCLOSED_OFF_TOLD * margin)]), len(calls)
        untold = geometry._any_inside(tube, [in_bore[1]]), len(calls)
        expect(asked == math.ceil(worth / took) and found.mesh is not None and len(meshes) == 1
               and on_mesh == (False, 0) and untold == (False, 1) and clock.read == read,
               "a slow kernel: settled after %d points with a mesh, made once; a point it tells of is not asked of "
               "the kernel, one it does not is, timed no more" % asked)
        found, asked = settled(tube, worth)
        expect(asked == 1 and found.mesh is not None and len(meshes) == 1,
               "a kernel taking what a mesh is worth for one point: a mesh after that point")
        geometry.enclosed_of = lambda solid: meshes.append(1)
        found, asked = settled(tube, took)
        again = [geometry._any_inside(tube, [in_bore[1], in_wall]) for _ in range(3)]
        expect(found.settled and found.mesh is None and len(meshes) == 1 and all(again),
               "a slow kernel on a solid too large for a mesh: one is tried once, and the kernel asked from then on")

        # A search under a face with a boss: the same answers with the mesh as without, fewer asked.
        def searched(shape, params, with_mesh):
            answers = []
            real_sure = geometry._Places.surely_in_part

            def sure(self, t, own, half_foot=None):
                answers.append(real_sure(self, t, own, half_foot))
                return answers[-1]

            del calls[:]
            geometry._kept_solids_in.clear()
            geometry.enclosed_of = real_enclosed if with_mesh else lambda solid: None
            geometry._Places.surely_in_part = sure
            try:
                geometry.build(shape, lower_left_face(shape), params)
                outcome = "built"
            except face_frame.FinError:
                outcome = "refused"
            finally:
                geometry._Places.surely_in_part = real_sure
            return outcome, answers, len(calls)

        # A mesh is worth it from the first point on, however quick the kernel.
        geometry._clock, d.ENCLOSED_WORTH, d.ENCLOSED_KERNEL_SLOW = real_clock, 0.0, 0.0
        bossed = bossed_cube((BOSS_MIDDLE, EDGE / 2))
        for name, params in (("the default gap", FinParams(placement=d.PLACEMENT_CENTER)),
                             ("a gap within the margin of the mesh",
                              FinParams(placement=d.PLACEMENT_CENTER, gap=ENCLOSED_NARROW_GAP,
                                        tine_clearance=ENCLOSED_NARROW_CLEARANCE))):
            on_mesh, by_kernel = searched(bossed, params, True), searched(bossed, params, False)
            expect(on_mesh[:2] == by_kernel[:2] and any(on_mesh[1]) and on_mesh[2] < by_kernel[2],
                   "%s, %s: %d places asked, told alike with the mesh and without; the kernel asked %d times "
                   "instead of %d" % (name, on_mesh[0], len(on_mesh[1]), on_mesh[2], by_kernel[2]))
    finally:
        geometry._inside, geometry.enclosed_of, geometry._clock = real_inside, real_enclosed, real_clock
        d.ENCLOSED_WORTH, d.ENCLOSED_KERNEL_SLOW = worth, slow
        geometry._kept_solids_in.clear()


def check_surely_in_part():
    """A place where the fin would stand in what stands out of the face is told
    from points of the fin, before it is built: only where the measure of the
    fin built says the same, with points the fin as built holds or comes near."""
    asked, built_at = [], []
    real_sure, real_body = geometry._Places.surely_in_part, geometry._Places._body

    def sure(self, t, own, half_foot=None):
        found = real_sure(self, t, own, half_foot)
        asked.append((self, t, own, found))
        return found

    def body(self, t, height, half_foot):
        built_at.append((self, t, height))
        return real_body(self, t, height, half_foot)

    def searched(shape, params, **more):
        """What a build under the face of `shape` asked, and what it made of it."""
        del asked[:], built_at[:]
        geometry._Places.surely_in_part, geometry._Places._body = sure, body
        try:
            geometry.build(shape, lower_left_face(shape), params, **more)
            outcome = "built"
        except face_frame.FinError:
            outcome = "refused"
        finally:
            geometry._Places.surely_in_part, geometry._Places._body = real_sure, real_body
        return outcome, list(asked), list(built_at)

    wide = bossed_cube((BOSS_WIDE, EDGE / 2))
    middle = bossed_cube((BOSS_MIDDLE, EDGE / 2))
    cases = [("the default foot", middle, FinParams(placement=d.PLACEMENT_CENTER), {}),
             ("a rectangular foot", middle, FinParams(placement=d.PLACEMENT_CENTER, foot_shape=d.FOOT_RECTANGLE), {}),
             ("no foot", middle, FinParams(placement=d.PLACEMENT_CENTER, foot_shape=d.FOOT_NONE), {}),
             ("a height of its own", middle, FinParams(placement=d.PLACEMENT_CENTER), {"heights": {1: EDGE / 3}}),
             ("a boss over the whole face", wide, FinParams(placement=d.PLACEMENT_CENTER), {})]
    for name, shape, params, more in cases:
        outcome, places, bodies = searched(shape, params, **more)
        told = [(self, t, own) for self, t, own, found in places if found]
        wrong, outside, far, points = 0, 0, 0, 0
        for self, t, own, found in places:
            height = self.reach(t, own)
            if height <= d.TOLERANCE:
                continue
            solid = real_body(self, t, height, self.half_foot)
            front = geometry.in_front_of(self.part, self.whole_face)
            wrong += found and solid.distToShape(front)[0] >= params.gap - d.TOLERANCE
            # Three by three: one inside the fin, one beside it on either side.
            for number, point in enumerate(self.sure_points(t, height, self.half_foot)):
                points += 1
                if number % 3 == 0:
                    outside += not solid.isInside(point, d.TOLERANCE, False)
                else:
                    far += solid.distToShape(Part.Vertex(point))[0] >= params.gap - d.TOLERANCE
        built_where_told = [1 for self, t, own in told if (self, t, self.reach(t, own)) in
                            [(places_, at, height) for places_, at, height in bodies]]
        expect(told and not wrong and not outside and not far and points and not built_where_told,
               "%s, %s: %d of %d places told to stand in the part, %d of them clear by the measure; of %d points "
               "%d outside the fin, %d as far off as the gap; fins built where it was told %d"
               % (name, outcome, len(told), len(places), wrong, points, outside, far, len(built_where_told)))
    # Told once, kept: the place is not asked of the kernel again.
    outcome, places, _ = searched(wide, FinParams(placement=d.PLACEMENT_CENTER))
    self, t, own, _ = next(place for place in places if place[3])
    real_inside = geometry._inside
    calls = []
    geometry._inside = lambda solid, point: calls.append(1) or real_inside(solid, point)
    try:
        again = self.surely_in_part(t, own)
        # A point on the surface of what stands out, and a kernel that cannot tell.
        front = geometry.in_front_of(self.part, self.whole_face)
        on_surface = front.Vertexes[0].Point
        deep = front.Solids[0].CenterOfMass
        expect(again and not calls, "a place told to stand in the part is not asked again")
        expect(real_inside(front.Solids[0], deep) and not real_inside(front.Solids[0], on_surface),
               "a point inside what stands out is inside it, one on its surface is not")

        class Failing:
            def isInside(self, *args):
                raise Part.OCCError("no classifier")
        expect(real_inside(Failing(), deep) is False, "where the kernel cannot tell, a point is not said to be inside")
    finally:
        geometry._inside = real_inside
    # Nothing in front of the face, a fin without a height, a round side: not said.
    cube = tilted_cube()
    outcome, places, _ = searched(cube, FinParams(placement=d.PLACEMENT_CENTER))
    expect(outcome == "built" and not any(found for *_, found in places),
           "a plain face: no place told to stand in the part (%d asked)" % len(places))
    expect(self.sure_points(t, 0.0, self.half_foot) == [], "a fin without a height has no points to ask")
    # What stands out in two solids: each is asked by itself.
    two = bossed_cube((BOSS_RADII[0], EDGE / 4), (BOSS_RADII[0], 3 * EDGE / 4))
    frame = face_frame.frame_of(two, lower_left_face(two))
    front = geometry.in_front_of(two, frame)
    hits = [sum(real_inside(solid, other.CenterOfMass) for solid in front.Solids) for other in front.Solids]
    expect(len(front.Solids) == 2 and hits == [1, 1],
           "two bosses stand out as two solids, a point in one is inside that one alone: %s" % hits)


def tapered(top_half, height):
    """A part whose face, leaning 45 degrees, tapers from TAPER_BASE_HALF at
    the bed to `top_half` at `height`, and that face."""
    def on_face(up, along):
        return V(-up, along, up)

    ring = [on_face(0, TAPER_BASE_HALF), on_face(height, top_half), on_face(height, -top_half),
            on_face(0, -TAPER_BASE_HALF)]
    stood = Part.Face(Part.makePolygon(ring + ring[:1])).extrude(V(TAPER_DEPTH, 0, 0))
    stood.translate(V(0, 0, -stood.BoundBox.ZMin))
    return stood, lower_left_face(stood)


def check_narrow_reason():
    """A tine of the one grid left out where the face narrows is named for
    why: narrower than the fin under it, or only narrower than a fin and its
    end insets need, with and without the restart."""
    for restart in (False, True):
        p = FinParams(placement=d.PLACEMENT_CENTER, tine_restart=restart)
        for (top_half, height), than_fin in ((TAPER_SHORT, False), (TAPER_NARROW, True)):
            stood, face = tapered(top_half, height)
            built = geometry.build(stood, face, p)
            named = [w for w in built.warnings if "left out: the face is narrower there than the" in w]
            expect(len(named) == 1 and named[0].endswith("than the fin") == than_fin,
                   "restart %s, a face tapering to %g mm at %g mm: %s" % (restart, 2 * top_half, height, named))


def main():
    cube = tilted_cube()
    face = lower_left_face(cube)

    separate = geometry.build(cube, face, FinParams())
    expect(separate.tine_z == [1.0, 6.0, 11.0], "tines at 1, 6 and 11 mm: %s" % separate.tine_z)
    expect(math.isclose(separate.height, 11.2), "fin height ends on the top tine")
    expect(len(separate.positions) == 1, "one fin on a 20 mm face")
    expect(math.isclose(separate.thickness, d.FIN_THICKNESS_BASE), "a fin below 100 mm is 1 mm thick")
    expect(separate.fins.common(cube).Volume < d.TOLERANCE, "fins do not overlap the cube")
    expect(len(separate.tines) == 3, "three tines on the fin")

    narrow = geometry.build(cube, face, FinParams(gap=0.2))
    expect(narrow.warnings, "0.2 mm gap warns about short tines")

    counter = geometry.build(cube, face, FinParams(), tine_count=1)
    expect(counter.tine_z == [1.0], "counter fin with one tine")

    one = geometry.build(cube, face, FinParams(placement=d.PLACEMENT_CENTER))
    expect(len(one.positions) == 1, "centre placement gives one fin")

    two = geometry.build(cube, face, FinParams(placement=d.PLACEMENT_ENDS))
    expect(len(two.positions) == 2, "end placement gives two fins")

    # Merged fins have no tine clearance: their tines reach the part.
    joined = geometry.merged(cube, geometry.build(cube, face, FinParams(connection=d.CONNECTION_MERGED)).fins)
    expect(len(joined.Solids) == 1, "merged mode gives one solid")

    try:
        geometry.build(cube, face, FinParams(tine_count=4))
    except face_frame.FinError as error:
        expect("only 3 of 4" in str(error), "a fourth tine does not fit: %s" % error)
    else:
        raise AssertionError("four tines were accepted")

    # Tines need a free layer between them, or they merge or round onto one layer.
    params = FinParams()
    least = params.tine_height + params.layer_height
    try:
        FinParams(tine_spacing=params.layer_height / 4).validate()
    except ParamError as error:
        expect("free layer" in str(error), "tines closer than a free layer are refused: %s" % error)
    else:
        raise AssertionError("tines on top of each other were accepted")
    FinParams(tine_spacing=least).validate()
    expect(True, "tines one free layer apart are accepted")

    # A first tine set by hand half a layer off the grid: rounding must not
    # bring two tines closer than a free layer.
    frame = face_frame.frame_of(cube, face)
    for offset in HALF_LAYER_STARTS:
        tall = FinParams(tine_layers=2, tine_first=offset)
        tall = FinParams(tine_layers=2, tine_first=offset, tine_spacing=tall.least_tine_spacing)
        zs = tine_rows.tine_heights(tall, frame, 0)[0]
        gap = min(b - a for a, b in zip(zs, zs[1:]))
        expect(gap > tall.least_tine_spacing - d.TOLERANCE,
               "first tine at %.1f mm: rounding keeps a free layer between tines (%.2f mm)" % (offset, gap))

    box = Part.makeBox(30, 10, 10)
    bottom = [e for e in box.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.Length == 10][0]
    change = orient.tilt(box, bottom, d.TILT_ANGLE)
    box.Placement = change.multiply(box.Placement)
    expect(abs(box.BoundBox.ZMin) < d.TOLERANCE, "tilted part rests on the bed")
    expect(box.BoundBox.ZMax > 10 + d.TOLERANCE, "tilted part stands up over the edge")
    leaning = [f for f in box.Faces if abs(f.normalAt(0, 0).z + math.sqrt(0.5)) < 1e-6]
    expect(leaning, "a face leans over the bed at 45 degrees")
    check_stand()

    steep = geometry.build(cube, face, FinParams())
    expect(not any("inclined" in w for w in steep.warnings), "45 degrees gives no angle warning")
    expect(not tine_rows._outlined, "the face a build asked the corners of is forgotten as the build ends")

    shape_regression(cube, face)

    opposite = geometry.opposite_faces(cube, face)[0]
    u0, u1, v0, v1 = opposite.ParameterRange
    normal = opposite.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
    expect(normal.x > 0 and normal.z < 0, "the opposite face leans the other way")

    for foot in (1.0, 2.0, 3.0):
        raised = geometry.build(cube, face, FinParams(foot_thickness=foot))
        expect(raised.tine_z[0] == foot and len(raised.fins.Solids) == 1,
               "with a %.0f mm foot the lowest tine sits on it and is attached" % foot)
    low = geometry.build(cube, face, FinParams(foot_thickness=3.0, tine_first=1.0))
    expect(len(low.fins.Solids) == 1, "a tine set below the top of the foot still reaches into the fin")
    check_corners(cube, face)
    check_overhangs(cube, face)
    check_limits()
    check_recesses(cube, face)
    check_frustum()
    check_loft()
    check_chamfer_and_fillet()
    check_tight_bounds()
    check_thickness()
    check_one_corner(cube, face)
    check_tine_ends(cube, face)
    check_tine_clearance(cube, face)
    check_shortened(cube, face)
    check_restart(cube, face)
    check_restart_short_stretch(cube, face)
    check_search_inset(cube, face)
    check_places_past_stretch()
    check_restart_narrow_lower_edge()
    check_moved_fins_feet()
    check_restart_names_what_fins_lack()
    check_restart_above_fillet()
    check_restart_planned(cube, face)
    check_restart_narrow(cube, face)
    check_restart_flank_hole(cube, face)
    check_wide_enough(cube, face)
    check_split_face()
    check_quick_fins()
    check_quick_plan()
    check_quick_plans()
    check_prism_side()
    check_cut_heights()
    check_faces_at()
    check_starts()
    check_islands()
    check_island_boxes()
    check_first_layers()
    check_bridge_lines()
    check_bridge_faces()
    check_bridges()
    check_no_fragile_calls()
    check_printable_plans()
    check_centres()
    check_stability()
    check_round_side()
    check_contour_pieces()
    check_contour()
    check_known_clear()
    check_meshed_distance()
    check_settled_clear()
    check_cut_at_height()
    check_three_round_fins()
    check_side_fin_matrix()
    check_part_of_side()
    check_split_side()
    check_left_out(cube, face)
    check_moved_fins(cube, face)
    check_merged_clearance(cube, face)
    check_fin_at(cube, face)
    check_boss_on_face()
    check_straight_faces()
    check_surely_in_part()
    check_enclosed()
    check_narrow_reason()
    print("all checks passed", file=sys.__stdout__)


run(main)
