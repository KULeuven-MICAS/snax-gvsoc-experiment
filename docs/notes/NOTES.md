# SNAX-GVSoC notes

Working notes for the SNAX-GVSoC exploration (X1, D115 in snax-forge).
One entry per step: what was run, what came out, what was learned.

## Pins

| What | Commit | Date |
|---|---|---|
| `gvsoc/gvsoc` (submodule `gvsoc/`) | `93cedc4cb2970a28ff38aef4393d8d69eae503a4` | 2026-09-25 |
| `pulp-platform/snitch_cluster` (submodule `snitch_cluster/`) | `4652c6b05886757c5cbe3dfe77c196dcd71e08e7` | 2024-08-02 |

Toolchains, all prebuilt downloads (see `container/Dockerfile`):

| Tool | Version | Used for |
|---|---|---|
| RISC-V GCC | 14.2.0, riscv-gnu-toolchain release 2025.01.17 | GVSoC tutorial programs (rv64) |
| Snitch LLVM | 0.12.0 (clang 12.0.1), pulp-platform/llvm-project | snitch_cluster runtime and programs (rv32) |
| Bender | 0.27.1 | snitch_cluster header generation |

### Why this snitch_cluster commit

- GVSoC's `make snitch_cluster` clones a `gvsoc-ci` branch that no longer
  exists in pulp-platform/snitch_cluster, so there is no official pin.
- GVSoC's cluster peripheral register file
  (`pulp/pulp/snitch/snitch_cluster/snitch_cluster_peripheral_reg.hjson`) is
  byte-identical to snitch_cluster from `a5af779` (2023-09-15) up to, not
  including, `96e34a2` (2024-08-09). `4652c6b` is the last commit in that range.
- snitch_cluster `c7eb9c2` (2025-01-28, native bootrom) moves the peripherals
  up by 0x1000 and `CL_CLINT_SET` from 0x180 to 0x1a0. Programs built from
  that commit or later fail on GVSoC with
  `Accessing invalid register (offset: 0x11a0 ...)`. Reproduced with `c4861da`.

## Layout

```
snax-gvsoc/
  gvsoc/            submodule, pinned
  snitch_cluster/   submodule, pinned
  container/        Dockerfile and requirements.txt
  snax/             module root for the SNAX components (added when needed)
  tutorials/        working copies of the GVSoC tutorials (added in GVS1)
  sw/               C programs (GVS3)
  build/            GVSoC build, install and run output; not tracked
  docs/             notes (this file), plans, one page per tutorial in
                    docs/tutorials/, and the API and tool reference in
                    docs/reference/
```

SNAX models stay outside the GVSoC tree. GVSoC picks up an external module
root with `make build MODULES=/abs/path` and finds its generators with
`gvrun --target-dir`.

## Container

- Image: `ghcr.io/kuleuven-micas/snax-gvsoc:gvs1`, built from `container/`.
- It holds compilers, Python packages and toolchains only. The repo is
  mounted at `/work`; `GVSOC_WORKDIR=/work/build` sends all GVSoC output to
  `build/`.

Build and push (local machine, Docker):

    docker build -t ghcr.io/kuleuven-micas/snax-gvsoc:gvs1 container
    docker push ghcr.io/kuleuven-micas/snax-gvsoc:gvs1

Run (MICAS server, Podman), from the repo root:

    podman run --rm -it -v "$PWD":/work ghcr.io/kuleuven-micas/snax-gvsoc:gvs1

## Commands already tried

Run inside the container on a 2-core machine, from a clean image and a clean
repo, before step 1 was handed over. They are the starting point for GVS1
steps 2 to 4; times are for 2 cores.

Build GVSoC for the `snitch` target (8 min 21 s, first build):

    make -C gvsoc build TARGETS=snitch
    source gvsoc/sourceme.sh

Run the bundled program (exit code 0, prints nothing):

    gvrun --target snitch --work-dir build/work/snitch \
        --param chip/soc/binary=$PWD/gvsoc/pulp/examples/snitch/fp32_computation_vector.elf run

Build the snitch_cluster tests (47 ELFs, 4 s). `APPS=` skips the
applications, whose data generators need numpy and torch, which are not in
the image:

    cd snitch_cluster/target/snitch_cluster
    make DEBUG=ON APPS= tests

Run one (`printf_simple` prints `Hello, World!` nine times, exit code 0):

    gvrun --target snitch --work-dir /work/build/work/printf_simple \
        --param chip/soc/binary=$PWD/sw/tests/build/printf_simple.elf run

Tutorial 0 from a copy outside the GVSoC tree (build 2 min, prints `Hello`):

    mkdir -p tutorials && cd tutorials
    T=/work/gvsoc/engine/docs/developer_manual/tutorials
    cp -r $T/utils $T/0_how_to_build_a_system_from_scratch .
    cd 0_how_to_build_a_system_from_scratch
    export GVSOC_ROOT=/work/gvsoc
    make prepare gvsoc all run

The tutorial build shares `build/` with the `snitch` build; the `snitch`
target still ran afterwards.

Differences from the GVSoC website docs: the tutorials are in
`gvsoc/engine/docs/developer_manual/tutorials`, the launcher is `gvrun` with
`--parameter binary=<elf>`, and tutorials 13 and 18 have no directory.

## Log

### GVS1 step 1: repo and container

- 2026-10-07. Repo created on micaseb19; image built with Docker on WSL
  (x86), pushed to ghcr.io, pulled and run with Podman on micaseb19.
- Image: `ghcr.io/kuleuven-micas/snax-gvsoc:gvs1`, 4.73 GB unpacked, about
  2.0 GB to pull. Contents: RISC-V GCC 2.1 GB, Snitch LLVM 1.6 GB, Ubuntu
  base and build packages 0.7 GB, Python packages 0.4 GB.
- `git submodule status --recursive` shows gvsoc at 93cedc4 and
  snitch_cluster at 4652c6b.
- Version check in the container: gcc 13.3.0, cmake 3.28.3, Python 3.12.3,
  riscv64-unknown-elf-gcc 14.2.0, clang 12.0.1, bender 0.27.1,
  GVSOC_WORKDIR=/work/build. `/work` is writable.
- Plain `podman run --rm -it -v "$PWD":/work <image>` works; no extra
  mount or user flags needed.
- Learned: `git add` the submodules after checking out the pins and before
  `git submodule update --init --recursive`, or the update resets them to
  the commit recorded by `submodule add`.

### GVS1 step 2: GVSoC built, bundled program runs

- 2026-10-07, micaseb19, in the container.
- `make -C gvsoc build TARGETS=snitch` builds into `build/`.
- `gvrun --target snitch ... fp32_computation_vector.elf run` prints nothing
  and exits 0. With `--trace=pe0/insn`: 484 lines, first instruction at
  cycle 7909 (boot ROM, 0x1000), last one an `ebreak` at cycle 23862.
