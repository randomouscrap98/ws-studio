#!/usr/bin/env python3
"""Horizontal -> vertical -> horizontal switch check.

Boots the town scene with the C35 script (boot id 20), captures a frame in
each of the three phases and checks it against a reference render in the
orientation active at that tick.  It also compares the world state before and
after the switches and reports how many vblank frames each switch took.
"""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WSC = HERE.parent
ROOT = WSC.parent
sys.path.insert(0, str(HERE))

import boot_oracle as boot  # noqa: E402
import gbdiff  # noqa: E402
import ref_render  # noqa: E402
import vertical_visual as vv  # noqa: E402

DEFAULT_EXPORT = WSC / "build" / "export"
DEFAULT_PROJECT = ROOT / "appData" / "templates" / "gbs2"
ELF = WSC / "gamerom" / "build" / "gamerom.elf"

PHASES = ((50, 1, "horizontal"), (90, 2, "vertical"), (150, 3, "horizontal"))


class SwitchError(Exception):
    pass


def world_state(ram, symbols, layout, actor_count):
    state = []
    for name in ("camera_x", "camera_y", "scroll_x", "scroll_y"):
        state.append((name, vv.read_u16(ram, symbols[name])))
    for index in range(actor_count + 1):
        base = symbols["actors"] + index * layout["size"]
        state.append(("actor{}".format(index),
                      vv.read_u16(ram, base + layout["x"]),
                      vv.read_u16(ram, base + layout["y"]),
                      vv.read_u8(ram, base + layout["flags"])))
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--export", default=str(DEFAULT_EXPORT))
    parser.add_argument("--project-dir", default=str(DEFAULT_PROJECT))
    parser.add_argument("--workdir", default=str(vv.WORKDIR / "switch"))
    args = parser.parse_args(argv)

    try:
        export = boot.ExportData(args.export)
        out_dir = Path(args.workdir)
        out_dir.mkdir(parents=True, exist_ok=True)
        layout = gbdiff.wsc_layout(out_dir)

        scene = "scene_sample_town"
        scene_meta = export.scene(scene)
        symbols = {
            name: boot.elf_symbol_address(ELF, name)
            for name in ("scroll_x", "scroll_y", "scroll_center_x",
                         "scroll_center_y", "camera_x", "camera_y", "actors",
                         "actors_len", "c35_phase",
                         "hal_orientation_switch_frames")
        }

        states = {}
        switch_frames = {}
        failures = 0
        for tick, expected_phase, orientation in PHASES:
            tag = "switch-t{}".format(tick)
            raw, ram = vv.run_wsrun(20, "horizontal", tick, out_dir, tag)
            phase = vv.read_u8(ram, symbols["c35_phase"])
            if phase != expected_phase:
                raise SwitchError(
                    "tick {}: phase {} (expected {})".format(
                        tick, phase, expected_phase))
            states[tick] = world_state(ram, symbols, layout,
                                       scene_meta["n_actors"])
            switch_frames[tick] = vv.read_u16(
                ram, symbols["hal_orientation_switch_frames"])

            scenario = vv.build_reference(
                export, args.project_dir, scene, 112, 328, orientation,
                ram, layout, tick, init_effects={}, timer_runs=0)
            reference_path = out_dir / (tag + ".ref")
            ref_render.render_scenario(scenario, reference_path)
            reference = reference_path.read_bytes()
            if orientation == "vertical":
                logical = vv.unrotate_vertical(raw)
                width, height = vv.LOGICAL_W, vv.LOGICAL_H
            else:
                logical = raw
                width, height = vv.PHYSICAL_W, vv.PHYSICAL_H
            try:
                vv.compare_frames(logical, reference, width, tick)
                print("tick {}: phase {} {} {}x{} exact match".format(
                    tick, phase, orientation, width, height))
            except vv.VisualError as exc:
                failures += 1
                print("tick {}: phase {}: {}".format(tick, phase, exc))

        # Compare against the same tick of a control run whose script only
        # idles: the town's actor update scripts evolve over time, so this
        # isolates any state change caused by the switches themselves.
        _, control_ram = vv.run_wsrun(21, "horizontal", 150, out_dir,
                                      "switch-control-t150")
        control = world_state(control_ram, symbols, layout,
                              scene_meta["n_actors"])
        if states[150] != control:
            failures += 1
            print("switches changed world state at tick 150")
            for switched, idle in zip(states[150], control):
                if switched != idle:
                    print("  switched {} != idle {}".format(switched, idle))
        else:
            print("world state at tick 150 matches the no-switch control "
                  "({} actors + camera/scroll)".format(
                      scene_meta["n_actors"]))

        print("switch time: horizontal -> vertical {} frames, "
              "vertical -> horizontal {} frames".format(
                  switch_frames[90], switch_frames[150]))

        if failures:
            print("FAIL vertical-switch: {} check(s) failed".format(failures))
            return 1
        print("PASS vertical-switch")
        return 0
    except (SwitchError, vv.VisualError, boot.OracleError, OSError,
            KeyError, ValueError) as exc:
        print("vertical_switch: {}".format(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
