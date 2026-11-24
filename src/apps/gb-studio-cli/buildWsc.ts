import crypto from "crypto";
import fs from "fs-extra";
import Path from "path";
import { spawnSync } from "child_process";

const DEFAULT_TOOLCHAIN = "/opt/wonderful";

const fail = (message: string): never => {
  throw new Error(message);
};

const findRepoRoot = (start: string): string => {
  let dir = Path.resolve(start);
  for (;;) {
    if (fs.existsSync(Path.join(dir, "wsc", "product", "Makefile"))) {
      return dir;
    }
    const parent = Path.dirname(dir);
    if (parent === dir) {
      return fail(
        "cannot find wsc/product/Makefile next to the CLI; " +
          "make:wsc needs the ws-studio source tree",
      );
    }
    dir = parent;
  }
};

const runTool = (command: string, args: string[]): string | undefined => {
  const result = spawnSync(command, args, {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  if (result.error || result.status !== 0) {
    return undefined;
  }
  return (result.stdout || "").trim();
};

const sanitize = (name: string): string =>
  name.replace(/[^A-Za-z0-9_.-]+/g, "_") || "project";

export type WscBuildOptions = {
  /** Ejected GBDK/GBVM project produced by the existing export step. */
  exportDir: string;
  /** Directory containing the project's .gbsproj file. */
  projectRoot: string;
  /** The .gbsproj file, used only for a stable build directory name. */
  projectFile: string;
  /** Destination .wsc path. */
  destination: string;
};

/** Check the tools make:wsc needs before doing an expensive export. */
export const assertWscPrerequisites = () => {
  const toolchain = Path.resolve(
    process.env.WONDERFUL_TOOLCHAIN || DEFAULT_TOOLCHAIN,
  );
  const required = [
    Path.join(toolchain, "target", "wswan", "medium", "makedefs.mk"),
    Path.join(toolchain, "bin", "wf-wswantool"),
    Path.join(
      toolchain,
      "toolchain",
      "gcc-ia16-elf",
      "bin",
      "ia16-elf-gcc",
    ),
  ];
  const missing = required.filter((path) => !fs.existsSync(path));
  if (missing.length > 0) {
    fail(
      `WonderSwan toolchain not found (WONDERFUL_TOOLCHAIN=${toolchain}); ` +
        `missing ${missing[0]}. Set WONDERFUL_TOOLCHAIN to the ` +
        "Wonderful install (default /opt/wonderful).",
    );
  }
  if (runTool("python3", ["--version"]) === undefined) {
    fail("python3 is required for make:wsc but was not found in PATH");
  }
  if (runTool("make", ["--version"]) === undefined) {
    fail("make is required for make:wsc but was not found in PATH");
  }
  return toolchain;
};

/** Build an exported project into a WSC ROM with the shared engine makefile. */
export const buildWsc = async ({
  exportDir,
  projectRoot,
  projectFile,
  destination,
}: WscBuildOptions) => {
  const toolchain = assertWscPrerequisites();
  const repoRoot = findRepoRoot(__dirname);
  const productDir = Path.join(repoRoot, "wsc", "product");

  if (!fs.existsSync(Path.join(exportDir, "src", "data"))) {
    return fail(`export did not produce ${Path.join(exportDir, "src", "data")}`);
  }

  const digest = crypto
    .createHash("sha1")
    .update(Path.resolve(projectFile))
    .digest("hex")
    .slice(0, 8);
  const stateDir = Path.resolve(
    process.env.WSC_PRODUCT_STATE ||
      Path.join(
        repoRoot,
        "wsc",
        "build",
        "product",
        `${sanitize(Path.basename(projectRoot))}-${digest}`,
      ),
  );
  const buildDir = Path.join(stateDir, "build");
  const genDir = Path.join(stateDir, "gen");
  const romPath = Path.join(stateDir, "product.wsc");
  await fs.ensureDir(stateDir);

  const result = spawnSync(
    "make",
    [
      "-C",
      productDir,
      `EXPORT_DIR=${exportDir}`,
      `PROJECT_DIR=${projectRoot}`,
      `BUILDDIR=${buildDir}`,
      `GEN_DIR=${genDir}`,
      `ROM=${romPath}`,
      "all",
    ],
    {
      stdio: "inherit",
      env: { ...process.env, WONDERFUL_TOOLCHAIN: toolchain },
    },
  );
  if (result.error) {
    return fail(`cannot run make: ${result.error.message}`);
  }
  if (result.status !== 0) {
    return fail(
      `WSC build failed (make exited with status ${result.status ?? 1})`,
    );
  }
  if (!fs.existsSync(romPath)) {
    return fail(`WSC build did not produce ${romPath}`);
  }
  const stat = await fs.stat(romPath);
  if (stat.size === 0) {
    return fail(`WSC build produced an empty ROM at ${romPath}`);
  }
  await fs.ensureDir(Path.dirname(Path.resolve(destination)));
  await fs.copy(romPath, destination);
  console.log(
    `WSC ROM written to ${destination} (${stat.size} bytes, ` +
      `build ${romPath})`,
  );
};
