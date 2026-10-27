# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Write shapes to a STEP file, one named object per shape.

The other way into the slicer, beside 3MF: STEP keeps the exact surfaces
instead of a mesh. PrusaSlicer loads a STEP file as one object with a part per
shape; Split to objects then makes part and fins two objects again, which the
separate connection mode needs.

INPUTS this has to withstand (write()):
  list of (name, shape)                 ->  STEP with one named object each
  empty list                            ->  ValueError
  shape without solids (empty, a face)  ->  ValueError naming it
  same name twice                       ->  written as given; the slicer shows both
  edges on offset curves (a pocket
    offset from an ellipse)             ->  read back whole: every shape is written
                                            as NURBS, see write()
  shape meshed before (3MF export of
    the same shape)                     ->  read back whole, the shape untouched

WHAT THE FILE HOLDS: the solids in millimetres, each under the name given, in an
assembly named after the scratch document; PrusaSlicer names the objects after
the file and ignores it. No mesh and no print settings.
"""

import FreeCAD as App
import Import

from .i18n import translate

# Name of the document the shapes are placed in for the export, closed afterwards.
SCRATCH_DOCUMENT = "FinSnapStepExport"


def write(path, named_shapes):
    if not named_shapes:
        raise ValueError(translate("FinSnap", "nothing to export"))
    for name, shape in named_shapes:
        if not shape.Solids:
            raise ValueError(translate("FinSnap", "%s has no solid to export") % name)

    # The STEP writer takes document objects, whose labels become the names
    # in the file; a hidden document holds them, so the user's stays untouched.
    scratch = App.newDocument(SCRATCH_DOCUMENT, hidden=True, temp=True)
    try:
        objects = []
        for name, shape in named_shapes:
            obj = scratch.addObject("Part::Feature")
            obj.Label = name
            # Faces bounded by offset curves are written so that they cannot be
            # read back: the solid falls apart and the slicer drops it. As NURBS
            # the same surfaces, exact, come back whole. Converted from a copy:
            # a shape meshed before, by the 3MF export, comes out of toNurbs()
            # broken, and writing it can crash FreeCAD.
            obj.Shape = shape.copy().toNurbs()
            objects.append(obj)
        Import.export(objects, path)
    finally:
        App.closeDocument(scratch.Name)
