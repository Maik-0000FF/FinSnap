# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""The G-code check on small hand-written G-code files.

Run with Python and shapely 2.0 or newer, no FreeCAD needed:
    python3 -m freecad.finsnap.tests.test_check_gcode

Every case is one square part 10 mm wide with a fin beside it, in two layers.

CASES this has to withstand:
  tine touching the part, skirt 3 mm away
    in its own layer                        ->  passed
  part leaning out over the skirt in the
    layer above                             ->  passed: the skirt is compared within
                                                its own layer
  purge line before the first ;Z:, 1 mm
    from the part                           ->  finding: closer than allowed
  purge line before the first ;Z:, far away ->  passed
  tine ending short of the part             ->  finding: no contact
  fin path running into the part            ->  finding: crossing
  no M486 labels                            ->  unusable
"""

import contextlib
import io
import os
import tempfile

from freecad.finsnap.tools import check_gcode as cg

BEAD = 0.45
# The part: a square, left edge at PART_LEFT. A tine ends TOUCHING away from it
# (centre lines one bead apart, so the beads touch) or SHORT, out of reach.
PART_LEFT, PART_RIGHT = 10.0, 20.0
TOUCHING = PART_LEFT - BEAD
SHORT = PART_LEFT - 1.0
INSIDE = PART_LEFT + 2.0
FIN_START = 5.0
TINE_Y = 15.0
FIRST, SECOND = 0.2, 0.4
SKIRT_MARGIN = 3.0           # wider than UNLABELLED_DISTANCE
LEANING_OUT = 5.0            # how far the part reaches past its foot in the second layer
NEAR_PURGE = PART_LEFT - 1.0
FAR_PURGE = -50.0


def square(left, right):
    corners = [(left, left), (right, left), (right, right), (left, right), (left, left)]
    return ["G1 X%.3f Y%.3f" % corners[0]] + ["G1 X%.3f Y%.3f E0.1" % c for c in corners[1:]]


def line(start, end):
    return ["G1 X%.3f Y%.3f" % start, "G1 X%.3f Y%.3f E0.1" % end]


def layer(z, part, fin, unlabelled=()):
    return [";Z:%.1f" % z, *unlabelled, "M486 S0", *part, "M486 S-1", "M486 S1", *fin, "M486 S-1"]


def gcode(tine_end=TOUCHING, purge=None, labels=True):
    """A part and its fin in two layers; the part leans out in the second."""
    head = ["; %s = %.2f" % (cg.WIDTH_KEY, BEAD), "M83"]
    if labels:
        head += ["M486 S0", "M486 APart", "M486 S1", "M486 APart" + cg.FINS_SUFFIX, "M486 S-1"]
    if purge is not None:
        head += line((PART_LEFT, purge), (PART_RIGHT, purge))
    tine = line((FIN_START, TINE_Y), (tine_end, TINE_Y))
    # The skirt runs round part and fin, as a slicer draws it.
    skirt = square(FIN_START - SKIRT_MARGIN, PART_RIGHT + SKIRT_MARGIN)
    lines = head + layer(FIRST, square(PART_LEFT, PART_RIGHT), tine, skirt)
    lines += layer(SECOND, square(PART_LEFT - LEANING_OUT, PART_RIGHT + LEANING_OUT),
                   line((FIN_START - LEANING_OUT - 1, TINE_Y), (FIN_START - LEANING_OUT, TINE_Y)))
    if not labels:
        lines = [entry for entry in lines if not entry.startswith("M486")]
    return "\n".join(lines) + "\n"


def check(text):
    """Exit code and printed report of the check on `text`."""
    path = os.path.join(tempfile.mkdtemp(), "case.gcode")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    report = io.StringIO()
    with contextlib.redirect_stdout(report):
        code = cg.main(["check_gcode.py", path])
    return code, report.getvalue()


def expect(condition, message, report=""):
    if not condition:
        raise AssertionError("%s\n%s" % (message, report))
    print("ok  ", message)


def main():
    code, report = check(gcode())
    expect(code == cg.EXIT_OK, "a touching tine and a skirt in its own layer pass", report)

    code, report = check(gcode(purge=NEAR_PURGE))
    expect(code == cg.EXIT_FINDINGS and "closer than" in report,
           "a purge line before the first layer, 1 mm from the part, is found", report)
    code, report = check(gcode(purge=FAR_PURGE))
    expect(code == cg.EXIT_OK, "a purge line far from the part passes", report)

    code, report = check(gcode(tine_end=SHORT))
    expect(code == cg.EXIT_FINDINGS and "no layer" in report, "a tine short of the part is found", report)
    code, report = check(gcode(tine_end=INSIDE))
    expect(code == cg.EXIT_FINDINGS and "CROSSING" in report,
           "a fin path into the part is found", report)

    code, report = check(gcode(labels=False))
    expect(code == cg.EXIT_UNUSABLE, "G-code without object labels is refused", report)
    print("all checks passed")


if __name__ == "__main__":
    main()
