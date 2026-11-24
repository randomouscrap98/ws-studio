# WSC product ROM

`Makefile` builds a WonderSwan Color image from a GB Studio export. It links
the portable engine and the WSC HAL through `../engine.mk`, but no test
scenes, test scripts or boot table: the generated bootstrap's project start
scene and position are used unchanged.

The usual entry point is the CLI command, which exports the project first:

```sh
gb-studio-cli make:wsc PROJECT.gbsproj OUT.wsc
```

or the scripted wrapper:

```sh
wsc/tools/build_product.sh PROJECT.gbsproj OUT.wsc [STATE_DIR]
```

`STATE_DIR` (default: a per-project directory under `wsc/build/product/`)
holds `build/` and `gen/`; the CLI keeps the exporter's own temporary tree
separate.

`make -C wsc product PROJECT=... PRODUCT_ROM=... PRODUCT_STATE=...` runs the
wrapper. The build needs the Wonderful toolchain (`WONDERFUL_TOOLCHAIN`,
default `/opt/wonderful`), `python3` and `make`; the CLI checks all three and
reports a clear error if one is missing.

If a project does not fit the 512 KiB ROM or the IRAM regions, the link or
the Wonderful ROM builder fails. The Makefile adds a short message around
those failures; the allocator/linker error above it has the details.
