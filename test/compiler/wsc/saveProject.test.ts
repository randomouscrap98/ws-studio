import fs from "fs-extra";
import os from "os";
import Path from "path";
import loadProject from "../../../src/lib/project/loadProjectData";
import {
  buildResourceExportBuffer,
  encodeResource,
} from "../../../src/shared/lib/resources/save";
import type { CompressedSceneResourceWithChildren } from "../../../src/shared/lib/resources/types";

const removeResourceFiles = (root: string) => {
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    const path = Path.join(root, entry.name);
    if (entry.isDirectory()) {
      removeResourceFiles(path);
    } else if (entry.name.endsWith(".gbsres")) {
      fs.removeSync(path);
    }
  }
};

const writeFiles = (root: string, files: { path: string; data: string }[]) => {
  for (const file of files) {
    const target = Path.join(root, file.path);
    fs.ensureDirSync(Path.dirname(target));
    fs.writeFileSync(target, file.data);
  }
};

test("a project with an unsupported event loads and saves byte-identically", async () => {
  const template = Path.resolve(
    __dirname,
    "../../../appData/templates/blank",
  );
  const root = fs.mkdtempSync(Path.join(os.tmpdir(), "wsc-save-test-"));
  try {
    const source = await loadProject(Path.join(template, "project.gbsproj"));
    const scene: CompressedSceneResourceWithChildren = {
      _resourceType: "scene",
      _index: 0,
      id: "11111111-1111-1111-1111-111111111111",
      type: "TOPDOWN",
      name: "Hidden",
      symbol: "scene_hidden",
      x: 0,
      y: 0,
      width: 20,
      height: 18,
      backgroundId: source.resources.backgrounds[0].id,
      tilesetId: "",
      colorModeOverride: "none",
      paletteIds: [],
      spritePaletteIds: [],
      autoFadeSpeed: 1,
      script: [
        {
          id: "hidden-print",
          command: "EVENT_PRINT",
          args: { source: "background", margin: 2 },
        },
      ],
      playerHit1Script: [],
      playerHit2Script: [],
      playerHit3Script: [],
      collisions: "",
      actors: [],
      triggers: [],
    };
    source.resources.scenes = [scene];
    source.resources.settings.startSceneId = scene.id;

    fs.copySync(template, root);
    removeResourceFiles(root);
    fs.removeSync(Path.join(root, "project"));
    const firstFiles = buildResourceExportBuffer(source.resources);
    writeFiles(root, firstFiles);
    fs.writeFileSync(
      Path.join(root, "project.gbsproj"),
      encodeResource("project", source.resources.metadata),
    );

    const loaded = await loadProject(Path.join(root, "project.gbsproj"));
    expect(loaded.resources.scenes).toHaveLength(1);
    expect(loaded.resources.scenes[0].script[0].command).toBe("EVENT_PRINT");

    const secondFiles = buildResourceExportBuffer(loaded.resources);
    for (const file of secondFiles.filter((file) =>
      file.path.startsWith("project/"),
    )) {
      expect(fs.readFileSync(Path.join(root, file.path), "utf8")).toBe(
        file.data,
      );
    }
    expect(
      fs.readFileSync(Path.join(root, "project.gbsproj"), "utf8"),
    ).toBe(encodeResource("project", loaded.resources.metadata));
  } finally {
    fs.removeSync(root);
  }
});
