# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""The version of FinSnap, read from package.xml at run time.

package.xml is the single source of the version; the Addon Manager reads it
from there as well. Nothing in the code repeats the number.

INPUTS this has to withstand (version()):
  package.xml with <version>1.2.3</version>  ->  "1.2.3"
  package.xml missing (copied package)       ->  UNKNOWN
  package.xml not well-formed                ->  UNKNOWN
  <version> empty or missing                 ->  UNKNOWN
"""

# Audited: Parses only package.xml of this addon.
import xml.etree.ElementTree as ET  # nosec B405

from .paths import PACKAGE_XML

NAMESPACE = {"p": "https://wiki.freecad.org/Package_Metadata"}
NAME = "FinSnap"
UNKNOWN = "unknown"

_cached = None


def version():
    global _cached
    if _cached is None:
        try:
            # Audited: package.xml of this addon.
            root = ET.parse(PACKAGE_XML).getroot()  # nosec B314
            _cached = (root.findtext("p:version", default="", namespaces=NAMESPACE) or "").strip() or UNKNOWN
        except (OSError, ET.ParseError):
            _cached = UNKNOWN
    return _cached


def application():
    """Name and version, as written into exported files and shown in the panel."""
    return "%s %s" % (NAME, version())
