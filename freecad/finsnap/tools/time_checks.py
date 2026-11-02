# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Time the checks of a part: overhangs, islands, bridges and stability.

Run in FreeCAD without its window:
    freecad --console freecad/finsnap/tools/time_checks.py
Parts measured: the test parts of the tests, and the solids of the FreeCAD
documents in TIME_CHECKS_FILES, paths split as the PATH is (":" on Linux),
opened hidden and never saved. A document's parts are named by number only,
"file 1, part 2", so the output can be passed on without telling what they
are. TIME_CHECKS_TOP sets how many of the calls costing most are listed after
the table, by the time spent in them alone (default TOP_CALLS, 0 for none).

Each check runs as Check part runs it, with the layers, bead and limits of the
standard, on a fresh copy of the part, so nothing kept from one check speeds
up another.

INPUTS this has to withstand:
  no TIME_CHECKS_FILES                  ->  the test parts only
  a path that is missing or no document ->  a line saying so, the rest measured
  a document without solids             ->  nothing measured of it
  a part a check fails on               ->  the error in its column, the rest
                                            measured
  TIME_CHECKS_TOP not a whole number    ->  TOP_CALLS
  TIME_CHECKS_TOP below 1               ->  no calls listed
"""

import cProfile
import os
import pstats
import sys
import time

import FreeCAD as App

from freecad.finsnap import bridge, limits, overhang, stability
from freecad.finsnap import defaults as d
from freecad.finsnap.tests import support

FILES = "TIME_CHECKS_FILES"
TOP = "TIME_CHECKS_TOP"
TOP_CALLS = 15
# The test parts measured: a tube as large as the slot stands beside it.
TUBE = (support.SLOT_RADIUS, support.SLOT_HEIGHT, support.SLOT_RADIUS / 2)
# FreeCAD drops what goes to sys.stdout when it ends; this reaches the shell.
OUT = sys.__stdout__


def test_parts():
    yield "tilted cube", support.tilted_cube()
    yield "slot on its end", support.slot_on_end()
    yield "split tube", support.split_cylinder(*TUBE)


def document_parts(paths):
    """(name, shape) of every solid of the documents `paths` that nothing
    else in it is made from, named by number only."""
    for number, path in enumerate(paths, 1):
        try:
            doc = App.openDocument(path, True)
        except Exception as error:
            print("file %d: not opened (%s)" % (number, error), file=OUT)
            continue
        try:
            solids = [obj for obj in doc.Objects
                      if hasattr(obj, "Shape") and obj.Shape.Solids and not obj.InList]
            for index, obj in enumerate(solids, 1):
                yield "file %d, part %d" % (number, index), obj.Shape.copy()
        finally:
            App.closeDocument(doc.Name)


def checks(shape):
    """The checks of `shape`, as (name, run), each run as Check part runs it."""
    rating = limits.current()
    first, layer = d.FIRST_LAYER_HEIGHT, d.LAYER_HEIGHT
    return (("overhangs", lambda: overhang.rated(shape, (), rating)),
            ("islands", lambda: overhang.islands(shape, first, layer)),
            ("bridges", lambda: bridge.bridges(shape, first, layer, d.BEAD_WIDTH, rating)),
            ("stability", lambda: stability.check(shape, [], first, layer, {}, d.BRIM_WIDTH)))


def measure(name, shape, profile):
    """One line of the table: the size of `shape` and the seconds each check takes."""
    box = shape.BoundBox
    cells = []
    for check, run in checks(shape.copy()):
        start = time.perf_counter()
        profile.enable()
        try:
            run()
            cells.append("%s %6.2f s" % (check, time.perf_counter() - start))
        except Exception as error:
            cells.append("%s failed (%s)" % (check, error))
        finally:
            profile.disable()
    print("%-18s %4.0f x %4.0f x %4.0f mm  %4d faces  %s"
          % (name, box.XLength, box.YLength, box.ZLength, len(shape.Faces), "  ".join(cells)), file=OUT)
    OUT.flush()


def main():
    paths = [path for path in os.environ.get(FILES, "").split(os.pathsep) if path]
    profile = cProfile.Profile()
    for name, shape in test_parts():
        measure(name, shape, profile)
    for name, shape in document_parts(paths):
        measure(name, shape, profile)
    try:
        top = int(os.environ.get(TOP, TOP_CALLS))
    except ValueError:
        top = TOP_CALLS
    if top > 0:
        pstats.Stats(profile, stream=OUT).sort_stats("tottime").print_stats(top)
    OUT.flush()


main()
# freecadcmd stays open after a script; leave it with the table printed.
os._exit(0)
