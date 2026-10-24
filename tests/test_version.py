"""Version check and bump on copies of package.xml and CHANGELOG.md.

Run with plain Python, no FreeCAD needed:
    python3 tests/test_version.py
"""

import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import bump_version  # noqa: E402
import check_version as cv  # noqa: E402

NEW = "9.9.9"
DATE = "2030-01-31"
ENTRY = "- an entry for the next release"


def copy():
    folder = tempfile.mkdtemp()
    for name in (cv.PACKAGE_NAME, cv.CHANGELOG_NAME):
        shutil.copy(os.path.join(ROOT, name), folder)
    return folder


def edit(folder, name, old, new):
    path = os.path.join(folder, name)
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text.replace(old, new, 1))


def expect(condition, message):
    if not condition:
        raise AssertionError(message)
    print("ok  ", message)


def main():
    expect(not cv.problems(ROOT), "the repository itself is consistent")
    version = cv.read(ROOT)[0]

    folder = copy()
    edit(folder, cv.CHANGELOG_NAME, cv.unreleased_link(cv.read(folder)[2], version),
         cv.unreleased_link(cv.read(folder)[2], "0.0.1"))
    expect(cv.problems(folder), "a stale [Unreleased] link is found")

    folder = copy()
    edit(folder, cv.CHANGELOG_NAME, cv.release_link(cv.read(folder)[2], version) + "\n", "")
    expect(cv.problems(folder), "a missing release link is found")

    expect(cv.problems(ROOT, tag="v0.0.1"), "a tag that does not match is found")
    expect(not cv.problems(ROOT, tag="dev"), "a branch name is not taken for a tag")

    folder = copy()
    expect(bump_version.bump(folder, NEW, DATE), "a bump with nothing under Unreleased is refused")
    expect(bump_version.bump(folder, version, DATE), "a bump to the current version is refused")
    expect(bump_version.bump(folder, "1.0", DATE), "a version without patch number is refused")

    edit(folder, cv.CHANGELOG_NAME, bump_version.UNRELEASED_HEADING + "\n",
         bump_version.UNRELEASED_HEADING + "\n\n" + ENTRY + "\n")
    expect(not bump_version.bump(folder, NEW, DATE), "a bump sets every place and passes the check")
    new_version, new_date, _, changelog = cv.read(folder)
    expect((new_version, new_date) == (NEW, DATE), "package.xml holds the new version and date")
    expect(changelog.index(cv.heading(NEW, DATE)) < changelog.index(ENTRY), "the entry moved under the new version")
    expect(not cv.problems(folder, tag="v" + NEW), "the release tag matches after the bump")
    print("all checks passed")


if __name__ == "__main__":
    main()
