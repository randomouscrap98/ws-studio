# GB Studio CLI export

`run.sh` builds GB Studio's command-line compiler (if it is not already
built), runs its `export` command on the `gbs2` template, and writes the
generated GBDK/GBVM project to `wsc/build/export/`.

The output is about 1.9 MB in 942 files (~4.8 MB on disk), so it is left in
the gitignored `wsc/build/` directory rather than committed.

## Run

```sh
wsc/export/run.sh
```

Options:

- First argument: destination directory (default `wsc/build/export`).
- `TEMPLATE=/path/to/project.gbsproj`: export a different project. The
  default is `appData/templates/gbs2/project.gbsproj`, because the `blank`
  template has no scenes. `gbdiff` uses this to export a patched project
  variant into its own directory; the normal export is not touched.

The script prints the number of exported files and their total byte size at
the end, for example:

```
exported files: 942 (1902920 bytes)
```

Re-running it deletes and recreates the destination, so the result comes from
a clean export each time. Intermediate data goes to `wsc/build/cli-tmp/`.

## Build prerequisites

- Node 24 (the repo requires `>=24.16.0 <25`; tested with 24.22.3).
- Yarn 1.22.22 on `PATH`.
- Network access for the first dependency install.

Dependencies are installed into the repo's gitignored `node_modules/` only
when it is missing or incomplete:

```sh
SKIP_YARN_COREPACK_CHECK=1 YARN_IGNORE_PATH=1 \
ELECTRON_SKIP_BINARY_DOWNLOAD=1 \
yarn install --pure-lockfile --ignore-scripts --non-interactive
```

`SKIP_YARN_COREPACK_CHECK` works around `package.json` declaring Yarn 4
while the system package is Yarn 1; `YARN_IGNORE_PATH` skips the committed
`.yarnrc` path to a Yarn 1 binary that is not in the repository.
`--ignore-scripts` avoids Electron's postinstall binary download.

The CLI is bundled with:

```sh
NO_TYPE_CHECKING=1 npm run make:cli
```

`NO_TYPE_CHECKING=1` is the same setting the repository's `start:cli`
script uses. With type checking on, the current `@types/node`/TypeScript 6
combination reports one error in `src/lib/project/loadScriptEventHandlers.ts`
(an `undefined` read-file encoding); webpack still emits the bundles and the
CLI runs. The bundled files are `out/cli/gb-studio-cli.js` (about 4.9 MB)
and `out/cli/buildWorker.js` (about 4.8 MB).

## Export environment

`export` does not call GBDK or `make`; it only compiles project assets to C
and asm with JavaScript. The exported `Makefile.common` still points at GBDK if
you later run `make`, but `buildTools/linux-x64` in this checkout contains
only `tools_version` (no `gbdk/`), so a ROM build from this export would need
the GB Studio GBDK build tools.

The CLI imports Electron's `app` while initialising localisation. With an
ignored Electron postinstall there is no `node_modules/electron/path.txt`,
and `electron/index.js` downloads the full Electron binary on first use.
`run.sh` sets `ELECTRON_OVERRIDE_DIST_PATH` to the normal install path so
this download is skipped; no Electron process is started.

The output tree contains:

- `src/core/`: the GBVM engine (C plus ten hand-written `.s` files)
- `src/states/`: top-down/platform/shmup/point-and-click/logo state C
- `src/data/`: generated scene, background, palette, sprite, actor,
  trigger and script data (C and asm bytecode)
- `src/wsc/`: the WSC HAL sources already present in the GBVM engine
- `include/`: engine headers, `vm.i`, `macro.i`, generated headers
- `lib/`: `hUGEDriver.lib`, `gbt_player.lib`
- `Makefile`, `Makefile.common`, `Makefile.build`, `utils/`, `obj/`,
  `build/rom/` (empty build directories)

Generated `src/data/*.s` files are sdas-syntax bytecode: `vm.i`/`macro.i`
expansions, `.db`/`.dw`/`.asciz`, labels and symbol references. They contain
no raw CPU instructions. The engine's `src/core/gb/*.s` files are ordinary
hand-written Z80/GB assembly.

## WSC product ROMs

The CLI also has `make:wsc`, which runs the same export and then the WSC
product build (`wsc/product/Makefile`, via `wsc/tools/build_product.sh`):

```sh
node out/cli/gb-studio-cli.js make:wsc PROJECT.gbsproj OUT.wsc
```

`wsc/export/run.sh` and `wsc/tools/build_product.sh` share
`wsc/tools/ensure-cli.sh` for the dependency install/CLI bundle step. The
`make:wsc` command checks `WONDERFUL_TOOLCHAIN` (default `/opt/wonderful`) and
`make` before starting the export. It runs the s2c and d2c TypeScript ports
in-process, so the default path does not use `python3`.
