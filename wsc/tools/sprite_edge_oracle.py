#!/usr/bin/env python3
"""Reference frame for the C17 sprite-edge test.

The scene is Sample Town with script_c17_edge as its init script.  The camera
moves to source (32, 16) px, then:

  * the Cat (actor 1) is placed at (20, 48) px, so its 8x8 entries land at
    screen x -4 and 4: the left entry is partly on screen;
  * the Duck (actor 4) is placed at (296, 80) px, 40 px past the right edge,
    so both of its entries are culled;
  * VM_SET_SPRITE_MODE selects 8x8.

ref_render applies the same HAL cull and 8-bit hardware coordinate rule, so
the expected frame contains the partly visible Cat entry and no Duck entry.
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
CAT_INDEX = 0              # scene_sample_town_actors[0] = actor 1
CAT_X = 20                 # px, screen -12: entries at -4 and 4
CAT_Y = 48
DUCK_INDEX = 3             # scene_sample_town_actors[3] = actor 4
DUCK_X = 296               # px, screen 264: 40 px past the right edge
DUCK_Y = 80


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
            # The engine can activate actors while the camera is still at its
            # boot position (source x 0); it does not reactivate them later.
            "activation_source_x": 0,
            "activation_source_y": SOURCE_Y,
            "player_x": PLAYER_X,
            "player_y": PLAYER_Y,
            "camera_x": CAMERA_X,
            "camera_y": CAMERA_Y,
            "sprite_mode": 8,
            "actor_overrides": {
                # The actors are moved after the camera settles; activation
                # used their scene positions (Cat 32,48; Duck 136,152 px).
                CAT_INDEX: {
                    "x": CAT_X << 5, "y": CAT_Y << 5, "frame": 0,
                    "activation_x": 32 << 5, "activation_y": 48 << 5,
                },
                DUCK_INDEX: {
                    "x": DUCK_X << 5, "y": DUCK_Y << 5, "frame": 0,
                    "activation_x": 136 << 5, "activation_y": 152 << 5,
                },
            },
        }
        _scene, _background, _actors, scenario, _expected = \
            boot_oracle.build_scene(
                export, args.project_dir, SCENE, PLAYER_X, PLAYER_Y,
                start_dir, 90, effects=effects, final=final)
        ref_render.render_scenario(scenario, args.out)
    except (boot_oracle.OracleError, OSError, KeyError, ValueError) as exc:
        print("sprite_edge_oracle: {}".format(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
