#!/usr/bin/env sh
# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

# Render the demo GIF of the README, docs/assets/demo.gif, from a part in a
# FreeCAD document, which is opened and never saved:
#   freecad/finsnap/tools/make_demo.sh <document.FCStd> <part name> <FaceN>
# FaceN is the face Quick fins stands the part on. Needs FreeCAD (FREECAD
# overrides the command, for example with freecad-weekly), xvfb-run and ffmpeg.
# FreeCAD runs on a virtual screen, in English, with a user data directory of
# its own holding only this checkout, so nothing shows and none of your
# settings change.
set -eu

[ $# -eq 3 ] || { echo "usage: $0 <document.FCStd> <part name> <FaceN>" >&2; exit 64; }
TOOLS=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$TOOLS/../../.." && pwd)
GIF="$ROOT/docs/assets/demo.gif"
# Frames per second, and the virtual screen, larger than the frames.
RATE=5
SCREEN=1600x1000x24

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/user/Mod"
ln -s "$ROOT" "$WORK/user/Mod/FinSnap"

env -u WAYLAND_DISPLAY -u DISPLAY LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 LANGUAGE=en \
    QT_QPA_PLATFORM=xcb FREECAD_QT_QPA_PLATFORM=xcb FREECAD_USER_DATA="$WORK/user" \
    DEMO_MODEL="$1" DEMO_PART="$2" DEMO_FACE="$3" DEMO_FRAMES="$WORK/frames" \
    xvfb-run -a -s "-screen 0 $SCREEN" "${FREECAD:-freecad}" "$TOOLS/make_demo.py"

# A palette of the whole demo first, then the GIF with it; no metadata.
ffmpeg -loglevel error -framerate "$RATE" -i "$WORK/frames/%04d.png" \
    -vf "palettegen=stats_mode=diff:max_colors=256" -y "$WORK/palette.png"
ffmpeg -loglevel error -framerate "$RATE" -i "$WORK/frames/%04d.png" -i "$WORK/palette.png" \
    -lavfi "paletteuse=dither=sierra2_4a" -map_metadata -1 -fflags +bitexact -y "$GIF"
echo "written $GIF"
