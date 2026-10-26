# Changelog

All notable changes to FinSnap are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Single fins can be removed: click one in the 3D view and press Delete, or Remove selected fin in the task panel; Bring removed fins back restores them
- The task panel adds and removes the counter fin
- A face split by a groove across it is supported together with the piece beyond the groove: the fin reaches over the gap, the tines over it are left out and named
- Quick fins: select an edge, and the part stands on it with one fin under its largest leaning face; or select a face, and the part is turned so that it leans 45 degrees over the bed with one fin under it. A face with one of its edges, or with a chamfer or fillet beside it, sets what the part stands on; a fillet alone or the two faces beside it carry it too. A counter fin is added opposite where one fits
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
- The drawings in the task panel are larger and show the tine clearance

### Fixed

- Long tooltips in the task panel wrap instead of running off the screen
- The fields of the task panel step by sizes that suit them; heights on the layer grid step by the layer height entered
- Quick fins takes a chamfer selected alone, however wide, as what the part rests on, not as the face for the fins
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

[Unreleased]: https://github.com/Maik-0000FF/FinSnap/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/Maik-0000FF/FinSnap/releases/tag/v0.3.0
[0.2.0]: https://github.com/Maik-0000FF/FinSnap/releases/tag/v0.2.0
[0.1.0]: https://github.com/Maik-0000FF/FinSnap/releases/tag/v0.1.0
