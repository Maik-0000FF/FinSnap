<!--
SPDX-FileCopyrightText: 2026 Maik-0000FF
SPDX-License-Identifier: GPL-3.0-or-later
-->

# Changelog

All notable changes to FinSnap are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- The arrow up takes the height of a fin from tine to tine, so a tine always ends the fin on top, without a piece standing out above it: near a tine the fin goes there, between tines, also over a recess, it is built as high as the arrow and shown yellow, and goes to the nearest tine that finds the face when let go
- The arrows on a fin keep their size on the screen, also on small fins and when zoomed out
- A list of fins in the task panel, one below the other, the counter fins included: a fin picked there gets the arrows and is selected, also one behind the part

### Changed

- Shorter description in the Addon Manager, which also shows the README with its pictures now
- The translation files are named `FinSnap_<language>.ts`, with the template `FinSnap.ts` as the start of a new language
- Tests and tools lie in the package, `freecad/finsnap/tests/` and `freecad/finsnap/tools/`, and come with the addon; run them as described in CONTRIBUTING.md
- The arrows on a fin are double arrows standing just outside it, so the fin no longer covers the arrow up; an end is left out where the fin cannot go
- A fin let go where it cannot stand goes as far towards there as it can, to the corner of the face or next to its neighbour, instead of staying at its last place
- While a fin cannot stand where its arrow is, it alone turns red and the other fins stay green, so the red preview no longer mixes with green
- Dragging a fin is about three times as fast: each place is built once, and what the drag does not change, the other fins and the overhangs of the part, is built once per drag; the arrow ends are tried once per place of the fin

### Fixed

- A fin dragged where it cannot stand is tried first and never built there, so the object stays valid and the report view gets no traceback at every step of the drag
- The report view shows the warnings of the fins when they change, instead of again at every rebuild, such as at each step of a drag
- Add counter fin no longer takes a face still selected from making the fins, such as the chamfer Quick fins stood the part on; a face chosen by hand that cannot take fins is refused with a note, and the counter fin stays as it was

## [0.4.1] - 2026-10-27

### Fixed

- Fins merged into the part ignore the tine clearance, so they no longer print loose; the field is greyed out then
- A change by hand that does not fit over a groove is refused, instead of building the fins under the selected face alone
- Cancel after Quick fins also stands the part back as it was
- Without a 3D view the task panel says so instead of failing
- A counter fin moved to another face starts without the changes by hand of the old one
- Lay flat again closes a task panel open on the fins before deleting or moving them
- Cancel after Quick fins is one step on the undo stack

## [0.4.0] - 2026-10-26

### Added

- Single fins can be removed: click one in the 3D view and press Delete, or Remove selected fin in the task panel; removing the last fins deletes the fins object, as deleting it in the tree does
- Single fins can be moved along the face and given a height of their own: while the task panel is open, two arrows in the 3D view sit on the upright outer edge of the first fin, or of a fin clicked, sized by its height and in the colours of the axes. The fin follows an arrow while it is dragged; where it cannot stand it stays at its last place and is shown red where the arrow is. Under Edit fins, Place on the face and Height show where the fin stands; after a drag the field takes the keyboard, and a value typed and Enter move the fin. The fins are see-through green while editing, red while they cannot be built, and tines that find no face are marked red
- Reset fins in the task panel undoes every change by hand: removed fins come back, moved fins and fin heights of their own are undone. With another number of fins the changes by hand are undone as well, and a note says so
- The task panel adds and removes the counter fin; its Edit fins buttons show icons
- A face split by a groove across it is supported together with the piece beyond the groove: the fin reaches over the gap, the tines over it are left out and named
- Quick fins: select an edge, and the part stands on it with one fin under its largest leaning face; or select a face, and the part is turned so that it leans 45 degrees over the bed with one fin under it. A face with one of its edges, or with a chamfer or fillet beside it, sets what the part stands on; a fillet alone or the two faces beside it carry it too. A counter fin, where wanted, is added in the task panel
- Stand on edge takes an edge between two flat faces at a right angle alone and stands the part on it at 45 degrees
- Export STEP: exact surfaces instead of a mesh, every body under its own name; split the object into objects in the slicer
- Tine clearance: the tines end short of the face, and the fin moves out by as much, so the tines keep their length
- Fin placement left corner and right corner: one fin on that end of the face
- Lay flat again asks whether to delete the fins; kept fins move along with the part and are rebuilt once it is moved again

### Changed

