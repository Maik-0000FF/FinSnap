# Changelog

All notable changes to FinSnap are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/Maik-0000FF/FinSnap/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Maik-0000FF/FinSnap/releases/tag/v0.2.0
[0.1.0]: https://github.com/Maik-0000FF/FinSnap/releases/tag/v0.1.0
