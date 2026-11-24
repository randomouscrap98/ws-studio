#!/usr/bin/env node
/*
 * Thin command-line wrapper for the TypeScript d2c port.
 *
 * Node 24 strips TypeScript types natively, so no build step or transpiler is
 * needed. The port deliberately lives in one file with no relative imports;
 * keep it to erasable TypeScript syntax (no enums, namespaces or parameter
 * properties) so this loader keeps working.
 */
"use strict";

const path = require("node:path");

const d2c = require(
  path.join(__dirname, "..", "..", "src", "lib", "compiler", "wsc", "d2c.ts"),
);

process.exitCode = d2c.main(process.argv.slice(2));