- Every new container needs `source gvsoc/sourceme.sh` again.
- `gvrun` creates its own `--work-dir`, but a `>` redirect into a directory
  that does not exist yet fails before `gvrun` starts.

### GVS1 step 3: Snitch tests built from source and run

- 2026-10-07, micaseb19, in the container.
- `make DEBUG=ON APPS= tests -j8` in `snitch_cluster/target/snitch_cluster`
  builds 47 test ELFs. `APPS=` skips the applications, whose data
  generators need numpy and torch (not in the image). The first build needs
  internet: Bender fetches one dependency into `snitch_cluster/.bender`.
- Ran 11 tests on `gvrun --target snitch`: simple, printf_simple, barrier,
  dma_simple, interrupt_local, fp32_computation_vector, openmp_parallel,
  perf_cnt, zero_mem, tls all exit 0 with no "invalid register" warning.
  non_null_exitcode exits 1, as intended (its main returns 14).
- This confirms the pin pair gvsoc 93cedc4 + snitch_cluster 4652c6b.
- Each run leaves its full system description in
  `build/work/<name>/gvsoc_config.json`.

### GVS1 step 4: tutorial 0, system from scratch

- 2026-10-07. Working copy in
  `tutorials/0_how_to_build_a_system_from_scratch`, with `tutorials/utils`
  beside it; write-up in `docs/tutorials/0_system_from_scratch.md`.
- The figures in this entry are from the check run of the same steps on a
  2-core Ubuntu 24.04 machine at the same pins, outside the container.
- `export GVSOC_ROOT=/work/gvsoc`, then `make prepare gvsoc all run` prints
  `Hello`. The GVSoC build for `my_system` takes 1 min 43 s after a `snitch`
  build. No `BUILDDIR=`, so the build shares `/work/build`; the `snitch`
  target still runs afterwards.
- `--trace=insn`: 231 lines, first instruction at cycle 3 (`_start`,
  0xc04), last one an `ebreak` at cycle 298. 100 MHz clock, 10000 ps per
  cycle, one instruction per cycle.
- The generator (`my_system.py`) runs twice. At build time
  `gapy ... components` writes `build/build/gvsoc/configs/my_system.config`
  (the C++ models to build, one `.so` each in `build/install/models`, named
  by a hash of sources and flags) and `my_system.tree.cpp` (instances,
  bindings and some parameter values, compiled into
  `libplatform_tree_my_system.so`). At run time `gvrun` runs the script
  again and writes `build/work/gvsoc_config.json` with the per-instance
  properties.
- The loader writes the ELF through the router as a normal IO request, then
  drives the entry and fetch-enable wires of the core. `printf` and `exit`
  use semihosting; there is no UART.
- `cpu/iss` is the instruction set simulator, GVSoC's CPU model: it executes
  each instruction's effect and adds a cycle count, with no pipeline model.
  The Snitch cores are variants of it (`iss/src/snitch*`). An `iss_v2`
  directory exists next to it; not looked at.
- Ports are declared in the C++ model (`new_master_port`, `new_slave_port`).
  The `i_X` / `o_Y` methods of the Python generator wrap those names with a
  type signature and are the nearest thing to a module header. List them
  with `grep -n "def [io]_[A-Z_]*(" <generator>.py`, or at run time with
  `--trace=<instance>` and the `New ... port` lines. The Python list can be
  incomplete: `memory.cpp` has `power_ctrl` and `meminfo`, `memory.py` only
  `i_INPUT`.
- What GVSoC checks on a binding, tried on this system: a misspelled method
  is a Python `AttributeError`; a type mismatch is `Invalid signature`; a
  port name unknown to the C++ model is `Binding from invalid slave port`;
  a missing `o_DATA` is `Data master port is not connected` (a check in the
  core model). A missing `o_DATA_DEBUG` runs fine. A missing `o_START` or
  `o_ENTRY` gives no message and the simulation never ends.
- The tutorial text in `tutorials.rst` at the pin is out of date (`parser`
  and `options` arguments, `remove_offset`, `gvsoc --binary`). The file in
  `solution/` is the working reference: `TargetParameter`, `rm_base=True`,
  and a `Target` class with `model` and `name` attributes.
- Every tutorial writes its program to `build/test/test` and its run output
  to `build/work/`, so each one overwrites the previous.
- GDB skipped: the server starts, but the toolchain's
  `riscv64-unknown-elf-gdb` needs libpython3.10, which Ubuntu 24.04 does
  not have. Seen on the check machine; not tried in the container.
- A run leaves `__pycache__/` next to the generator; it should be ignored
  by git.

### GVS1 step 5: tutorial 1, component from scratch

- 2026-10-08. Working copy in
  `tutorials/1_how_to_write_a_component_from_scratch`; write-up in
  `docs/tutorials/1_component_from_scratch.md`.
- The figures in this entry are from the check run of the same steps on a
  2-core Ubuntu 24.04 machine at the same pins, outside the container.
- `make prepare gvsoc all run` prints
  `Received request at offset 0x0, size 0x4, is_write 0` then
  `Hello, got 0x12345678 from my comp`. The tutorial text matches
  `solution/`, except one handler declaration with `void *__this` instead
  of `vp::Block *__this`.
- The first `make gvsoc` takes 4 min 1 s (197 files), as long as a first
  build of tutorial 0. The tutorial directory is a module root and an
  include path of every model, so switching tutorials recompiles all models
  of `my_system`, the RV64 core included, in four variants (`optim`,
  `debug`, `asserts`, `profile`). Expect this once per tutorial. Editing
  `my_comp.cpp` and rebuilding: 7 to 14 s.
- The library name `gen_my_comp_cpp_<hash>` hashes the source names and
  flags, not the file content; it stays the same across edits.
- Changing `value` in `my_system.py` needs no rebuild and gives no platform
  tree warning: the property is only in `gvsoc_config.json`, and the tree
  node of `my_comp` has no compiled config.
- `get_child_int` returns 0 with no message when the property is missing,
  so a misspelled property name is silent.
- Without `extern "C" gv_new` the build passes and the run aborts with
  `couldn't find gv_new loaded module`.
- An IO request is a direct function call through pointers copied at bind
  time (`IoMaster::bind_to`); router, model and the core's `c.lw` all show
  in cycle 158. For a load, `get_data()` points to the core's destination
  register. `lw` does not clear it first and `lbu` does, so an unanswered
  4-byte read returns the old register value and a 1-byte one returns 0.
