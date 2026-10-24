"""Check that the version is consistent.

package.xml is the single source of the version; the Addon Manager reads it
from there. This check makes sure the changelog and a release tag agree.

Usage:
    python3 tools/check_version.py [tag]

INPUTS this has to withstand:
  version 0.1.0, changelog entry "## [0.1.0] - <date of package.xml>"  ->  exit 0
  version not of the form MAJOR.MINOR.PATCH (e.g. "0.1", "v0.1.0")     ->  exit 1
  no changelog entry for the version                                  ->  exit 1
  changelog date differs from <date> in package.xml                   ->  exit 1
  tag given and not "v" + version (e.g. "v0.1.1" for 0.1.0)            ->  exit 1
  tag given that is no version tag (branch name)                       ->  ignored
  package.xml or CHANGELOG.md missing                                 ->  exit 1
"""

import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.join(ROOT, "package.xml")
CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")
NAMESPACE = {"p": "https://wiki.freecad.org/Package_Metadata"}
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
TAG_PREFIX = "v"


def problems(tag=None):
    found = []
    try:
        root = ET.parse(PACKAGE).getroot()
        with open(CHANGELOG, encoding="utf-8") as handle:
            changelog = handle.read()
    except (OSError, ET.ParseError) as error:
        return [str(error)]

    version = (root.findtext("p:version", default="", namespaces=NAMESPACE) or "").strip()
    date = (root.findtext("p:date", default="", namespaces=NAMESPACE) or "").strip()
    if not SEMVER.match(version):
        found.append("package.xml version %r is not MAJOR.MINOR.PATCH" % version)

    entry = re.search(r"^## \[%s\] - (\S+)$" % re.escape(version), changelog, re.MULTILINE)
    if not entry:
        found.append("CHANGELOG.md has no entry '## [%s] - <date>'" % version)
    elif entry.group(1) != date:
        found.append("CHANGELOG.md dates %s %s, package.xml %s" % (version, entry.group(1), date))

    if tag and tag.startswith(TAG_PREFIX) and SEMVER.match(tag[len(TAG_PREFIX):]):
        if tag != TAG_PREFIX + version:
            found.append("tag %s does not match package.xml version %s" % (tag, version))
    return found


def main(argv):
    found = problems(argv[1] if len(argv) > 1 else None)
    for problem in found:
        print("version:", problem)
    if not found:
        print("version consistent")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
