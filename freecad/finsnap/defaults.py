# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Default values for fin generation, in one place.

Every number the generator uses without being told otherwise lives here. The
task panel shows these as starting values, the feature stores them as
properties, and the geometry never hard-codes a value of its own.

Lengths are in millimetres.
"""

# --- Slicer settings ---------------------------------------------------------
# The fin is designed around the bead the printer lays down, so the slicer
# settings come first. They should match the print profile used later.
NOZZLE_DIAMETER = 0.4
BEAD_WIDTH = 0.45
LAYER_HEIGHT = 0.2
FIRST_LAYER_HEIGHT = 0.2
# Brim the slicer prints round what stands on the bed (mm); it holds the part
# like a wider footprint while it is printed. None by default.
BRIM_WIDTH = 0.0

# --- Connection ---------------------------------------------------------------
# "separate": the fin is its own object, tines only touch the part, no
#             extrusion path runs from one into the other.
# "merged":   fin and part are fused into one body, the tines are printed as
#             one continuous path with the part.
CONNECTION_SEPARATE = "separate"
CONNECTION_MERGED = "merged"
CONNECTIONS = (CONNECTION_SEPARATE, CONNECTION_MERGED)
CONNECTION = CONNECTION_SEPARATE

# Gap, tine width and tine height were chosen by a test print: of touching and
# merged fins with tines one to three layers high, separate fins with tines one
# bead wide and one layer high came off cleanest, leaving only faint contact points.
#
# Clearance between fin and supported face, measured along the face normal.
GAP = 0.3
# The largest gap taken (mm), and so the longest tines: longer, a tine hangs
# out from the fin too far to print straight.
GAP_MAX = 2.0
# A gap a warning proposes is rounded up to this (mm).
GAP_HINT_STEP = 0.01
# Clearance between the end of a tine and the face, along the face normal; the
# tines are as much shorter than the gap. 0: the tine touches the face, and the
# slicer joins tine and part into one bead. Test prints with 0.25 mm tines
# held with 0.04 mm and with this clearance, tine and part printed as separate
# beads; a bead swells a few hundredths of a millimetre, so too much and the
# tine no longer holds. Find it by a test print.
TINE_CLEARANCE = 0.05

# --- Tines --------------------------------------------------------------------
# Tines are horizontal, so each one is printed within its own layers.
TINE_SPACING = 5.0          # vertical distance between tine bottoms
# The tine grid starts anew at the lower edge of the face under each fin and
# above every interruption it reaches over; off, one grid counts from the bed for every fin.
TINE_RESTART = True
TINE_FIRST_AUTO = 0.0       # 0: the lowest tine sits on the top of the foot
TINE_LAYERS = 1             # tine height in layers
TINE_WIDTH_BEADS = 1        # tine width across the fin, in beads
TINE_COUNT_AUTO = 0         # 0: as many as fit below the top of the face
# How far a tine reaches into the fin body before it is fused with it.
TINE_INTO_FIN = 1.0

# --- Fin body -----------------------------------------------------------------
FIN_PLATEAU = 2.0           # flat top instead of a sharp tip
FIN_MIN_BEADS = 2           # thinnest automatic fin, in beads: one path out and one back
# Automatic thickness, from a test print: 1 mm held parts up to 100 mm high,
# printed by the slicer as one path out and one back. It is no whole number of
# beads on purpose; the slicer fills the rest. Taller fins grow in proportion,
# 1 mm per 100 mm.
FIN_THICKNESS_BASE = 1.0
FIN_THICKNESS_BASE_HEIGHT = 100.0
FIN_THICKNESS_AUTO = 0.0    # 0: from FIN_THICKNESS_BASE and the height, at least FIN_MIN_BEADS
FIN_HEIGHT_AUTO = 0.0       # 0: the top tine defines the height
# Distance kept from the top edge of the supported face, so the fin does not
# reach into the edge or chamfer above it.
FACE_TOP_MARGIN = 0.5
# The same above the lower edge of a face that ends above the bed, for the one
# grid from the bed. Tines restarted on the face start right at its lower edge
# instead: they are placed only where their whole end lies on the face.
FACE_BOTTOM_MARGIN = FACE_TOP_MARGIN

# --- Placement along the supported face ---------------------------------------
PLACEMENT_AUTO = "auto"
PLACEMENT_CENTER = "center"
PLACEMENT_ENDS = "ends"
PLACEMENT_DISTRIBUTED = "distributed"
# Two fins on the ends of the face: each tine lies whole on the face and ends
# flush with its end, so its mark merges with that edge.
PLACEMENT_CORNERS = "corners"
# One fin on one end of the face, tines as with "corners". Left and right as
# seen from outside, looking at the face.
PLACEMENT_CORNER_LEFT = "left corner"
PLACEMENT_CORNER_RIGHT = "right corner"
PLACEMENT_ONE_CORNER = (PLACEMENT_CORNER_LEFT, PLACEMENT_CORNER_RIGHT)
PLACEMENTS = (PLACEMENT_AUTO, PLACEMENT_CENTER, PLACEMENT_ENDS, PLACEMENT_CORNERS, *PLACEMENT_ONE_CORNER,
              PLACEMENT_DISTRIBUTED)
PLACEMENT = PLACEMENT_AUTO
FIN_COUNT = 3               # used by "distributed"
END_INSET = 0.5             # distance of the outer fins from the face ends
FACE_LENGTH_PER_FIN = 50.0  # "auto": one fin per this much face length, a single one centred

# --- Foot ---------------------------------------------------------------------
FOOT_ELLIPSE = "ellipse"
FOOT_RECTANGLE = "rectangle"
FOOT_NONE = "none"
FOOT_SHAPES = (FOOT_ELLIPSE, FOOT_RECTANGLE, FOOT_NONE)
FOOT_SHAPE = FOOT_ELLIPSE
FOOT_THICKNESS = 1.0        # thin enough to peel off without residue
FOOT_OVERHANG = 0.0         # how far the foot reaches past the straight outer end of the fin
FOOT_WIDTH_RATIO = 0.2      # foot width as a share of its length; 0.2 held well in print
FOOT_HALF_WIDTH_AUTO = 0.0  # 0: from FOOT_WIDTH_RATIO, limited by the neighbours
# Minimum space left between the feet of neighbouring fins. On tall, narrow
# parts the fins stand close together and the feet are narrowed to keep it.
FOOT_CLEARANCE = 1.0

# --- Counter fin --------------------------------------------------------------
# A small fin on the opposite face, against tipping away from the main fin.
COUNTER_TINE_COUNT_AUTO = 0  # 0: as many tines as the main fin, so the same size
# Minimum cosine between the lean of the counter face and the reverse lean of
# the main face, for the automatic search of the opposite face.
OPPOSITE_DIRECTION = 0.9

# --- Warnings -----------------------------------------------------------------
# Inclination of the supported face against the bed. Outside this range the
# face is either close to a flat overhang or close to a wall.
FACE_ANGLE_MIN = 30.0
FACE_ANGLE_MAX = 60.0
# Angle the tilt command offers first.
TILT_ANGLE = 45.0
# Two faces count as square to each other within this many degrees, so that an
# edge alone stands the part. Solids converted from a mesh are rarely exact.
RIGHT_ANGLE_TOLERANCE = 0.5
# The built-in limits of the checks, those of the normal strictness; the user
# chooses another or sets their own in Edit > Preferences (limits.py). Angles
# are measured from the bed: 0 degrees is a face lying flat over it, 90 a
# vertical wall.
# Faces lying flatter than this need support; those without fins are reported
# as critical. 45 degrees is the usual limit of FDM printing.
OVERHANG_ANGLE = 45.0
# Faces lying flatter than this sag or fail even with good cooling: not printable.
OVERHANG_UNPRINTABLE_ANGLE = 30.0
# A part that stands, but would tip once leaned by less than this tipping
# angle while it is printed, is at risk of tipping (degrees, see stability.py).
# About a margin of 2 mm with the centre of mass 20 mm over the bed.
TIPPING_ANGLE = 5.0
# Gravity, to say which acceleration from the side a tipping angle withstands
# (mm/s2).
GRAVITY = 9806.65
# The strict strictness counts the geometry alone: no band of critical
# overhangs, a face needing support is not printable; and no grip of the first
# layer on the bed, so a larger tipping angle holds against the nozzle and the
# moving bed: 15 degrees withstands about 0.27 g from the side, as a bed slinger
# accelerates (degrees).
STRICT_OVERHANG_UNPRINTABLE_ANGLE = OVERHANG_ANGLE
STRICT_TIPPING_ANGLE = 15.0
# A bridge spanning further than this between its supports sags: critical (mm).
BRIDGE_CRITICAL = 2.0
# Further than this, a common printer no longer bridges it: not printable (mm).
BRIDGE_UNPRINTABLE = 10.0
# Strict counts any bridge needing more than a short span as not printable.
STRICT_BRIDGE_UNPRINTABLE = BRIDGE_CRITICAL
# Smaller overhanging faces, like the corner facets of a chamfer, are printed
# over without support and are not reported (mm2).
OVERHANG_MIN_AREA = 1.0
# Grid of normals sampled per direction on a curved face.
OVERHANG_SAMPLES = 8
# How closely the mesh the lowest points of a part are looked for on follows
# its faces (mm): fine enough to find the lowest point of a fillet or a boss.
ISLAND_MESH_DEFLECTION = 0.1
# How closely the mesh the centres of mass of a part are worked out on follows
# its faces (mm). The same as for islands: the kernel keeps one mesh with the
# shape, and a finer one asked first would be reused for the islands. At 0.1 mm
# a centre lies within a few hundredths of a millimetre of the exact one.
CENTRE_MESH_DEFLECTION = ISLAND_MESH_DEFLECTION
# Two sections of neighbouring layers overlapping by less than this area carry
# nothing (mm2): they only touch.
ISLAND_MIN_OVERLAP = 1e-6
# A tine shorter than this share of a bead is not printed to its end. Measured
# with a 0.45 mm bead: a 0.28 mm tine fell short, a 0.35 mm tine reached.
TINE_MIN_LENGTH_BEADS = 0.75
# Share of the end of a tine that has to lie on the face: all of it. A tine
# partly over a recess or a hole would hang free there and print unevenly, so
# it is left out.
TINE_MIN_CONTACT = 1.0

# --- Round sides --------------------------------------------------------------
# A cylinder or tube stands on its rim, and its fin under the lowest line of its
# curved side, built on the plane touching the side there. Off that line the
# side falls away behind the plane; a tine still ends on it where it lies no
# further behind than this (mm), a fifth of the gap.
ROUND_SIDE_MAX_DROP = 0.05
# The end of a tine counts as on the face, or the tine clearance short of it,
# within this (mm): as far as a round side may fall away behind the plane its
# tines end on. Further off, the tine misses the face or reaches into the part.
TINE_END_TOLERANCE = ROUND_SIDE_MAX_DROP

# --- Contour ------------------------------------------------------------------
# The fin under a whole round side follows the contour of the part up to its
# top, as a cut through the lowest line shows it: steps, cones, fillets and
# curves alike. Off, it stands under the round side alone.
FOLLOW_CONTOUR = True
# Recesses in the contour lower than this (mm), small chamfers, fillets, holes
# and grooves, the fin bridges straight; its tines there are left out.
CONTOUR_BRIDGE = 3.0
# Over a face of the contour looking up, where no tine rests, the fin keeps
# this gap from the part (mm), larger than GAP, so it cannot stick to it there.
CONTOUR_GAP = 1.0
# Heights at which the contour is sampled, per layer: finer than a layer, so
# the fin keeps its distance also across a fillet between two samples.
CONTOUR_SAMPLES_PER_LAYER = 4
# Cuts across the thickness of the fin, its middle and both faces among them,
# the gap kept from each: a hole narrower than the fin is open in the middle
# cut alone, and its edges lie beside it.
CONTOUR_CUTS = 5
# At a corner of the part the fin keeps its gap with a sharp corner too, its
# flank on along each face to where the two meet; at a corner sharper than
# about 127 degrees of turn, as far as this many gaps past it, then rounded.
CONTOUR_MITRE_LIMIT = 2.0
# The contour goes on on the same face past a stretch without tines, a pocket
# in it, where it comes back within this (mm) of where it would have run; the
# fin then runs straight past.
CONTOUR_SAME_LINE = 0.05
# How far a curve of the contour may lie off the straight pieces it is cut
# into (mm), and how much closer than its gap the fin may come along the
# contour: between two samples and at a curve. Within it the flank stays as
# the samples give it, so it keeps straight; past it, the samples beside a
# corner are raised. Between two cuts, as at the edge of a hole narrower
# than the fin, nothing bounds it beforehand, by decision: geometry.check()
# measures the fin against the part itself and refuses one that comes closer.
CONTOUR_DEFLECTION = 0.001
CONTOUR_TOLERANCE = 0.005
# Of that, what a run between two samples may come closer before they are
# raised, and as much again what the flank may shift as it is drawn with
# fewer points: together with the curve off its pieces, the tolerance.
CONTOUR_SHARE = (CONTOUR_TOLERANCE - CONTOUR_DEFLECTION) / 2
# The flank of the fin never runs inward up the contour more steeply than
# this angle from the bed allows: the fin itself prints without an overhang.
FIN_FLANK_ANGLE = OVERHANG_ANGLE

# --- Checks -------------------------------------------------------------------
TOLERANCE = 1e-4
# Layer positions are rounded to this many decimals, so that 5 x 1.2 is 6.0.
LENGTH_DECIMALS = 6
# Below this the face counts as vertical or flat and cannot carry a fin.
MIN_NORMAL_COMPONENT = 1e-3

# --- Export -------------------------------------------------------------------
# 10 µm and 1 degree: finer than PrusaSlicer's G-code resolution (0.0125 mm),
# coarser would show facets on round features.
MESH_LINEAR_DEFLECTION = 0.01
MESH_ANGULAR_DEFLECTION_DEG = 1.0
