# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Turn an STL mesh into a solid that fins can be built on.

A mesh has no exact faces, only triangles. Sewing them into a solid and
merging coplanar triangles gives planar faces again, which is all the fin
generator needs. Curved regions stay faceted; fins on them are not supported.

INPUTS this has to withstand (solid_from_mesh()):
  closed mesh of a printable part        ->  refined solid
  open mesh (holes)                      ->  ValueError: no solid
  empty mesh                             ->  ValueError
"""

import Part

from .i18n import translate

# Sewing tolerance for mesh points, in millimetres.
SEW_TOLERANCE = 0.01


def solid_from_mesh(mesh):
    if mesh.CountFacets == 0:
        raise ValueError(translate("FinSnap", "the mesh is empty"))
    shell = Part.Shape()
    shell.makeShapeFromMesh(mesh.Topology, SEW_TOLERANCE)
    try:
        solid = Part.makeSolid(Part.makeShell(shell.Faces))
    except Part.OCCError:
        raise ValueError(translate("FinSnap", "the mesh is not closed"))
    if not solid.isValid() or solid.Volume <= 0:
        raise ValueError(translate("FinSnap", "the mesh is not closed"))
    return solid.removeSplitter()
