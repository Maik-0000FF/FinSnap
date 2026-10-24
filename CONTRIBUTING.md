# Contributing

Thanks for your interest in improving FinSnap. Contributions of all kinds are welcome; one of the easiest is a **translation** of the user interface.

## Adding a language

The texts of the workbench live in Qt translation files under [`freecad/finsnap/translations/`](freecad/finsnap/translations/). Adding a language needs no code change.

1. Copy `finsnap_de.ts` to `finsnap_<code>.ts`, for example `finsnap_fr.ts`, and set `language="fr"` in its header.
2. Translate the texts, for example with Qt Linguist.
3. Compile it: `lrelease freecad/finsnap/translations/finsnap_fr.ts`.
4. Restart FreeCAD with that language selected under **Edit → Preferences → General**.

After changing texts in the code, refresh the `.ts` files with `tools/update_translations.sh`.

## Submitting a change

1. Fork the repository and create a branch.
2. Run the tests in FreeCAD's console:
   ```bash
   freecad --console tests/test_cube.py
   freecad --console tests/test_feature.py
   QT_QPA_PLATFORM=offscreen freecad tests/test_gui.py
   python3 tests/test_version.py
   ```
3. Open a pull request against the **`dev`** branch and describe what you changed and why.

Default values belong in [`freecad/finsnap/defaults.py`](freecad/finsnap/defaults.py), new parameters in the table in [`feature.py`](freecad/finsnap/feature.py); the task panel and the object are generated from it.

Icons, logo and the drawings of the task panel are written by `tools/make_icons.py` and `tools/make_drawings.py`. Change the scripts and run them, not the SVG files.

## Versioning

FinSnap follows [Semantic Versioning](https://semver.org/). The version lives in one place, `<version>` in [`package.xml`](package.xml). The FreeCAD Addon Manager reads it from there, and the workbench reads it at run time for the title of its task panel, its tooltip and the metadata of exported files. Only [`CHANGELOG.md`](CHANGELOG.md) repeats it, in the heading of the release and in two link lines at the bottom.

A release:

1. Add the changes under `[Unreleased]` in `CHANGELOG.md` while working.
2. Run `python3 tools/bump_version.py 0.2.0`. It sets version and date in `package.xml`, moves the entries under the new version, updates both links and checks the result.
3. Commit, then tag the commit `v0.2.0`.

`tools/check_version.py` runs in the CI and fails if any of these places disagree, including a tag that does not match.

## Other contributions

Bug reports and feature ideas are welcome as [issues](https://github.com/Maik-0000FF/FinSnap/issues). A photo of a test print and the slicer settings help a lot.