- The model answers `IO_REQ_OK` to everything. Returning `IO_REQ_INVALID`,
  or reading an unmapped address, makes the RV64 core take a load fault;
  the runtime exits 1 and `gvrun` prints
  `Input error: Platform returned an error (exitcode: 1)`, with no message
  naming the address. Not checked on the Snitch target.
- Nothing in the pinned tree reads `GAPY_TARGET`; tutorial 1's
  `my_system.py` has none and works. The tutorial 0 page was corrected.
- Tutorial 1's `my_system.py` creates no `Gdbserver`; the runner adds one
  at the top level (`gvsoc/engine/python/gvsoc/runner_gvrun2.py`).
- Questions answered. `vp` is the engine's C++ namespace and headers
  (`gvsoc/engine/engine/include/vp/`): base classes, port types, clocks,
  traces, registers; the source never spells it out, the docs call GVSoC a
  virtual platform. `testset.cfg` is GVSoC's own regression test for the
  tutorial (`gvtest`): it builds `solution/` in its own build directory,
  runs it and checks the two output lines; not used here.
- The page has a commented `my_comp.cpp` and a line-by-line explanation of
  step 3. Both tutorial pages draw the system in Mermaid.

### GVS1 step 6: tutorial 2, components communicating

- 2026-10-08. Working copy in
  `tutorials/2_how_to_make_components_communicate_together`; write-up in
  `docs/tutorials/2_components_communicating.md`.
- The figures in this entry are from the check run of the same steps on a
  2-core Ubuntu 24.04 machine at the same pins, outside the container.
- `make prepare gvsoc all run` prints `Received request ...`,
  `Received value 1`, `Received results 11111111 22222222`, then
  `Hello, got 0x12345678 from my comp`. Build 4 min 25 s (201 files), again
  a full rebuild because the tutorial directory changed. The text in
  `tutorials.rst` uses the old `gsystree` alias and `void *__this`;
  `solution/` is the reference.
- A wire (`vp::WireMaster<T>` / `vp::WireSlave<T>`, `vp/itf/wire.hpp`) is a
  direct function call, like an `io` request: binding copies the slave's
  handler into the master, `sync(value)` calls it. No event, no delay, no
  stored value. The whole exchange (`my_comp` -> `my_comp2` -> back into
  `my_comp`) runs inside the core's `c.lw` at cycle 158, with the calls
  nested.
- The signature string is only a label both ends must match
  (`Invalid signature` otherwise); GVSoC never compares it with the C++
  types. Same signature with different C++ types builds and binds, then
  crashes (`Segmentation fault`, exit 139).
- `sync()` on an unbound `WireMaster` crashes with a segmentation fault;
  checked with a print to `stderr` showing `is_bound()` = 0 just before the
  call. Unlike tutorial 0's unbound `o_DATA_DEBUG`, this is not harmless.
  Models' `printf` output is lost in such a crash (stdout is buffered).
- One master can be bound to several slaves; each receives the value in
  turn (`next` chain in `WireMaster`). Tried with two `MyComp2`.
- A pointer sent on a wire is only valid during the receiver's handler when
  it points to the sender's stack, as in the tutorial.
- The two classes are both called `MyComp`; this is fine because each
  model is its own library with its own `gv_new`.
- The working copy keeps the `solution/` files; the page shows the same
  code with comments, which was built and run on the check machine.
- Impression after tutorial 2: GVSoC is more involved than expected and
  its documentation is weak (out-of-date text, few comments, behaviour found
  by experiment). An input for GVS4.

### GVS1 step 7: tutorial 3, system traces

- 2026-10-08. Working copy in
  `tutorials/3_how_to_add_system_traces_to_a_component`; write-up in
  `docs/tutorials/3_system_traces.md`.
- The figures in this entry are from the check run of the same steps on a
  2-core Ubuntu 24.04 machine at the same pins, outside the container.
- Tutorial 3 starts from tutorial 1's component, not tutorial 2's. The text
  in `tutorials.rst` matches `solution/`. Build 3 min 8 s (197 files).
- `make run` prints only `Hello, ...`; `--trace=my_comp` adds
  `1580000: 158: [/soc/my_comp/trace] Received request at offset 0x0, ...`
  after eight base-class lines (ports, bindings, reset).
  `--trace-level=info` hides the `DEBUG` message. `--trace=my_comp:t3.log`
  writes to the work directory (`/work/build/work/t3.log`), colour codes
  kept.
- Traces are compiled out of the default build: only the `debug` and
  `profile` model variants define `VP_TRACE_ACTIVE`
  (`gvsoc/engine/cmake/vp_model.cmake`). Any `--trace`, `--vcd` or
  `--event`, even one matching nothing, makes `gvrun` use
  `gvsoc_launcher_debug` and `install/models/debug/`
  (`gen_config` in `runner_gvrun2.py`). A 20-million-iteration loop on
  `my_system`: 4.2 s by default, 14.2 s with `--trace=zzz`, about 3.5 times
  slower before any line is printed.
- Every component already has a trace named `trace` (from `vp::Block`),
  registered again as `comp` (from `vp::Component`). The tutorial's trace
  reuses the name `trace`, so `--trace=my_comp/trace` also shows the base
  class's `clock` and `reset` port lines. Own traces should get their own
  names.
- Questions answered:
  - Several traces per component: yes, one `vp::Trace` member per name,
    each with its own path. The RV64 core registers 14 (`insn`, `lsu`,
    `csr`, `regfile`, ...); this is why `--trace=insn` selects only
    instructions.
  - Nesting, in Python: a component without `add_sources` is a pure
    container (composite) and can forward its own ports to a child with
    `self.bind(self, 'in_0', child, 'in_0')`, as `snitch_cluster.py` does.
    In C++: a model can contain `vp::Block` sub-units with their own path,
    traces and clock events but no bindable ports, as the Snitch fast
    core's `Ssr` and `SsrStreamer` do. Rule of thumb: parts wired
    differently per design point become components in a composite; fixed
    parts of one unit become blocks.
  - Profiling: the counterpart of SNAX-MODEL's profiles is statistics, not
    traces. A model registers counters with `stats.register_stat(...)`;
    `--stats` writes `build/work/stats.txt` with per-component counters
    (checked: `/soc/ico` and `/soc/mem` reads, writes, bytes, bandwidth).
    `--stats` uses the `profile` build: the same loop took 13.9 s against
    5.1 s by default.
  - Can the SNAX cluster be modelled in GVSoC: in outline yes, on top of the
    stock `snitch` target (cores, TCDM, DMA, crossbar already exist), adding
    streamers and accelerators as our own components and wires for
    `start` / `busy` / irq. The TCDM path is not the `Router` but
    per-core router, `L1_interleaver` and `Memory` banks. Two gaps are in
    the GVS2 and GVS3 findings below.

