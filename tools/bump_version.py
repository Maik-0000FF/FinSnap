"""Set a new version everywhere at once.

    python3 tools/bump_version.py 0.2.0 [2026-11-01]

Sets <version> and <date> in package.xml, turns the entries under
"[Unreleased]" in CHANGELOG.md into the new version's section, updates both
link lines, and runs tools/check_version.py on the result. The date defaults to
today. Commit and tag (v0.2.0) stay with you.

INPUTS this has to withstand:
  new version above the current one, entries under Unreleased  ->  files updated, exit 0
  version not MAJOR.MINOR.PATCH                                 ->  exit 1, nothing written
  version not above the current one (1.2.3 -> 1.2.3 or 1.2.2)   ->  exit 1, nothing written
  date not YYYY-MM-DD (or not a real date)                      ->  exit 1, nothing written
  nothing under [Unreleased]                                    ->  exit 1, nothing written
  repository is inconsistent before the bump                    ->  exit 1, nothing written
  check after writing fails                                     ->  exit 1 with the problems
"""

import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_version as cv  # noqa: E402

UNRELEASED_HEADING = "## [%s]" % cv.UNRELEASED


def parse(version):
    return tuple(int(part) for part in version.split("."))


def bump(root, new, date):
    """Write the new version into package.xml and CHANGELOG.md; returns a list of errors."""
    if not cv.SEMVER.match(new):
        return ["%r is not MAJOR.MINOR.PATCH" % new]
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        return ["%r is not a date YYYY-MM-DD" % date]
    before = cv.problems(root)
    if before:
        return ["fix this before bumping: " + p for p in before]

    old, _, repository, changelog = cv.read(root)
    if parse(new) <= parse(old):
        return ["%s is not above the current version %s" % (new, old)]

    start = changelog.find(UNRELEASED_HEADING)
    following = changelog.find("\n## [", start + len(UNRELEASED_HEADING))
    if start < 0 or following < 0 or not changelog[start + len(UNRELEASED_HEADING):following].strip():
        return ["nothing under %s in %s" % (UNRELEASED_HEADING, cv.CHANGELOG_NAME)]

    changelog = changelog.replace(UNRELEASED_HEADING,
                                  UNRELEASED_HEADING + "\n\n" + cv.heading(new, date), 1)
    changelog = changelog.replace(cv.unreleased_link(repository, old),
                                  cv.unreleased_link(repository, new) + "\n" + cv.release_link(repository, new), 1)

    package_path = os.path.join(root, cv.PACKAGE_NAME)
    with open(package_path, encoding="utf-8") as handle:
        package = handle.read()
    package = re.sub(r"<version>[^<]*</version>", "<version>%s</version>" % new, package, count=1)
    package = re.sub(r"<date>[^<]*</date>", "<date>%s</date>" % date, package, count=1)

    with open(package_path, "w", encoding="utf-8") as handle:
        handle.write(package)
    with open(os.path.join(root, cv.CHANGELOG_NAME), "w", encoding="utf-8") as handle:
        handle.write(changelog)
    return cv.problems(root)


def main(argv):
    if len(argv) not in (2, 3):
        print("Usage: python3 tools/bump_version.py <new version> [<date>]")
        return 1
    date = argv[2] if len(argv) == 3 else datetime.date.today().isoformat()
    errors = bump(cv.ROOT, argv[1], date)
    for error in errors:
        print("bump:", error)
    if errors:
        return 1
    print("version %s set; commit, then tag the commit %s%s" % (argv[1], cv.TAG_PREFIX, argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
