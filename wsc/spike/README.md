# C04s far-data spike

Throwaway research ROMs for the WonderSwan Color port. Each subdirectory is a
normal Wonderful `wswan/medium` project; run everything with:

```sh
wsc/spike/run.sh
```

The script rebuilds every ROM, runs it in `wsrun`, reads the result variables
from the 64 KiB IRAM dump using the ELF symbols, and prints one `PASS`/`FAIL`
line per claim. Build logs, RAM dumps and the far-walk disassembly are written
to `wsc/build/spike/`.

| Project | Claim |
| --- | --- |
| `farwalk` | `__far` pointers as locals, struct members, function parameters and arrays; increment/deref codegen |
| `placement` | two 40 KiB far sections, their 64 KiB segments, and a table of far pointers |
| `reach512` | all 512 KiB of a 512 KiB ROM reachable through the default linear window |
| `reach2m` | 768 KiB (the last 12 × 64 KiB banks) reachable on a 2 MiB ROM |
| `limits` | 96 KiB linker section across a segment boundary; pointer wrap vs. normalisation; C object size limit |
| `dsclobber` | compiler keeps the far segment in `%ds`, so a global store after a far read in non-returning `main()` is lost |

The source files are evidence, not engine code. `src/data.s` in `placement`,
`reach512`, `reach2m` and `limits` exists because the compiler rejects C
objects larger than 32767 bytes; the linker itself handles larger sections.