### GVS1 step 8: tutorial 4, VCD traces

- 2026-10-08. Working copy in
  `tutorials/4_how_to_add_vcd_traces_to_a_component`; write-up in
  `docs/tutorials/4_vcd_traces.md`.
- The figures in this entry are from the check run of the same steps on a
  2-core Ubuntu 24.04 machine at the same pins, outside the container.
  GTKWave was not available there; the waveform was checked by reading
  `all.vcd`.
- Tutorial 4 starts from tutorial 3's component; `main.c` now writes 0 to
  19 to `0x20000000`. `solution/` has only `my_comp.cpp` and `my_comp.py`.
  The text in `tutorials.rst` matches. Build 3 min 2 s (196 files).
- `vp::Signal<uint32_t> vcd_value(*this, "status", 32)` gives the path
  `/soc/my_comp/status`. `set(v)` dumps a change, `release()` dumps `z`.
  A signal also keeps its value (`get()`), has `set_and_release` (one-cycle
  pulse), `inc` / `dec`, and its own text trace at `TRACE` level
  (`/soc/my_comp/status/trace`, `Setting signal (value: ...)`).
- `--vcd --event=my_comp` writes `build/work/all.vcd` (timescale 1 ps) and
  `view.gtkw`. `status` changes from cycle 1513, 0 to 4, `z`, 6 to 19, one
  step every 5 cycles. `--vcd` alone does not dump component signals (4
  signals, no `status`); `--event=.*` dumps 88 signals, 772 kB for about
  1500 cycles.
- `gen_gtkw` in the generator only places the signal in the GTKWave script;
  without it `status` is still in the VCD. `view.gtkw` names the VCD by its
  container path, which must be fixed when opening it on another machine.
- The 5 cycles per iteration are 3 instructions (`c.sw`, `c.addiw`, `bne`)
  with a taken `bne` costing 3 cycles: the RV64 core model adds a branch
  penalty, so "one instruction per cycle" (step 4) holds only for
  straight-line code.
- `gvrun` does not clean `build/work/`; files from earlier runs
  (`stats.txt`, trace files) stay.

### GVS1 step 9: tutorial 5, register map

- 2026-10-08. Working copy in
  `tutorials/5_how_to_add_a_register_map_in_a_component` (the `solution/`
  files, with the generated `headers/`); write-up in
  `docs/tutorials/5_register_map.md`.
- Gone through on micaseb19 in the container. The figures in this entry are
  from the check run of the same steps on a 2-core Ubuntu 24.04 machine at
  the same pins, outside the container. The build time after a tutorial
  switch was not measured there (it was a first build of everything,
  5 min 56 s for 334 files); a rebuild after an edit of `my_comp.cpp` took
  6 s.
- Three ways to make a register. By hand: one more branch on
  `req->get_addr()` in the handler. `vp::Register<uint32_t>`: a value with a
  name, a trace (`<name>/trace`) and a VCD signal, and `update()` for
  partial accesses. Generated: `regmap-gen` turns `regmap.md` into one
  `vp::Register` class per register and a map class `vp_regmap_regmap`,
  which is a `vp::Block`; `regmap.access()` picks the register from the
  offset.
- The finished model prints `REG0 callback`, the two `Hello, got ...` lines,
  `Hit value`, `Hello, got 0x11227744 at 0x20000008`, `REG0 callback`. The
  first callback is the reset at time 0 (registered with `true`), the last
  one the store to `0x20000100` at cycle 4249. With
  `--trace=my_comp/regmap --trace-level=trace` each access is printed with
  its fields, e.g. `value: { FIELD0=0x78, FIELD1=0x123456 }`.
- The code in `tutorials.rst` matches `solution/`, but its trace paths
  (`/soc/my_comp/reg0`) and cycle numbers are out of date; the registers
  are under `/soc/my_comp/regmap/`. The starting `my_comp.cpp` now returns
  `IO_REQ_INVALID` for what it does not serve.
- `regmap-gen` is a Python script of the gvsoc submodule
  (`gvsoc/engine/bin/regmap-gen`, module in `gvsoc/engine/python/regmap/`),
  not a separate install; the container's Python packages are enough. Three
  ways to call it:
  `PYTHONPATH=/work/gvsoc/engine/python /work/gvsoc/engine/bin/regmap-gen ...`
  works with no build and no `sourceme.sh`, and is what the page uses; plain
  `regmap-gen` needs a finished build (the install step copies it to
  `build/install/bin`) and `sourceme.sh` sourced in the current container,
  otherwise `command not found`; the tutorial's `make regmap` fails in a
  copy outside the GVSoC tree (relative path to the engine).
- `regmap-gen` is the first tutorial command that needs `sourceme.sh`: the
  `make` targets call `gvrun` by its full path. Easy to miss in a new
  container.
- `make prepare` copies `solution/my_comp.cpp`, which includes the generated
  headers, so `make gvsoc` then fails with
  `headers/mycomp_regfields.h: No such file or directory` until the headers
  are generated.
- `update(reg_offset, size, value, is_write)`: byte offset inside the
  register (not a bus address), number of bytes, the request's data pointer
  (source on a write, destination on a read), direction (not a write
  enable). A `memcpy` with no bounds check: an 8-byte store into the 32-bit
  `my_reg` was accepted and read back as 8 bytes.
- A callback replaces the default read and write of its register, for loads
  as well as stores, and must call `update` itself; without it a store is
  lost and a load returns a stale value.
- An access to an offset of the map with no register prints
  `Accessing invalid register` and ends the run with exit code 1: model
  warnings are errors by default (`force_warning` calls `exit(1)`).
  `--no-werror` lets the run go on. The tutorial model ignores the return
  value of `regmap.access` and answers `IO_REQ_OK`.
- An access the model refuses (size other than 4 in the hand-made part) ends
  as `Platform returned an error (exitcode: 1)` with no address. GCC splits
  a misaligned 4-byte store into 2-byte accesses, so a request crossing two
  registers could not be produced from C.
- The `Default` of the register table is the reset value; a field's
  `Default` is not. An `Access Type` of `R` sets a write mask in the header
  that `vp::Register` does not apply: read-only needs a callback.
- Registers show up in the VCD (`--vcd --event=my_comp`: `my_reg`,
  `regmap/reg0`, `regmap/reg1`).
