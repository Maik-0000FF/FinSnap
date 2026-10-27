# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Check that the version is consistent everywhere it appears.

package.xml is the single source of the version; the Addon Manager reads it
from there, and the workbench reads it at run time. Only CHANGELOG.md repeats
it, because its format asks for it. This check makes sure every place agrees.

Usage:
    python3 -m freecad.finsnap.tools.check_version [tag]

WHERE THE VERSION APPEARS, all checked here:
  package.xml   <version>, <date>, and the repository URL the links are built from
  CHANGELOG.md  heading "## [X.Y.Z] - <date>"
                link "[Unreleased]: <repository>/compare/vX.Y.Z...HEAD"
                link "[X.Y.Z]: <repository>/releases/tag/vX.Y.Z"
  git tag       vX.Y.Z on the release commit (given as argument by the CI)

INPUTS this has to withstand:
  everything consistent                                         ->  exit 0
  version not MAJOR.MINOR.PATCH (e.g. "1.2", "v1.2.3")          ->  exit 1
  no changelog heading for the version                          ->  exit 1
  changelog heading dated differently from <date>               ->  exit 1
  [Unreleased] link missing or comparing from another version   ->  exit 1
  release link of the version missing or pointing elsewhere     ->  exit 1
  no repository URL in package.xml                              ->  exit 1
  tag given and not "v" + version (e.g. "v1.2.4" for 1.2.3)     ->  exit 1
  tag given that is no version tag (branch name)                ->  ignored
  package.xml or CHANGELOG.md missing, package.xml malformed    ->  exit 1
"""

import os
import re
import sys
# Audited: Parses only package.xml of this repository.
import xml.etree.ElementTree as ET  # nosec B405

from freecad.finsnap.paths import ROOT

PACKAGE_NAME = "package.xml"
CHANGELOG_NAME = "CHANGELOG.md"
NAMESPACE = {"p": "https://wiki.freecad.org/Package_Metadata"}
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
TAG_PREFIX = "v"
UNRELEASED = "Unreleased"


def heading(version, date):
    return "## [%s] - %s" % (version, date)


def unreleased_link(repository, version):
    return "[%s]: %s/compare/%s%s...HEAD" % (UNRELEASED, repository, TAG_PREFIX, version)


def release_link(repository, version):
    return "[%s]: %s/releases/tag/%s%s" % (version, repository, TAG_PREFIX, version)


def read(root=ROOT):
    """(version, date, repository URL, changelog text) or raises OSError / ParseError."""
    # Audited: package.xml of this repository.
    package = ET.parse(os.path.join(root, PACKAGE_NAME)).getroot()  # nosec B314
    with open(os.path.join(root, CHANGELOG_NAME), encoding="utf-8") as handle:
        changelog = handle.read()
    version = (package.findtext("p:version", default="", namespaces=NAMESPACE) or "").strip()
    date = (package.findtext("p:date", default="", namespaces=NAMESPACE) or "").strip()
    repository = ""
    for url in package.findall("p:url", NAMESPACE):
        if url.get("type") == "repository":
            repository = (url.text or "").strip().rstrip("/")
    return version, date, repository, changelog


def problems(root=ROOT, tag=None):
    try:
        version, date, repository, changelog = read(root)
    except (OSError, ET.ParseError) as error:
        return [str(error)]

    found = []
    if not SEMVER.match(version):
        found.append("package.xml version %r is not MAJOR.MINOR.PATCH" % version)
    if not repository:
        found.append("package.xml has no repository URL")

    lines = changelog.splitlines()
    entry = re.search(r"^## \[%s\] - (\S+)$" % re.escape(version), changelog, re.MULTILINE)
    if not entry:
        found.append("CHANGELOG.md has no heading '%s'" % heading(version, "<date>"))
    elif entry.group(1) != date:
        found.append("CHANGELOG.md dates %s %s, package.xml %s" % (version, entry.group(1), date))

    for wanted in (unreleased_link(repository, version), release_link(repository, version)):
        if wanted not in lines:
            found.append("CHANGELOG.md lacks the link line '%s'" % wanted)

    if tag and tag.startswith(TAG_PREFIX) and SEMVER.match(tag[len(TAG_PREFIX):]):
        if tag != TAG_PREFIX + version:
            found.append("tag %s does not match package.xml version %s" % (tag, version))
    return found


def main(argv):
    found = problems(tag=argv[1] if len(argv) > 1 else None)
    for problem in found:
        print("version:", problem)
    if not found:
        print("version consistent")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
