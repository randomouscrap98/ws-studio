#!/usr/bin/env python3
"""Reference frame for the C13 script-handler test.

The test scene is Sample Town with script_c13_test as its init script.  The
frame is rendered from the same exported C data the ROM loads, using the
values written in wsc/gamerom/src/script_c13_test.s:

  * actor 4 (Duck) starts at (96, 80) px and VM_ACTOR_MOVE_TO takes it to
    (128, 80) px; direction LEFT, animation frame 1, animation paused.
  * actor 1 (Cat) is deactivated and reactivated, so it is back in the active
    list at its scene position (32, 48) px.
  * VM_SET_SPRITE_MODE selects 8x8, so every metasprite entry is one tile.
  * VM_CAMERA_MOVE_TO ends at subpixels (4608, 2816) = (144, 88) px.  The WSC
    scroll is camera_px - (screen/2), i.e. (32, 16) px.

The player is at the test build's start position (48, 80) px.  The room is
56x56 tiles, so the camera source is not centred and no extra actors are
activated by the horizontal camera move.
"""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import boot_oracle  # noqa: E402
import ref_render  # noqa: E402

SCENE = "scene_sample_town"
PLAYER_X = 48              # px, BOOT_START_X = 1536
PLAYER_Y = 80              # px, BOOT_START_Y = 2560
SOURCE_X = 32              # px, camera 144 - 224/2
SOURCE_Y = 16              # px, camera 88 - 144/2
CAMERA_X = 4608            # subpx, 144 px
CAMERA_Y = 2816            # subpx, 88 px
DUCK_INDEX = 3             # scene_sample_town_actors[3] = actor 4 in scripts
DUCK_X = 4096              # subpx, 128 px
DUCK_Y = 2560              # subpx, 80 px
DUCK_FRAME = 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--export", default=str(boot_oracle.DEFAULT_EXPORT))
    parser.add_argument("--project-dir", default=str(boot_oracle.DEFAULT_PROJECT))
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    try:
        export = boot_oracle.ExportData(args.export)
        start_dir = boot_oracle.parse_start_dir(args.export)
        effects = {
            "hide_player": False,
            "deactivated_actors": set(),
            "sprite_mode": 8,
        }
        final = {
            "source_x": SOURCE_X,
            "source_y": SOURCE_Y,
            "player_x": PLAYER_X,
            "player_y": PLAYER_Y,
            "camera_x": CAMERA_X,
            "camera_y": CAMERA_Y,
            "sprite_mode": 8,
            "actor_overrides": {
                DUCK_INDEX: {"x": DUCK_X, "y": DUCK_Y, "frame": DUCK_FRAME},
            },
        }
        _scene, _background, _actors, scenario, _expected = \
            boot_oracle.build_scene(
                export, args.project_dir, SCENE, PLAYER_X, PLAYER_Y,
                start_dir, 60, effects=effects, final=final)
        ref_render.render_scenario(scenario, args.out)
    except (boot_oracle.OracleError, OSError, KeyError, ValueError) as exc:
        print("c13_oracle: {}".format(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