- Questions answered:
  - The `regmap.md` format has no documentation; it is what
    `gvsoc/engine/python/regmap/regmap_md.py` accepts. A `# Title` and a
    `## Registers` table are required; columns are found by name; one
    `### <register>` section per register holds its fields. The tool does
    not check overlaps or field ranges, and a misspelled column name gives a
    misleading error. Written up in `docs/reference/regmap.md`, with the
    options that work (`--name`, `--header-headers`, `--input-hjson`,
    `--rst`, `--json`) and those that do not at the pin (`--table`).
  - All 12 files in `headers/` are generated. The model needs
    `_regfields.h` and `_gvsoc.h`; `_regs.h` and `_regfields.h` are usable
    from the C program; the accessor headers need `GAP_READ` / `GAP_WRITE`
    macros that `tutorials/utils` does not have.
  - The stock Snitch cluster peripheral generates its map at build time
    from the reggen HJSON of snitch_cluster, in a `gen()` method of its
    Python generator. Tried with `regmap.md`: headers go to
    `build/build/engine/<dir>/`, and an edit of `regmap.md` followed by
    `make gvsoc` regenerates and rebuilds in 7 s.
  - A `start` / `status` example with a read-only status register and a
    program using the generated offsets was built and run; it is in
    `docs/reference/regmap.md`.
- New: `docs/reference/gvsoc_api.md`, the classes and calls used in
  tutorials 0 to 5 by class, with their arguments and whether each was run
  or only read. Later steps add to it.

### GVS1 step 10: tutorial 6, timing

- 2026-10-08. Working copy in `tutorials/6_how_to_add_timing`; write-up in
  `docs/tutorials/6_timing.md`.
- Gone through on micaseb19 in the container. The figures in this entry are
  from the check run of the same steps on a 2-core Ubuntu 24.04 machine at
  the same pins, outside the container.
- Tutorial 6 starts from tutorial 2's two components, with a trace in
  `my_comp2`; `solution/` holds only `my_comp2.cpp`. Build after the
  tutorial switch: 2 min 33 s (201 files); a rebuild after an edit: 4 s.
  The text in `tutorials.rst` guards the enqueue with `is_enqueued()`,
  `solution/` does not; the behaviour is the same at the pin.
- Before: `Received notif` and `Sending result` are both in cycle 158,
  inside the core's `c.lw`. After, with `event.enqueue(10)` in the
  notification handler and the sending moved into the event's callback:
  `Received notif` at cycle 158, `Sending result` at cycle 168, and the
  core runs 8 instructions in between. The program's output is the same
  three lines; the delay only shows in the traces.
- A `vp::ClockEvent` is a callback plus a cycle. `enqueue(n)` puts it in the
  list of the owner block's clock engine at `now + n` and returns at once;
  nothing in the model blocks. The count is in cycles of the owner's clock
  (100 MHz here). The core's instruction step has the same callback
  signature (`Exec::exec_instr`; read, not run), so core and model are
  callbacks of one clock engine.
- One event holds one pending call. Two notifications one cycle apart with
  `enqueue(10)` gave one callback, at cycle 168: an enqueue on a pending
  event is ignored when its cycle is later, and replaces the pending one
  when it is earlier (`enqueue(2)` gave cycle 161). No message either way.
- Also tried: `enqueue(0)` runs in the same cycle; re-enqueueing from the
  callback gives a periodic event (cycles 160, 162, 164); `enable()` runs
  the callback at every cycle from the next one until `disable()`;
  `cancel()` drops the pending call; `get_args()` carries values to the
  callback but belongs to the event, so a second enqueue overwrites them.
- A pending event does not keep the run alive: with `enqueue(1000000)` the
  run ended when the program exited (about cycle 1500) and the callback
  never ran, with no message.
- Cost: an event enabled at every cycle with an empty callback made a
  20-million-iteration loop about 25 % slower (6.0 s against 4.8 s, default
  build).
- A busy flag with a duration, tried in `my_comp`: a store starts a run of
  100 cycles (`busy = true`, `done_event.enqueue(n)`), the callback clears
  the flag, the program polls it. `Start` at cycle 161, `Done` at cycle 261,
  `done after 21 polls`.
- Question answered: yes, the idea is to compute the result at once in
  plain C++ and let the event decide when it becomes visible. Tried with an
  fadd of 4 cycles and an fmul of 6, four operations started one cycle
  apart: each result arrived its own latency after its start (cycles 162,
  164, 165, 167). One event is enough for several operations in flight,
  with a list of pending results in the model. The list must be ordered by
  ready cycle: a first version with a FIFO delivered the second fadd a cycle
  late, behind the slower fmul. Latency and back-pressure are separate: a
  unit that holds one operation at a time also needs a `busy` check.
- `vp::ClockEvent` added to `docs/reference/gvsoc_api.md`.

### GVS1 step 11: tutorial 7, IO request interface

- 2026-10-11. Working copy in
  `tutorials/7_how_to_use_the_io_request_interface`; write-up in
  `docs/tutorials/7_io_requests.md`.
- Gone through on micaseb19 in the container. The figures in this entry are
  from the check run of the same steps on a 2-core Ubuntu 24.04 machine at
  the same pins, outside the container; the committed working copy was built
  and run there too (both `Hello` lines, last instruction at cycle 5907).
- Tutorial 7 starts from tutorial 3's single component; `solution/` holds
  only `my_comp.cpp`. Build after the tutorial switch: 2 min 23 s (197
  files); a rebuild after an edit: 4 s. The tutorial's `main.c` never reads
  the second register, so a read of `0x20000004` has to be added to see the
  asynchronous path. `testset.cfg` only checks the first line.
- Synchronous answer with latency: `req->inc_latency(1000)` before
  `return vp::IO_REQ_OK`. The latency is a number in the request; nothing is
  scheduled.
- The tutorial text is out of date on what the core does with it. At the
  pin the RV64 core does not stall at the load: the load at cycle 158
  completes, the core runs on, and it stalls at `c.sdsp a1` (cycle 167), the
  first instruction that reads the loaded register; the next instruction is
  at cycle 1161. With the use three instructions after the load, latencies
  of 2, 3, 4, 10 and 1000 put the next instruction at load cycle + latency
  + 3; latencies of 0 and 1 cost nothing. The tutorial program ends at
  cycle 2530 against 1537 without latency.
- A store's latency is ignored by this core: with 0, 1000 and 100000 the
  program ended at cycle 288 each time.
- `inc_latency` adds (twice 1000 gave 2000); `set_latency` keeps the larger
  value. The request arrives with latency 0 through the router.
- Asynchronous answer: keep the `vp::IoReq *`, `event.enqueue(2000)`, return
  `vp::IO_REQ_PENDING`; in the event's callback write the data and call
  `req->get_resp_port()->resp(req)`. The request arrives at cycle 2504 and
  the load's trace line appears at cycle 4504 with the value; no instruction
  runs in between. The core is stalled at the instruction itself.
- Pending works for stores: a store answered with `IO_REQ_PENDING` was held
  from cycle 161 to 2161. On this core it is the only way to make a store
  take time.
