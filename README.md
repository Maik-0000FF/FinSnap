<!--
SPDX-FileCopyrightText: 2026 Maik-0000FF
SPDX-License-Identifier: GPL-3.0-or-later
-->

# FinSnap | Breakaway fins for FreeCAD

![FinSnap](https://raw.githubusercontent.com/Maik-0000FF/FinSnap/main/docs/assets/logo.svg)

[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![FreeCAD 1.1+](https://img.shields.io/badge/FreeCAD-1.1%2B-418FDE?logo=freecad&logoColor=white)](https://www.freecad.org/)
[![CI](https://github.com/Maik-0000FF/FinSnap/actions/workflows/ci.yml/badge.svg)](https://github.com/Maik-0000FF/FinSnap/actions/workflows/ci.yml)
[![Sponsor](https://img.shields.io/badge/Sponsor-%E2%9D%A4-pink?logo=github)](https://github.com/sponsors/Maik-0000FF)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20me-ff5e5b?logo=ko-fi&logoColor=white)](https://ko-fi.com/maik0000ff)

**A FreeCAD workbench that adds breakaway fins to parts printed standing on an edge.**

Printing a part tilted by 45 degrees puts the layer lines diagonal to the load and gives every side the same surface finish, with no bottom face and no top face. A part standing on an edge has almost no grip on the bed, though. FinSnap adds thin fins next to it that hold it upright. The fins touch the part only with small horizontal tines, so they snap off without leaving marks.

![FinSnap in FreeCAD: a tilted 40 mm cube with a fin and the task panel](https://raw.githubusercontent.com/Maik-0000FF/FinSnap/main/docs/assets/screenshot.png)

![FinSnap at work: Quick fins stands a part on its chamfer, the fin's height is dragged from tine to tine over a recess, and the fin is moved along the face past its corner, where it stops](https://raw.githubusercontent.com/Maik-0000FF/FinSnap/main/docs/assets/demo.gif)

## Why print standing on an edge

A part printed flat is weakest straight across its layers, and two of its faces differ from all the others. Standing on an edge at 45 degrees changes that:

- **Strength:** the layer boundaries run diagonally through the part. A load along one of its main axes no longer pulls a single layer seam apart; it is shared between layers and extrusion paths.
- **Surface:** every side shows the same layer pattern. There is no smooth bottom next to a top skin with a pattern of its own, and no first-layer imprint on a visible face.
- **Accuracy:** no face rests on the bed, only the edge the part stands on, so no outline is widened by the squashed first layer (elephant's foot).

How much each effect matters depends on the material, the printer and the part.

**Features:**
- Quick fins: select an edge or a face, and the part is stood up with one fin in one step
- Fins generated automatically under a selected face that leans over the bed
- Two connection modes:
  - **separate**: fins are their own object, the tines only touch the part, no extrusion path runs from fin to part
  - **merged**: fins and part become one body, the tines are printed as one path with the part
- Tine height and width in layers and beads, so the design follows the print profile
- Fin height set by the highest tine that finds the face, 1 mm thick up to 100 mm of height and thicker above
- Adjustable tine clearance, so the tines end short of the face and leave fainter marks
- A face split by a groove across it is supported as one: the fin reaches over the groove to the piece beyond it
- One fin centred, two at the ends, two on the corners, one on the left or right corner, or several distributed along the face
- Oval, rectangular or no foot, narrowed automatically so neighbouring feet never touch
- Counter fin on the opposite face, added with the fins or afterwards; the opposite face is found automatically
- Every automatic value can be overridden by hand
- Single fins removed by hand, and the counter fin added or removed, right in the task panel
- Works on STEP and FreeCAD bodies; STL meshes are converted to solids first
- 3MF export with every body as its own object, mesh fineness adjustable; STEP export with exact surfaces
- English and German user interface

## How it works

The fin's inner edge runs parallel to the supported face. Horizontal tines bridge the gap between them and end on the face, or the tine clearance short of it (see [Tine clearance](#tine-clearance)). In the separate mode the slicer prints the fin and the part as two objects: the tine lies against the part and sticks to it, without an extrusion path crossing over.

![Fin with foot and tines under a tilted part](https://raw.githubusercontent.com/Maik-0000FF/FinSnap/main/docs/assets/fin_detail.png)

## Installation

FinSnap needs FreeCAD 1.1 or newer and is tested with the stable release and the weekly builds.

### Addon Manager

FinSnap is not yet listed in the FreeCAD Addon Manager. Until then, the Addon Manager can install it as a custom repository. This works the same on Windows, macOS and Linux and in every package of FreeCAD, finds the right folder by itself, needs no git and brings updates:

1. Open **Edit → Preferences → Addon Manager**.
2. Under **Custom repositories**, add an entry with the repository URL `https://github.com/Maik-0000FF/FinSnap` and the branch `main`. FreeCAD 1.1 needs the branch, since it takes `master` when none is given; newer versions find it themselves.
3. Open **Tools → Addon Manager**, find FinSnap, install it and restart FreeCAD.

### Manual

FinSnap goes into a folder named `FinSnap` in the `Mod` folder of your FreeCAD user data directory. FreeCAD shows that directory in the Python console with `App.getUserAppDataDir()`; create the `Mod` folder in it if it does not exist yet. On a fresh FreeCAD 1.1 it is:

| System | `Mod` folder |
|---|---|
| Windows | `%APPDATA%\FreeCAD\v1-1\Mod` (`$env:APPDATA\FreeCAD\v1-1\Mod` in PowerShell) |
| macOS | `~/Library/Application Support/FreeCAD/v1-1/Mod` |
| Linux, also AppImage | `~/.local/share/FreeCAD/v1-1/Mod` |
| Linux, Flatpak | `~/.var/app/org.freecad.FreeCAD/data/FreeCAD/v1-1/Mod` |
| Linux, Snap | `~/snap/freecad/current/.local/share/FreeCAD/v1-1/Mod` |

The `v1-1` part names the FreeCAD version: `v26-3` for FreeCAD 26.3, `v27-1` for the current weekly builds. A FreeCAD that shares its configuration with an older version keeps using the older folder; a FreeCAD 1.1 that still shares its configuration with 1.0 uses `FreeCAD/Mod` without a version. A FreeCAD that copied the configuration of an older version on its first start has its own copy of FinSnap, which is updated separately.

**Without git:** download the [ZIP of the `main` branch](https://github.com/Maik-0000FF/FinSnap/archive/refs/heads/main.zip), extract it outside the `Mod` folder, for example where it was downloaded, and move the `FinSnap-main` folder that holds `package.xml` into the `Mod` folder as `FinSnap`, so that `Mod/FinSnap/package.xml` exists. Windows can extract it into a second `FinSnap-main` folder; the inner one is then the one to move. Restart FreeCAD.

**With git:** clone the repository into the `Mod` folder and restart FreeCAD. On Linux:

```bash
git clone https://github.com/Maik-0000FF/FinSnap.git ~/.local/share/FreeCAD/v1-1/Mod/FinSnap
```

On Windows in PowerShell:

```powershell
git clone https://github.com/Maik-0000FF/FinSnap.git "$env:APPDATA\FreeCAD\v1-1\Mod\FinSnap"
```

On macOS:

```bash
git clone https://github.com/Maik-0000FF/FinSnap.git ~/Library/Application\ Support/FreeCAD/v1-1/Mod/FinSnap
```

With another package or version, replace the target with the folder from the table, followed by `FinSnap`.

## Commands

The workbench adds one toolbar and a **FinSnap** menu with these commands, in the order they are usually used:

| Command | What it does | How to use it |
|---|---|---|
| ![](https://raw.githubusercontent.com/Maik-0000FF/FinSnap/main/freecad/finsnap/icons/quick_fins.svg)<br>**Quick fins** | Stands the part up and adds one fin in the middle of a face in one step, then opens the task panel to adjust it; a counter fin, where wanted, is added there; Fin placement there spreads more fins along the face. | Select the edge the part is to stand on: it stands on it at 45 degrees (or on the right angle of its faces), and the fins go under the largest face leaning over the bed. Or select the face the fins are to support: the part is turned so that this face leans 45 degrees over the bed, standing on the longest edge of the face that works. To choose what it stands on, select one of the face's edges as well, or, after the face, a chamfer or fillet beside it to rest on. A chamfer or fillet alone, or the two faces beside a fillet, carry the part too, with the fins under the largest leaning face. To put fins under a chamfer itself, select it with one of its edges. The rim or the curved side of a cylinder or tube stands it on its rim, leaning 45 degrees to the front, with one fin under the lowest line of its side, at 0 degrees of the side; a chamfer on the rim and a brim in the slicer give it more hold on the bed. A cylinder split into two halves, as STEP files often bring it, is not stood on its rim yet ([#45](https://github.com/Maik-0000FF/FinSnap/issues/45)). |
| ![](https://raw.githubusercontent.com/Maik-0000FF/FinSnap/main/freecad/finsnap/icons/tilt.svg)<br>**Stand on edge** | Lays one face of the part onto the bed, turns the part about an edge of that face by the tilt angle and sets it back onto the bed, standing on that edge. Inside a Body, the whole Body is turned. Afterwards the view looks along the edge from the side, so the tilt angle shows, and fits the part. | Select the edge and the face of that edge that is to lie on the bed, click the button and enter the angle (45 degrees by default). For an edge already on the bed, the edge alone is enough. So it is for an edge between two flat faces at a right angle: the part stands on it at 45 degrees, without asking for an angle. A chamfer or a fillet selected alone is laid onto the bed and carries the part, without asking for an angle. Two faces selected alone, such as the two beside a fillet, stand the part on what joins them, both equally steep. The rim of a cylinder or tube stands it on that rim, leaning to the front by the angle entered. |
| ![](https://raw.githubusercontent.com/Maik-0000FF/FinSnap/main/freecad/finsnap/icons/lay_flat.svg)<br>**Lay flat again** | Puts a part stood on an edge back as it lay before and shows it isometric. Deleting the last fins of a part does the same. | Select the part or its fins and click the button. If the part has fins, it asks whether to delete them. **No** keeps them, moved along with the part; they keep their last shape and are rebuilt once the part is moved again, by Stand on edge or by hand. While the part lies flat, its fins are left out of an export, and a message names them. |
| ![](https://raw.githubusercontent.com/Maik-0000FF/FinSnap/main/freecad/finsnap/icons/add_fins.svg)<br>**Add fins** | Creates the fins under a face that leans over the bed and opens the task panel with automatic values. | Select the leaning face, click the button, adjust the values in the panel, which shows every change right away, and click **OK** to keep them. Select a second face on the opposite side as well to get a counter fin straight away; it goes under a flat face, not under the side of a cylinder or tube. Double-click the fins in the tree to open the panel again. |
| ![](https://raw.githubusercontent.com/Maik-0000FF/FinSnap/main/freecad/finsnap/icons/counter_fin.svg)<br>**Add counter fin** | Adds a fin on the opposite side of existing fins, against tipping away, as large as the main fin. Fewer counter tines in the panel make it smaller. | Select the fins and click the button: the face leaning the other way is found automatically. To choose it yourself, select a face of the part as well. The counter fin goes under a flat face, not under the side of a cylinder or tube. To remove the counter fin, clear its face in the property view. |
| ![](https://raw.githubusercontent.com/Maik-0000FF/FinSnap/main/freecad/finsnap/icons/mesh_to_solid.svg)<br>**Mesh to solid** | Turns an imported STL mesh into a solid with planar faces, so fins can be added to it. | Import the STL, select the mesh object and click the button. The mesh is hidden, the solid appears next to it. |
| ![](https://raw.githubusercontent.com/Maik-0000FF/FinSnap/main/freecad/finsnap/icons/export_3mf.svg)<br>**Export 3MF** | Writes a 3MF file for the slicer, every body as its own object, see [What the 3MF file contains](#what-the-3mf-file-contains). | Click the button with nothing selected to export all fins with their parts, or select what to export. Selecting the fins alone brings their part along. Set the mesh fineness, then choose the file. |
| ![](https://raw.githubusercontent.com/Maik-0000FF/FinSnap/main/freecad/finsnap/icons/export_step.svg)<br>**Export STEP** | Writes a STEP file with exact surfaces instead of a mesh, every body under its own name, see [STEP instead of 3MF](#step-instead-of-3mf). | Selection as with Export 3MF, then choose the file. In the slicer, split the object into objects. |

Every button shows a tooltip with these explanations when the pointer rests on it.

## Task panel

The task panel opens with **Add fins**, **Quick fins** or a double-click on the fins in the tree. Each section of fields folds away with a click on its header and opens again as it was left; the first time only **Edit fins** is open, and the drawings always show. A folded section holding a value that differs from the standard has its header marked. Under **Edit fins** it changes single fins:

| Button | What it does |
|---|---|
| ![](https://raw.githubusercontent.com/Maik-0000FF/FinSnap/main/freecad/finsnap/icons/remove_fin.svg)<br>**Remove selected fin** | Removes the fin clicked in the 3D view, as the Delete key does. Removing the last fins deletes the fins object. |
| ![](https://raw.githubusercontent.com/Maik-0000FF/FinSnap/main/freecad/finsnap/icons/reset_fins.svg)<br>**Reset fins** | Undoes every change by hand: removed fins come back, moved fins and fin heights of their own are undone. |
| ![](https://raw.githubusercontent.com/Maik-0000FF/FinSnap/main/freecad/finsnap/icons/counter_fin.svg)<br>**Add counter fin** | Adds the counter fin on the face leaning the other way, or on a face of the part selected. The counter fin goes under a flat face, not under the side of a cylinder or tube. |
| ![](https://raw.githubusercontent.com/Maik-0000FF/FinSnap/main/freecad/finsnap/icons/remove_counter.svg)<br>**Remove counter fin** | Removes the counter fin. |

Below the buttons, the list of fins names every fin, one below the other: the main fins from the left, then the counter fins. Pick one to put the arrows on it and select it, so **Remove selected fin** and the Delete key take that fin; a fin behind the part is reached this way without turning the view. The fin with the arrows is marked in the list. Below it, **Place on the face** and **Height** show where that fin stands; type a value to move it, taken once you pause typing or at once with Enter. The double arrows on the fin do the same by dragging, see step 8 under [Usage](#usage). Under the side of a cylinder or tube the fin stays under the lowest line; moving it there turns the part about its axis instead. The field is then **Angle on the part**: where round the side the middle of the tines stands, in degrees from the line at 0 degrees of the side, where the fin is first put; the arrow along the face is an arc round the axis. **Reset fins** and **Cancel** turn the part back.

## Usage

For a quick start, select the edge the part is to stand on, or the face the fins are to support, and click **Quick fins**. The steps below do the same one at a time.

1. Stand the part on an edge: select an edge of the part and the face of that edge that is to lie on the bed, then click **Stand on edge** (45 degrees by default). For an edge between two faces at a right angle, the edge alone is enough. Afterwards the view looks along the edge from the side, so the tilt angle shows. A part with a chamfered or rounded edge stands on it: select the chamfer or fillet alone, or the two faces beside it. Or orient the part yourself.
2. Switch to the **FinSnap** workbench.
3. Select the face that leans over the bed.
4. Click **Add fins**. The task panel opens with automatic values.
5. Enter the slicer settings of your print profile: nozzle diameter, bead width, layer height, first layer height.
6. Adjust any value and confirm with **OK**. Every change shows in the 3D view right away. Fields that have no effect with the current choices are greyed out, and their tooltip says why. A field that differs from the standard for new fins is marked in orange, and the button beside it puts the standard back. **Save as standard** makes the current values the start of every new fin; **Factory settings** goes back to the built-in values. The letters next to the fields point to the side view and top view drawn in the panel.
7. Check the overhangs: faces that lie flatter than 45 degrees over the bed and carry no fins are marked red and listed under the warnings of the fins. Add fins or a counter fin there, or plan support in the slicer. Stand on edge already selects such faces after the tilt.
8. For a counter fin against tipping away, select the fins and click **Add counter fin**. The face leaning the other way is found automatically; select a face of the part as well to choose it yourself. The task panel does the same with **Add counter fin** and **Remove counter fin** under **Edit fins**. To leave out a single fin, for example one over a hole, click it in the 3D view and press Delete, or **Remove selected fin** in the task panel. With the task panel open, two double arrows stand just outside the upright outer edge of the first fin, always of the same size on the screen, as FreeCAD's own draggers; click another fin to put them there. Drag them to move the fin along the face or to change its height; the fin follows. Its height goes from tine to tine, so a tine always ends the fin on top and nothing of it stands out above: near a tine the fin goes there and is green; between tines, also over a recess, it is built as high as the arrow and shown yellow, and let go there it goes to the nearest tine that finds the face; a height typed into the field is taken as it is. An arrow shows no end where the fin cannot go further. Where it cannot stand, it turns red, the other fins stay green; let go there, the fin goes as far as it can, to the corner of the face, next to its neighbour or to the highest it can be. **Place on the face** and **Height** under **Edit fins** show the values; type one to move the fin. The fins are see-through while editing, and tines that find no face are marked red. **Reset fins** undoes every change by hand.
9. Click **Export 3MF**, or **Export STEP**. With nothing selected, all fins of the document are exported together with their parts; otherwise the selection is exported. Selecting the fins alone also brings their part along.

An STL file is imported first, then turned into a solid with **Mesh to solid**. Fins can be added to its planar faces.

**Mesh to solid** does in one step what takes three commands of the Part workbench (Shape From Mesh, Convert to Solid, Refine Shape): the triangles become a solid, and triangles lying in one plane are merged into one face again. What to expect:

- **Planar faces** come back as single faces, and fins on them are the same as on the original part. Tested on a part exported as STL with 0.1 mm and 0.01 mm deviation: the fins under its main face matched those of the original in number, tines and height.
- **Curved surfaces stay faceted**, in many small faces. That is enough for printing, but it is no clean round surface to model on, and fins only go under planar faces or the side of an exact cylinder.
- **Large meshes take time:** about 5 seconds for 6500 triangles; fine meshes with hundreds of thousands of triangles take much longer.
- **The mesh has to be closed.** An open or broken mesh is refused with a message; repair it first, for example with Evaluate and Repair of the Mesh Design workbench.

## Slicing

> [!IMPORTANT]
> When the 3MF file is opened, PrusaSlicer asks:
>
> **Multi-part object detected**
> *"This file contains several objects positioned at multiple heights. Instead of considering them as multiple objects, should the file be loaded as a single object having multiple parts?"*
>
> Answer **No**. With **Yes**, part and fins become parts of one object, and the slicer joins them with a continuous path, which is exactly what the separate mode avoids.

- Keep supports off; the fins are the support.
- The tine height should be a whole number of layers of the print profile, otherwise a tine falls between two layers.
- A gap that makes the tines shorter than about three quarters of a bead leaves them short of the face. FinSnap warns about this.
- In the merged mode, set the seam position of the print profile to rear or random. Otherwise the slicer tends to place the seam where the tines join the part, which shows as a vertical line along the tines.

### STEP instead of 3MF

**Export STEP** is the second way into the slicer. It writes the exact surfaces instead of a triangle mesh, each body under its own name.

PrusaSlicer loads a STEP file as **one object with a part per body**. In that state the slicer joins part and fins as in the merged mode. Split it before slicing: select the object and click **Split to objects** in the top toolbar (right-click menu: **Split → To objects**). Part and fins are then separate objects again, and the result is the same as with 3MF.

Both ways were sliced and compared on a test part with a main fin and a counter fin: the same layers, the tines touching the part in the same layers, the same amount of filament to within 0.01 %. Which one to use:

| | 3MF | STEP |
|---|---|---|
| Geometry | triangle mesh, curved surfaces within the mesh fineness | exact surfaces |
| In PrusaSlicer | separate objects, after answering **No** to the question when opening | one object, **Split to objects** needed |
| Use | the default | when a 3MF does not open as expected, or another program needs exact surfaces |

FinSnap writes every body to STEP as NURBS surfaces. FreeCAD's own STEP export (File → Export) writes faces bounded by offset curves, as a pocket offset around an ellipse creates them, in a way that cannot be read back: the slicer then drops the whole part without a message. As NURBS the same surfaces come back whole.

### Tine clearance

With **Tine clearance** at 0, the tines touch the face, and a print shows faint marks where they stood. A clearance lets them end that far short of the face, measured along the face normal. The fin moves out by the same amount, so the tines keep their length; the **gap** stays the length of the tines across.

```
part face | clearance | gap (tines) | fin
```

Sliced in PrusaSlicer (part tilted 45 degrees, 0.45 mm beads, gap 0.25 mm), measured in the G-code between the edges of the beads:

| Tine clearance | Tine to part in the print path |
|---|---|
| 0 | 0.000 mm (touching) |
| 0.05 mm | 0.071 mm |
| 0.10 mm | 0.142 mm |
| 0.15 mm | 0.212 mm |
| 0.20 mm | 0.283 mm |

The slicer prints the tines exactly with the planned distance. Measured across the layer it is larger than the clearance itself, 1.41 times at 45 degrees, because the face leans.

Whether a tine still holds the part across that distance depends on how far the bead swells while printing, which depends on material, temperature and speed. **Find the value with a test print:**

1. Tilt a small test part, for example a 20 mm cube, add fins with the separate connection and the default gap.
2. Make copies of fins and part with tine clearances of **0, 0.03, 0.05 and 0.08 mm** and print them with the profile you will use.
3. For each one check: does the part stand without wobbling, and does the fin come off without force? Look at the marks the tines left on the face.
4. Take the largest clearance that still holds the part. A bead swells by a few hundredths of a millimetre while printing; once the clearance is wider than that, the tine no longer reaches the face and the fin stops holding. Where that limit lies is not measured yet, which is what the test print is for.
5. Save it with **Save as standard** in the panel, so new fins start with it.

## What the 3MF file contains

**Export 3MF** writes a plain 3MF file (core specification, no slicer project):

- **One object per body**, named after it: the part as `<part>`, its fins as `<part>_fins`. In the merged mode, part and fins are one object.
- **Triangle meshes in millimetres.** Planar faces are exact; curved surfaces follow the mesh fineness chosen in the export dialog (surface deviation, default 0.01 mm, and angular deviation, default 1 degree).
- **Metadata** `Application` with the name and version that wrote the file, `FinSnap <version>`, and `CreationDate` with the date of the export.
- **No print settings, supports or colours.** The slicer opens the file with its own print profile.

The file is a ZIP archive; the content above sits in `3D/3dmodel.model`. A slicer that saves the file again as its own project may replace the metadata with its own.

## Parameters

| Group | Parameter | Automatic | Meaning |
|---|---|---|---|
| Slicer | Nozzle diameter, bead width, layer height, first layer height | | Values of the print profile |
| Connection | Connection | separate | separate or merged |
| | Gap | 0.25 mm | Length of the tines across, between fin and the end of the tines, along the face normal |
| | Tine clearance | 0 mm = touching | Distance from the end of the tines to the face, along the face normal; the fin moves out by as much. See [Tine clearance](#tine-clearance) |
| Tines | Tine spacing | 5 mm | Vertical distance between tines, at least the tine height plus one layer |
| | Tine first | 0 = on the top of the foot | Height of the lowest tine |
| | Tine layers | 1 | Tine height in layers |
| | Tine width beads | 1 | Tine width in beads |
| | Tine count | 0 = as many as fit | Tines per fin |
| Fin | Fin thickness | 0 = 1 mm up to 100 mm of height, 1 mm per 100 mm above, at least 2 beads | Wall thickness |
| | Fin height | 0 = top of the highest tine that finds the face | Height of the fin. Tines over a recess are left out, and the fin ends at the highest tine left. A lower value leaves out the tines above it; at most just below the top of the face |
| | Top width | 2 mm | Width of the flat top of the fin, instead of a tip |
| Placement | Fin placement | auto | auto, centre, ends, corners, left corner, right corner, distributed. Corners puts a fin on each end of the face: each tine lies whole on the face and ends flush with its end, so the tine marks merge with the edges. The fin itself reaches a little past the end. Left corner and right corner put one such fin on that end only, left and right as seen from outside, looking at the face |
| | Fin count | 3 | Fins for distributed placement |
| | End inset | 0.5 mm | Distance of the outer fins from the face ends |
| | Face length per fin | 50 mm | Automatic placement adds one fin per this length |
| Foot | Foot shape | oval | oval, rectangle, none |
| | Foot thickness | 1 mm | Rounded to whole layers |
| | Foot overhang | 0 mm | Reach past the straight outer end of the fin |
| | Foot width ratio | 0.2 | Foot width as a share of its length |
| | Foot half width | 0 = from ratio | Half width of the foot |
| Counter fin | Counter tine count | 0 = as many as the main fin | Tines of the counter fin; it only has to stop the part from tipping over, so it may be smaller |

## Requirements

- FreeCAD 1.1 or newer, tested with the stable release and the weekly builds

## Development

Tests and tools live in the package, under `freecad/finsnap/tests/` and `freecad/finsnap/tools/`. The tests run in FreeCAD, with the checkout installed as described under [Manual](#manual), from the repository root:

```bash
freecad --console freecad/finsnap/tests/test_cube.py
freecad --console freecad/finsnap/tests/test_feature.py
QT_QPA_PLATFORM=offscreen freecad freecad/finsnap/tests/test_gui.py
python3 -m freecad.finsnap.tests.test_version
```

The CI checks every push: lint with ruff, a security scan with Bandit, licence information with REUSE, complete translations, and the tests against the stable FreeCAD release.

`python3 -m freecad.finsnap.tools.check_gcode <file.gcode>` checks a sliced G-code file: no path may run from a fin into its part, and every tine has to reach the part.

## Contributing

Questions, test results and feedback go to the [FreeCAD forum thread](https://forum.freecad.org/viewtopic.php?t=108188), bug reports and ideas to [issues](https://github.com/Maik-0000FF/FinSnap/issues). See the [Contributing guide](CONTRIBUTING.md) for translations and code changes.

## Support

> If you find FinSnap useful, you can support its development:
>
> <a href="https://github.com/sponsors/Maik-0000FF">
>   <img src="https://img.shields.io/badge/Sponsors-Support_this_project-ea4aaa?style=for-the-badge&logo=github" alt="GitHub Sponsors">
> </a>
> &nbsp;
> <a href="https://ko-fi.com/maik0000ff">
>   <img src="https://img.shields.io/badge/Ko--fi-Buy_me_a_coffee-ff5e5b?style=for-the-badge&logo=ko-fi&logoColor=white" alt="Ko-fi">
> </a>
>
> A star also helps, it makes this project easier to discover.

## License

GPL-3.0-or-later

## Author

Created by [Maik-0000FF](https://github.com/Maik-0000FF)