- After Stand on edge the view looks along the edge from the side, so the tilt angle shows; after Lay flat again it is isometric
- Automatic fins are 1 mm thick up to 100 mm of height and grow by 1 mm per 100 mm above, at least two beads (before: at least three beads, growing with 5 % of the height); the foot width ratio is 0.2 instead of 0.5. Saved files with automatic values get thinner fins and narrower feet when they are rebuilt
- An automatic fin ends at its highest tine that finds the face
- Warnings name the main or the counter fin
- Fins of a part laid flat are left out of an export, and a message names them
- The red overhang marks are hidden while the part they lie on is hidden, not only while the fins are
- The drawings in the task panel are larger and show the tine clearance

### Fixed

- Long tooltips in the task panel wrap instead of running off the screen
- The fields of the task panel step by sizes that suit them; heights on the layer grid step by the layer height entered
- Quick fins takes a chamfer selected alone, of any width or angle, as what the part rests on, not as the face for the fins
- Heights are measured on the surfaces: the bounding box of curved faces reached up to 1.7 mm past a fillet, so outer fillets were refused as resting faces, a part laid on one floated above the bed, and fins could reach below it
- The command icons in the README show on GitHub

## [0.3.0] - 2026-10-24

### Added

- Save as standard and Factory settings in the task panel: new fins start with the saved values
- Fields that differ from the standard are marked, with a button beside each that puts the standard back

### Changed

- Warnings and refusals in the task panel stand out in a framed box with a sign, apart from the result line
- With a fixed tine count, tines a narrowing face cannot take are left out and named in a warning instead of refusing the fin
- Tine spacing must now be at least the tine height plus one layer, as closer tines merged or lay on top of each other; files with a smaller spacing show a message with the least value instead of building the fins

### Fixed

- A tine over a recess or hole in the face stopped the whole fin; tines that do not lie wholly on the face are now left out with a warning, and a fin with no tine left is left out as well
- A first tine set by hand half a layer off the grid could round two tines so close that they touched; the upper one now moves up to keep a free layer
- Fins on a face the part had lost stopped all other fins of that part
- Exporting an object without a shape raised an error instead of a message
- Add counter fin accepted a face of another part

## [0.2.0] - 2026-10-24

### Added

- Stand on edge takes any edge together with the face that is to lie on the bed, or a chamfer or fillet alone, which then carries the part, or the two faces beside it
- Lay flat again command; deleting the last fins of a part lays it flat as well
- Corner placement: two fins on the face ends, each tine whole on the face and flush with its end, so the tine marks merge with the edges
- Overhang check: faces flatter than 45 degrees without fins are marked red, listed as a warning and selected after Stand on edge

### Changed

- The task panel shows every change right away instead of on Preview, and greys out fields that have no effect with the current choices
- Error messages and warnings follow the language of FreeCAD

### Fixed

- The task panel showed the last result instead of the reason when no fins could be built
- Stand on edge refused the straight side edges of lofts and tapered Pads as curved
- Tines were drawn into the part and cut back by it; beside a face sloping away a rest stuck out. Tines now end in the plane of the face and are all equally long
- Fins under a face that narrows, like the side of a frustum, failed because the lowest tines missed the face; such tines are now left out with a warning
- Cancel in the task panel kept the changes made to existing fins

## [0.1.0] - 2026-10-24

### Added

- Fins under a face that leans over the bed, with horizontal tines that touch the part
- Separate and merged connection modes
- Tine, fin, placement and foot parameters sized from the slicer settings, all with automatic values that can be overridden
- Counter fin on the opposite face, also added afterwards with its own command
- Stand on edge command, tilting a part about a bottom edge
- Mesh to solid command for STL files
- 3MF export with every body as its own object and adjustable mesh fineness
- English and German user interface
- Version read from package.xml, shown in the task panel and the workbench tooltip and written into exported 3MF files

[Unreleased]: https://github.com/Maik-0000FF/FinSnap/compare/v0.4.1...HEAD
[0.4.1]: https://github.com/Maik-0000FF/FinSnap/releases/tag/v0.4.1
[0.4.0]: https://github.com/Maik-0000FF/FinSnap/releases/tag/v0.4.0
[0.3.0]: https://github.com/Maik-0000FF/FinSnap/releases/tag/v0.3.0
[0.2.0]: https://github.com/Maik-0000FF/FinSnap/releases/tag/v0.2.0
[0.1.0]: https://github.com/Maik-0000FF/FinSnap/releases/tag/v0.1.0