- `resp()` never called: the run never ends, with no message (killed after
  20 s). `resp()` called twice:
  `[/soc/host/exec] Trying to decrease zero stalled counter`, abort, exit
  code 134. `resp()` in the same cycle (`enqueue(0)`) works. A latency added
  just before `resp()` adds to the wait at the use of the value.
- `IO_REQ_DENIED`, then `grant(req)` 2000 cycles later and `resp(req)` 2000
  cycles after that: the load completes at cycle 4158 with the right value,
  the core stalled throughout. One run; the meaning of `grant` (the slave
  now owns the request) is from the comments in `io.hpp`.
- A latency of 1000000000 cycles ended the run at cycle 1000000965 in 7.9 s
  of host time, against about 1 s without: waiting is cheap, not free.
- Not checked: whether the router is in the return path of `resp()`; any of
  this on the Snitch core.
- Latency and pending calls in `docs/reference/gvsoc_api.md` are now marked
  as run.

### GVS1 step 12: tutorial 10, interconnect timing

- 2026-10-11. Working copy in
  `tutorials/10_how_to_customize_an_interconnect_timing` (`my_system.py` as
  in `solution/`, `main.c` changed to use the loaded values); write-up in
  `docs/tutorials/10_interconnect_timing.md`.
- Gone through on micaseb19 in the container. The figures in this entry are
  from the check run of the same steps on a 2-core Ubuntu 24.04 machine at
  the same pins, outside the container. The build time after a tutorial
  switch was not measured there (a first build of everything, 7 min 11 s).
- Tutorial 10 starts from tutorial 4's component; `solution/` holds only
  `my_system.py`. Nothing is written in C++: the timing of the router is two
  arguments of its generator, `latency` (on the router, or on one mapping
  with `o_MAP(..., latency=)`) and `bandwidth` (bytes per cycle, 0 = no
  limit, which is the default). Both are properties read from
  `gvsoc_config.json`: a change needs no rebuild and gives no platform tree
  warning.
- The tutorial text is out of date. Its `main.c` loads into a register that
  is never read, so the loop runs at one load per cycle with any latency or
  bandwidth (8 cycles per iteration, as with no timing). Its trace of a
  stalled `sd` does not happen at the pin: a store is not delayed. The
  default bandwidth is 0, not 4.
- `latency=100` on the `mem` mapping, tutorial `main.c`: the run ends at
  cycle 2039 against 341. The 1698 cycles are the loader (first instruction
  at cycle 103, not 3), 14 instruction fetches of 100 each, and two loads of
  the start-up code whose value is used at once (100 and 98).
- The core fetches through a one-line buffer of 64 bytes
  (`prefetch_single_line.cpp`): one 64-byte read on the fetch port each time
  the program counter leaves the line, also for a line fetched before. The
  fetch goes through the router like data, and a fetch latency stalls the
  core.
- With `main.c` changed to add up the four loaded values (12 cycles per
  iteration with no timing): `latency=100` gives 111 cycles per iteration.
  The four loads still go out in four consecutive cycles and their latencies
  overlap; four loads cost one latency. A latency delays each request and
  does not make requests wait for each other.
- `bandwidth=1`, no latency: 20 cycles per iteration. A 4-byte load takes
  the router for 4 cycles and the next one gets the remaining cycles as
  latency (3, 6, 9 for the second to fourth load; `next_burst` 12892, 12896,
  12900, 12904 in the router trace). The first instruction is at cycle
  12127: the loader's write of 12124 bytes takes 12124 cycles. The run ends
  at cycle 17491. With both (the solution): 120 cycles per iteration, end at
  cycle 27057.
- How it works (read in `interco/router/router.cpp`, and matching the
  traces): the synchronous router forwards the request inside the master's
  call and only writes two fields of the request, `latency` (cycles until it
  is served) and `duration` (`ceil(size / bandwidth)`). There is one limiter
  per input port and one per mapping, each with a read and a write counter
  ("free again from cycle N"); a request passes the limiter of its input,
  then the one of its mapping. The router's `latency` is added in the input
  limiter, a mapping's `latency` in the mapping limiter.
- A request that finds the router free gets latency 0 and only a duration.
  The RV64 core reads only the latency, so a single access costs it nothing
  at any bandwidth; the loader reads latency plus duration
  (`get_full_latency()`). The bandwidth limits a flow, it is not a cost per
  access: `bandwidth=4` and `bandwidth=8` leave the loop at 12 cycles.
- Tried beyond the tutorial, with three more loops (four loads of
  `my_comp`'s register, 12 cycles; four stores, 8 cycles; two loads and two
  stores in turn, 10 cycles):
  - `latency=7` on the `comp` mapping: 18 cycles, and nothing else is
    delayed. Router latency 5 plus mapping latency 7: 23 cycles; they add.
    `bandwidth=1` plus `latency=7`: 27 cycles; wait and latency add.
  - Stores only: 8 cycles with `latency=100` and with `bandwidth=1`. This
    core ignores a store's latency (step 11), so this router never slows a
    store down.
  - Loads and stores in turn, `bandwidth=1`: 11 cycles (reads and writes
    have separate counters). With `shared_rw_bandwidth=True`: 16 cycles; the
    stores then cost time through the loads behind them.
  - Fetch on its own router input (`host.o_FETCH(ico.i_INPUT(1))`): a load
    to `my_comp` no longer queues behind a fetch (first iteration 20 cycles
    against 79). No rebuild.
  - A loop that crosses a 64-byte line fetches twice per iteration: at
    `bandwidth=1` iterations of 185 and 87 cycles in turn, against 11 when
    compiled with `-falign-loops=64`. With no router timing both take 10.
  - A request that crosses two mappings (the loader's write, with the
    memory split in two) is split by the router into one request per
    mapping.
  - `--stats`: `/soc/ico` has reads, writes, bytes and average bandwidth,
    and no count of delayed cycles. `--vcd --event=ico`: an `addr` and a
    `size` signal per mapping.
  - `synchronous=False` is another C++ model (`router_async.cpp`): without
    a rebuild `Couldn't find component`, then 15 s of `make gvsoc`. It holds
    each request and answers later, so stores stall too (2 cycles apart, 4
    with `bandwidth=1`), a load costs one more cycle, and latencies are
    ignored. A program that calls `printf` aborts with
    `Pending IO response during debug request` (exit code 134): semihosting
    reads memory through the data port and cannot take a pending answer.
- Question answered: tutorials 8 (multiple cores) and 9 (clock domains) are
  skipped by the plan, not optional steps; tutorial 10 does not build on
  them. Two masters on one router are measured in GVS2 on the Snitch target.
- Router arguments and the request's `duration` added to
  `docs/reference/gvsoc_api.md`.

## Findings for later tasks

