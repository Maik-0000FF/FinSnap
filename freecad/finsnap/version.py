"""The version of FinSnap, read from package.xml at run time.

package.xml is the single source of the version; the Addon Manager reads it
from there as well. Nothing in the code repeats the number.

INPUTS this has to withstand (version()):
  package.xml with <version>1.2.3</version>  ->  "1.2.3"
  package.xml missing (copied package)       ->  UNKNOWN
  package.xml not well-formed                ->  UNKNOWN
  <version> empty or missing                 ->  UNKNOWN
"""

import os
import xml.etree.ElementTree as ET

# package.xml sits in the root of the addon, two levels above this package.
PACKAGE_XML = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                           "package.xml")
NAMESPACE = {"p": "https://wiki.freecad.org/Package_Metadata"}
NAME = "FinSnap"
UNKNOWN = "unknown"

_cached = None


def version():
    global _cached
    if _cached is None:
        try:
            root = ET.parse(PACKAGE_XML).getroot()
            _cached = (root.findtext("p:version", default="", namespaces=NAMESPACE) or "").strip() or UNKNOWN
        except (OSError, ET.ParseError):
            _cached = UNKNOWN
    return _cached


def application():
    """Name and version, as written into exported files and shown in the panel."""
    return "%s %s" % (NAME, version())
