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
GAP = 0.25
# Clearance between the end of a tine and the face, along the face normal.
# 0: the tine touches the face. A test print with touching tines left visible
# marks; a clearance reduces them, but a bead swells a few hundredths of a
# millimetre, so too much and the tine no longer holds. Find it by a test print.
TINE_CLEARANCE = 0.0

# --- Tines --------------------------------------------------------------------
# Tines are horizontal, so each one is printed within its own layers.
TINE_SPACING = 5.0          # vertical distance between tine bottoms
# The tine grid starts anew at the lower edge of the face under each fin and
# above every gap it bridges; off, one grid counts from the bed for every fin.
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
# The same above the lower edge of a face that ends above the bed.
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
# Faces lying flatter than this against the bed need support; those without
# fins are reported and marked. 45 degrees is the usual limit of FDM printing.
OVERHANG_ANGLE = 45.0
# A part that stands, but whose plumb line comes closer to the edge of its
# footprint than this while it is printed, is only just standing (mm).
STABILITY_CLOSE = 2.0
# Smaller overhanging faces, like the corner facets of a chamfer, bridge over
# without support and are not reported (mm2).
OVERHANG_MIN_AREA = 1.0
# Grid of normals sampled per direction on a curved face.
OVERHANG_SAMPLES = 8
# How closely the mesh the lowest points of a part are looked for on follows
# its faces (mm): fine enough to find the lowest point of a fillet or a boss.
ISLAND_MESH_DEFLECTION = 0.1
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