### GVS2

- The GVSoC Snitch model matches snitch_cluster as of August 2024.
- The `perf_cnt` test runs but every counter reads 0.
- The `snitch` target has a `soc/nb_cluster` parameter.
- Changing the L1 bank count (16, 32, 64) left the `dma_simple` cycle count
  unchanged at 23460. One core and a plain DMA copy, so this does not yet
  say whether bank contention is modelled.
- GVSoC's docs say `pulp.snitch.snitch_cluster_single` and the default slow
  core are to be deprecated in favour of `snitch:core_type=fast`.
- The `Router` is not the TCDM crossbar. TCDM path in the Snitch target
  (read from `snitch_cluster.py` and the C++, not yet measured): per-core
  `Router` (address decode, `bandwidth=8`) -> `L1_interleaver` (bank select
  from the low address bits, no arbitration) -> `Memory` bank. Per-bank
  contention is in the bank model: `width_log2=3` and a `next_packet_start`
  cycle, so a request to a busy bank gets extra latency. No priority or
  round-robin. The DMA reaches the same banks through `DmaInterleaver`, so
  a non-core port (a streamer) could be added the same way. `narrow_axi`
  and `wide_axi` are plain `Router` instances. To measure: two masters
  hitting the same bank in the same cycle.
- The bank model (`memory.cpp`) already reports a conflict: when a request
  arrives while `next_packet_start` is in the future, it adds the
  difference as latency and prints `Delayed packet (latency: N)` on its
  trace. It has stats for reads, writes, bytes and bandwidth, but no
  conflict counter. Counting conflicts needs a `StatScalar` next to that
  line, in our own L1 model or a fork of `memory.cpp`.
- SNAX configures accelerators with `csrw` to custom CSRs through the CSR
  manager, not with memory-mapped stores. The GVSoC core handles CSRs
  inside the ISS. The core has an `o_OFFLOAD` wire (`riscv.py`,
  `IssOffloadInsn`) that hands instructions to another unit, used by the
  Snitch FP subsystem; whether custom CSR accesses can be routed out
  through it is not checked. Fallback: memory-mapped accelerator registers,
  which changes the SNAX software.
