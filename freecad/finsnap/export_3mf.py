"""Write shapes to a 3MF file, one named object per shape.

Written by hand instead of through the mesh exporter so that every shape is
certain to arrive in the slicer as its own object. The separate connection
mode depends on that: fin and part must be sliced as two objects.

INPUTS this has to withstand (write()):
  list of (name, shape)                 ->  3MF with one object each, unit millimetre
  empty list                            ->  ValueError
  shape without solids (empty, a face)  ->  ValueError naming it
  name with &, <, > or quotes           ->  escaped in the XML
  same name twice                       ->  written as given; the slicer shows both
  linear or angle <= 0                  ->  ValueError
  application given                     ->  written as the Application metadata;
                                            default "FinSnap <version>"

WHAT THE FILE HOLDS: one object per shape, named as given, as a triangle mesh in
millimetres; the metadata Application (program and version) and CreationDate
(date of the export, ISO 8601). No print settings: the slicer opens it with its
own profile.
"""

import datetime
import math
import zipfile
from xml.sax.saxutils import escape, quoteattr

import MeshPart

from . import defaults as d
from .version import application as finsnap_application

CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" '
    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="model" '
    'ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
    '</Types>\n')

RELATIONSHIPS = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
    'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
    '</Relationships>\n')

MODEL_NAMESPACE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"


def _object_xml(number, name, shape, linear, angular_deg):
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=linear,
                                  AngularDeflection=math.radians(angular_deg), Relative=False)
    points, triangles = mesh.Topology
    parts = ['  <object id="%d" name=%s type="model"><mesh><vertices>' % (number, quoteattr(name))]
    parts += ['<vertex x="%.6f" y="%.6f" z="%.6f"/>' % (p.x, p.y, p.z) for p in points]
    parts.append("</vertices><triangles>")
    parts += ['<triangle v1="%d" v2="%d" v3="%d"/>' % t for t in triangles]
    parts.append("</triangles></mesh></object>")
    return "".join(parts)


def write(path, named_shapes, linear=d.MESH_LINEAR_DEFLECTION,
          angular_deg=d.MESH_ANGULAR_DEFLECTION_DEG, application=None):
    """linear: largest distance of the mesh from the surface in mm; angular_deg: largest
    angle between neighbouring triangles. Planar faces are exact either way."""
    if not (linear > 0 and angular_deg > 0):
        raise ValueError("mesh deviation and angle must be greater than 0")
    if not named_shapes:
        raise ValueError("nothing to export")
    for name, shape in named_shapes:
        if not shape.Solids:
            raise ValueError("%s has no solid to export" % name)

    objects = [_object_xml(i, name, shape, linear, angular_deg)
               for i, (name, shape) in enumerate(named_shapes, 1)]
    items = ['  <item objectid="%d"/>' % i for i in range(1, len(named_shapes) + 1)]
    metadata = [' <metadata name="Application">%s</metadata>' % escape(application or finsnap_application()),
                ' <metadata name="CreationDate">%s</metadata>' % datetime.date.today().isoformat()]
    model = "\n".join(['<?xml version="1.0" encoding="UTF-8"?>',
                       '<model unit="millimeter" xml:lang="en-US" xmlns="%s">' % MODEL_NAMESPACE,
                       *metadata, " <resources>", *objects, " </resources>",
                       " <build>", *items, " </build>", "</model>", ""])
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", RELATIONSHIPS)
        archive.writestr("3D/3dmodel.model", model)
