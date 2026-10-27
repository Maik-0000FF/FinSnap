<!--
SPDX-FileCopyrightText: 2026 Maik-0000FF
SPDX-License-Identifier: GPL-3.0-or-later
-->

# Contributing

Thanks for your interest in improving FinSnap. Contributions of all kinds are welcome; one of the easiest is a **translation** of the user interface.

## Adding a language

The texts of the workbench live in Qt translation files under [`freecad/finsnap/translations/`](freecad/finsnap/translations/). Adding a language needs no code change.

1. Run `freecad/finsnap/tools/update_translations.sh <code>`, for example `fr`. It writes `FinSnap_fr.ts` from the template `FinSnap.ts`, with every text untranslated.
2. Translate the texts, for example with Qt Linguist.
3. Run `freecad/finsnap/tools/update_translations.sh` again; it compiles every language to `.qm`.
4. Restart FreeCAD with that language selected under **Edit → Preferences → General**.

After changing texts in the code, refresh the `.ts` files with `freecad/finsnap/tools/update_translations.sh`.

## Submitting a change

1. Fork the repository and create a branch.
2. Install the checkout as an addon: link it into the `Mod` folder of your FreeCAD user data directory (`App.getUserAppDataDir()` in FreeCAD's Python console shows it), for example `ln -s "$PWD" ~/.local/share/FreeCAD/v1-1/Mod/FinSnap`.
3. Run the tests from the repository root:
   ```bash
   freecad --console freecad/finsnap/tests/test_cube.py
   freecad --console freecad/finsnap/tests/test_feature.py
   QT_QPA_PLATFORM=offscreen freecad freecad/finsnap/tests/test_gui.py
   python3 -m freecad.finsnap.tests.test_version
   ```
4. Open a pull request against the **`dev`** branch and describe what you changed and why.

Default values belong in [`freecad/finsnap/defaults.py`](freecad/finsnap/defaults.py), new parameters in the table in [`feature.py`](freecad/finsnap/feature.py); the task panel and the object are generated from it.

Icons, logo and the drawings of the task panel are written by `python3 -m freecad.finsnap.tools.make_icons` and `python3 -m freecad.finsnap.tools.make_drawings`. Change the scripts and run them, not the SVG files.

## Versioning

FinSnap follows [Semantic Versioning](https://semver.org/). The version lives in one place, `<version>` in [`package.xml`](package.xml). The FreeCAD Addon Manager reads it from there, and the workbench reads it at run time for the title of its task panel, its tooltip and the metadata of exported files. Only [`CHANGELOG.md`](CHANGELOG.md) repeats it, in the heading of the release and in two link lines at the bottom.

A release:

1. Add the changes under `[Unreleased]` in `CHANGELOG.md` while working.
2. Run `python3 -m freecad.finsnap.tools.bump_version 0.2.0`. It sets version and date in `package.xml`, moves the entries under the new version, updates both links and checks the result.
3. Commit, then tag the commit `v0.2.0`.

`freecad/finsnap/tools/check_version.py` runs in the CI and fails if any of these places disagree, including a tag that does not match.

## Other contributions

Bug reports and feature ideas are welcome as [issues](https://github.com/Maik-0000FF/FinSnap/issues). A photo of a test print and the slicer settings help a lot.