- `regmap-gen` reads reggen HJSON (`--input-hjson`, or `regmap_hjson` in a
  generator's `gen()`); run on the stock
  `snitch_cluster_peripheral_reg.hjson`, 52 register classes. If SNAX
  describes an accelerator's registers in that format for the RTL, the same
  file can generate the GVSoC model's map. How SNAX's CSR manager lists its
  registers has not been read yet.
- To measure on the `snitch` target: what the Snitch core does with a
  latency on a load and on a store, and with `IO_REQ_PENDING`. On the
  tutorial's RV64 core a load's latency stalls at the first use of the
  value and a store's latency is ignored (step 11). The Snitch build takes
  other branches in `gvsoc/core/models/cpu/iss/src/lsu.cpp`
  (`CONFIG_GVSOC_ISS_SNITCH`: stores "without an answer to the core", one
  more cycle on loads). The stock bank model reports contention as
  latency, so this would decide whether a core sees bank conflicts on
  stores.
- The cluster's routers are the synchronous `Router` of tutorial 10 with a
  bandwidth and no latency (read in `snitch_cluster.py`): `wide_axi` and
  `tcdm_dma_ico` 64, `narrow_axi` 8, one `pe<N>_ico` per core with
  `arch.tcdm.bank_width`. Measured on the tutorial system (step 12): this
  router only writes a latency and a duration into the request and never
  holds it; the bandwidth is kept per input port and per mapping, so two
  masters delay each other only when they share one of the two; a request
  that finds the router free gets latency 0. To measure on the `snitch`
  target: whether the Snitch core and the DMA read the duration
  (`get_full_latency()`) or only the latency, since that decides what a
  bandwidth of 8 or 64 costs them.
- On the tutorial core a store ignores its latency, so a synchronous router
  or a bank that reports contention as latency never slows a store. If the
  Snitch core does the same, store contention on L1 is invisible in cycle
  counts unless the path holds the request (pending), as the asynchronous
  router does.
- Instruction fetch goes through the interconnect and stalls the core on a
  latency. The tutorial core refetches a 64-byte line at each line change;
  the tree has a Snitch instruction cache model (`snitch_icache.cpp`);
  whether the `snitch` target uses it is not checked. Fetch cost has to be
  kept apart from data cost when reading cycle counts.

### GVS3

- Editing one C++ model and rebuilding takes 5 to 20 s; a run of a small
  test takes 1 to 3 s (2 cores).
- The bank count is hard-coded in the stock generator. For sweeps, our own
  target should expose such values as `gvrun` parameters, so that a design
  point needs no edit of the generator. Not tried yet.
- Generator changes need no rebuild as long as every C++ model variant is
  already compiled. Checked: values (tutorial 0 memory size) and shape
  (Snitch L1 with 16, 32 and 64 banks, edited in the installed generator
  `build/install/generators/pulp/snitch/snitch_cluster/snitch_cluster.py`).
  GVSoC warns that the installed platform tree does not match and builds
  the system from `gvsoc_config.json`; traces are identical and run time is
  unchanged (1.6 s for the bundled ELF, 2 cores). A variant with other
  sources or flags (e.g. `Router(..., synchronous=False)`) fails with
  `Couldn't find component` until rebuilt.
- Caveat from `runner_gvrun2.py`: the JSON path only works for models that
  read their parameters from JSON. `Memory` and the clock have that
  fallback and the router reads JSON only; these are the only compiled
  configs in the stock `snitch` target. Other models with a config class
  (snitch fast core, iDMA v2/v3, `iss_v2`) are not checked.
- GVSoC does not check that a component's ports are all bound, unless the
  model does it itself. Our SNAX components should check their mandatory
  ports in C++, as the core does for `data`.
- A model reads its parameters from `gvsoc_config.json` with
  `get_js_config()`, so a value that only goes through `add_properties` can
  be swept with no rebuild (tutorial 1). Our components should read their
  sizes and latencies that way, and check that each one is present, since
  a missing property reads as 0 with no message.
- Our module root (`snax/`) should stay at one path: moving it, like
  switching tutorial directories, recompiles every model of the target.
- A register window should return `IO_REQ_INVALID` for offsets and sizes it
  does not serve, so a wrong access from the program traps instead of
  reading stale data (checked on the RV64 core, not on Snitch).
- GVSoC's `gvtest` with a `testset.cfg` and a `Checker` on the output is a
  ready pattern for regression tests of our components.
- `start` / `busy` / interrupt lines map to `WireMaster<bool>` /
  `WireSlave<bool>`, but a wire call takes zero time and nests inside the
  caller. An accelerator model that should react a cycle later must
  schedule a clock event in its wire handler (tutorial 6), and must have
  its state consistent before it drives any wire, since the callee may call
  back into it.
- Optional output wires of our components should be guarded with
  `is_bound()`; `sync()` on an unbound wire crashes.
- An interrupt line to several cores can be one master bound to several
  slaves.
- Profiling and design-space runs must not use `--trace`: any trace option
  switches to the debug build, about 3.5 times slower. `--stats` switches
  to the profile build, about 2.7 times slower. Measured on the tutorial
  `my_system` with a 20-million-iteration loop, 2 cores.
- A SNAX model's always-on numbers should be statistics
  (`stats.register_stat`), written to `stats.txt` by `--stats`; traces are
  for looking at single runs. Whether `stats.txt` (or `--stats-raw`) can
  feed the SNAX-FORGE run viewer is part of the GVS3 question.
- Streamers are `io` masters that issue many requests into L1. Tutorial 7
  covers only the slave side; the HWPE tutorial (step 15) is the example of
  a component streaming into L1, so step 15 is kept.
- Build structure for SNAX-GVSoC: the cluster as a Python composite on top
  of the stock Snitch cluster, streamers and accelerators as separate
  components (wired per design point), internal parts of an accelerator
  (FSM, counters) as `vp::Block`s inside one model.
- VCD is the most direct feed from GVSoC into the SNAX-FORGE run viewer
  found so far: `vp::Signal` values per path with ps time stamps, selected
  with `--event`, in a standard format that `pyvcd` (already in the
  container) can read. Not tried yet. Text traces carry no structure, and
  `stats.txt` is end-of-run only.
- Candidate split for a SNAX accelerator model: FSM state, streamer
  occupancy and bank-conflict pulses as signals (VCD, looked at per run);
  totals such as busy cycles and conflicts as statistics (`--stats`, every
  profiling run).
- Register maps can be generated end to end: a description (`regmap.md` or
  HJSON) next to the component, and a `gen()` method in its Python
  generator that writes the headers during `make gvsoc` (run in step 9,
  7 s after an edit). SNAX-FORGE could write that description from the
  accelerator's interface, as one more item of the per-design-point bundle
  (snax-forge D111; the layout is D36, the mapping onto SNAX's CSRs is open
  item 9). Details and a worked example in `docs/reference/regmap.md`.
- What generation does not cover: the behaviour (callbacks, written once
  per kind of block), and checking. `regmap-gen` accepts overlapping
  registers and fields silently, so whatever writes the description has to
  check it.
- The map is compiled into the model: a new register layout is a rebuild of
  that model, a new value is not. A sweep over register counts rebuilds per
  point.
- `vp::Register::update` has no bounds check and the generated write mask
  is not applied. Our register windows should check `offset + size`
  themselves, make read-only registers read-only in a callback, and return
  `IO_REQ_INVALID` when `regmap.access` reports no register.
- A warning from a model (`vp_warning_always`, as `vp::regmap` uses for an
  unknown offset) ends the run with exit code 1 unless `--no-werror` is
  given. Useful for our own "this must not happen" checks.
- The generated `_regs.h` and `_regfields.h` give the C program the same
  offsets and bit positions as the model (used in the example of
  `docs/reference/regmap.md`). A candidate source for the header of CSR
  names in GEN2.
- Timing of an accelerator model in GVSoC: compute at once, delay the
  arrival with a `vp::ClockEvent`. The accelerator entry's `latency` is the
  number given to `enqueue`; its `ii` is a busy check before a new
  operation is accepted. Several operations in flight need one event and a
  list of pending results ordered by ready cycle (run in step 10 with fadd
  and fmul).
- Two styles of clock event: enqueue per occurrence, or enabled at every
  cycle. A per-cycle callback cost about 25 % of run time on the tutorial
  system even when empty, so a streamer or accelerator should enqueue for
  the next cycle in which something happens, not tick every cycle, unless
  it really works every cycle.
- An enqueue on a pending event is silently ignored or replaces the pending
  one. A model that can be asked again while busy has to handle that itself
  (a queue, or a refusal), or requests are lost with no message.
- A pending event does not keep the simulation alive. A program that exits
  before the accelerator is done ends the run without the result; the
  program has to wait (poll `busy`, or an interrupt).
- `this->clock.get_cycles()` gives a model the current cycle, for
  `busy_cycles` counters and for stamping events for the run viewer.
- Two ways to make the core wait on a register access of an accelerator:
  a latency (a number in the request, no event, no state) for a fixed
  access cost, and `IO_REQ_PENDING` with `resp()` when the wait depends on
  the model, e.g. a blocking write to `start` answered by the event that
  ends the run. A blocking `start` and a polled `busy` are both possible;
  which one matches SNAX's software is to be checked.
- A pending request is a contract: exactly one `resp()`. A forgotten one
  hangs the run with no message, a second one aborts. Our components should
  keep the pending request in one place and clear the pointer when they
  answer.
- While its request is pending a core is stalled, so one core cannot send a
  second one. With several masters (cores, DMA, streamers) on the same
  slave that no longer holds: a slave that answers `IO_REQ_PENDING` needs a
  queue, or `IO_REQ_DENIED` and `grant()` for the others.
- `IO_REQ_DENIED` / `grant()` is the back-pressure of the `io` interface
  (run once). It is the candidate for a streamer port that cannot accept in
  this cycle; the master side of it is in step 15.
- Long waits cost little host time: a billion stalled cycles took about 7 s.
  A program that waits on an accelerator is cheap to simulate; one that
  polls runs an instruction stream for the whole wait.
- Interconnect timing is generator arguments (`latency`, `bandwidth`), read
  from `gvsoc_config.json`: sweeping them needs no rebuild (step 12). For
  SNAX-GVSoC the platform file's link widths and path costs can go straight
  into those arguments. `synchronous=False` is another model and needs a
  build once.
- A latency says when one request is served; it does not make requests wait
  for each other. A streamer or accelerator port that serves one beat per
  cycle needs a busy-until counter like the router's limiter (or the bank
  model's `next_packet_start`), not only `inc_latency`.
- A model that issues requests itself (a streamer) has to decide what to do
  with the latency and the duration it gets back: wait for
  `get_full_latency()` before the next beat, as the loader does, or the
  bandwidth of the path has no effect on it. To look at in step 15.
- The router has no statistic for cycles lost to the bandwidth limit, and
  the bank model none for conflicts. Our L1 path needs its own counters for
  "cycles a request was delayed", per port, to feed the profiles.
- `printf` (semihosting) aborts behind an asynchronous router. If the SNAX
  model ever holds requests on the path between a core and its memory, the
  debug requests (`req->get_debug()`) must be answered at once.
