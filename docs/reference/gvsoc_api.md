# GVSoC API reference

The GVSoC classes and calls used so far, by class, with what each argument
means. GVSoC has no API documentation for most of these; the signatures were
read from the headers and tried in the tutorials. Look here for "what were
the arguments again"; look in `docs/tutorials/` for the walk-through.

Pinned to gvsoc `93cedc4`. Signatures can change with the pin.

Only what has been used is listed, not everything a header offers. The
"Checked" column says how far an entry is trusted:

- **T0** to **T7**, **T10**: built and run in that tutorial (pages in
  `docs/tutorials/`).
- **T16**: run for the tutorial 16 page, on the check machine only (step 13
  is on hold).
- **HWPE**: from the HWPE tutorial (`docs/tutorials/hwpe_accelerator.md`):
  run in its final state on the check machine, or with the small master
  written to try the calls.
- **read**: read from the source at the pin, not run.

A new step adds its classes here, as it adds an entry to `NOTES.md`.

Headers are relative to `gvsoc/engine/engine/include/`; Python files to
`gvsoc/`.

## Contents

- [Model skeleton: vp::Component](#model-skeleton-vpcomponent)
- [Memory-mapped requests: io](#memory-mapped-requests-io)
- [Issuing requests: vp::IoMaster](#issuing-requests-vpiomaster)
- [Wires](#wires)
- [Traces: vp::Trace](#traces-vptrace)
- [VCD signals: vp::Signal](#vcd-signals-vpsignal)
- [Registers: vp::Register](#registers-vpregister)
- [Register maps: vp::regmap](#register-maps-vpregmap)
- [Clock events: vp::ClockEvent](#clock-events-vpclockevent)
- [Statistics and sub-blocks](#statistics-and-sub-blocks)
- [Python generator of a component](#python-generator-of-a-component)
- [Python generator of a system](#python-generator-of-a-system)
- [gvrun options](#gvrun-options)
- [Control from Python: the proxy](#control-from-python-the-proxy)
- [Rules of thumb](#rules-of-thumb)

## Model skeleton: vp::Component

`vp/vp.hpp`, `vp/component.hpp`, `vp/block.hpp`.

```cpp
#include <vp/vp.hpp>

class MyComp : public vp::Component
{
public:
    MyComp(vp::ComponentConf &config);
};

MyComp::MyComp(vp::ComponentConf &config) : vp::Component(config) {}

extern "C" vp::Component *gv_new(vp::ComponentConf &config)
{
    return new MyComp(config);
}
```

| Call | Arguments and meaning | Checked |
|---|---|---|
| `class X : public vp::Component` | Every model. `vp::Component` derives from `vp::Block`, which holds name, path, parent, clock and traces | T1 |
| `X(vp::ComponentConf &config)` | The constructor the engine expects; pass `config` to the base class. Members without a default constructor (signals, registers, regmaps) are built in the initializer list, in declaration order | T1, T4, T5 |
| `extern "C" vp::Component *gv_new(vp::ComponentConf &config)` | The entry point of the model's library; returns `new X(config)`. Without `extern "C"` the run aborts with `couldn't find gv_new loaded module` | T1 |
| `new_slave_port(std::string name, SlavePort *port, void *comp=NULL)` | Registers an input port. `name` is what the Python generator's `SlaveItf(self, name, ...)` refers to. The instance comes back as the handler's first argument | T1 |
| `new_master_port(std::string name, vp::MasterPort *port, vp::Block *comp=NULL)` | Registers an output port, named as in the generator's `itf_bind(name, ...)` | T2 |
| `get_js_config()` | This instance's part of `gvsoc_config.json`: what the generator passed to `add_properties` | T1 |
| `get_js_config()->get_child_int("key")` | One property as an integer. A missing key returns 0 with no message. `get_child_bool`, `get_child_str` and `get("key")->get_int()` also exist | T1; the others read |
| `get_path()`, `get_name()` | `/soc/my_comp` and `my_comp` | read |
| `virtual void reset(bool active)` | Called on reset assert (`true`) and release (`false`). Override to reset model state. Signals and registers are reset by the block itself | read |
| `virtual void start()` | Called once before the simulation starts | read |

GVSoC does not check that a model's ports are bound, unless the model does
it itself.

## Memory-mapped requests: io

`vp/itf/io.hpp`. The port type behind every memory-mapped access. A request
is a direct function call from the master into the slave's handler; it takes
no simulated time unless the handler says so, with a latency or a pending
answer.

Slave side:

```cpp
#include <vp/itf/io.hpp>

static vp::IoReqStatus handle_req(vp::Block *__this, vp::IoReq *req);
vp::IoSlave input_itf;

// in the constructor
this->input_itf.set_req_meth(&MyComp::handle_req);
this->new_slave_port("input", &this->input_itf);
```

| Call | Arguments and meaning | Checked |
|---|---|---|
| `vp::IoSlave` | An input port for requests | T1 |
| `set_req_meth(vp::IoReqMeth *meth)` | Stores the handler. Its type is `vp::IoReqStatus (vp::Block *, vp::IoReq *)`; it is `static`, and the first argument is the instance, to be cast back | T1 |
| `req->get_addr()` | `uint64_t`. The address of the access. Behind a router mapping with `rm_base=True` it is the offset inside the component's window | T1 |
| `req->get_size()` | `uint64_t`. Number of bytes: 4 for `lw` / `sw`, 1 for `lbu` / `sb`, 8 for `ld` / `sd`. GCC splits a misaligned access into smaller ones | T1, T5 |
| `req->get_is_write()` | `bool`. `true` for a store, `false` for a load | T1 |
| `req->get_data()` | `uint8_t *`. The master's data: read from it on a store, write into it on a load. For a load from the core it points at the destination register itself | T1 |
| `req->get_opcode()` | `IoReqOpcode`: `READ`, `WRITE`, and the atomics `LR`, `SC`, `SWAP`, `ADD`, ... | read |
| return `vp::IO_REQ_OK` | The request is done, now | T1 |
| return `vp::IO_REQ_INVALID` | Error. The RV64 core takes a load or store fault; the tutorial runtime exits 1 and `gvrun` prints `Platform returned an error (exitcode: 1)` with no address. Not checked on Snitch | T1 |
| return `vp::IO_REQ_PENDING` | Accepted, not done. The request belongs to the slave until it calls `resp(req)`, exactly once. The core is stalled at the instruction, for a load and for a store. Keep the `vp::IoReq *`; it stays valid until the answer | T7 |
| `req->get_resp_port()->resp(req)` | The answer to a pending request. `get_resp_port()` is the `vp::IoSlave *` the request came in through, stored in the request by the master's `req()`. Write the data before the call. Never calling it hangs the run with no message; calling it twice aborts with `Trying to decrease zero stalled counter` | T7 |
| return `vp::IO_REQ_DENIED`, then `req->get_resp_port()->grant(req)` | Not accepted now. `grant(req)` later means accepted; `resp(req)` after that ends the request. The core is stalled throughout | T7, one run |
| `req->inc_latency(uint64_t n)` | Adds `n` cycles to the request's latency, with a synchronous `IO_REQ_OK`. Only a number in the request: no event, no state in the model. Every component on the path can add its own | T7 |
| `req->set_latency(n)` | Keeps the larger of the current latency and `n` | T7 |
| `req->get_latency()` | What earlier components on the path have put there; 0 behind a router without latency | T7 |
| `req->set_duration(uint64_t n)`, `get_duration()` | The second timing field: how many cycles the transfer itself takes. `set_duration` keeps the larger value. A router with a bandwidth and the memory model set it | T10 through the router; the calls read |
| `req->get_full_latency()` | Latency plus duration: what a master waits when it accounts for the whole transfer. The loader uses it; the RV64 core reads only `get_latency()` | T10 through the loader; the call read |
| `req->is_debug()` | `true` for an access that should not count for timing (the proxy's accesses, semihosting). The memory model skips its timing for it; the router does not look at it | T16, HWPE |

What a latency does is up to the master. Measured on the tutorial's RV64
core (T7): a load's latency does not stall the load; the destination
register becomes valid later, and the core stalls at the first instruction
that reads it (next instruction at load cycle + latency + 3). A store's
latency is ignored. A latency set before `resp()` on a pending load adds to
the wait. Not measured on the Snitch core, which takes other branches of
`gvsoc/core/models/cpu/iss/src/lsu.cpp`.

An unanswered load keeps what was in the destination: `lw` returns the old
register value, `lbu` returns 0 (T1).

## Issuing requests: vp::IoMaster

`vp/itf/io.hpp`. The other end of an `io` binding: a component that sends
requests itself (an accelerator's port into L1, a streamer, a DMA).

```cpp
vp::IoMaster out_itf;
vp::IoReq req;                 // one object per request in flight
uint32_t data;

static void handle_resp(vp::Block *__this, vp::IoReq *req);
static void handle_grant(vp::Block *__this, vp::IoReq *req);

// in the constructor
this->out_itf.set_resp_meth(&MyMaster::handle_resp);
this->out_itf.set_grant_meth(&MyMaster::handle_grant);
this->new_master_port("out", &this->out_itf);

// to send
this->req.init();
this->req.set_addr(addr);
this->req.set_size(4);
this->req.set_is_write(false);
this->req.set_data((uint8_t *)&this->data);
vp::IoReqStatus status = this->out_itf.req(&this->req);
```

| Call | Arguments and meaning | Checked |
|---|---|---|
| `vp::IoMaster` | An output port for requests. Declared with `new_master_port(name, &port)`; in the generator `self.itf_bind(name, slave_itf, signature='io')` | HWPE |
| `vp::IoReq` | The request object. It belongs to the master; the slave works on it and may keep a pointer until it answers. One object means one request in flight | HWPE |
| `req.init()` | Sets latency and duration to 0 and clears the debug flag and the argument stack. Before every reuse | HWPE |
| `req.set_addr(uint64_t)`, `set_size(uint64_t)`, `set_is_write(bool)` | The access. The address is what the bound slave expects: a bus address into a router, an offset into an interleaver or a memory | HWPE |
| `req.set_data(uint8_t *)` | The master's buffer: source of a write, destination of a read. It must stay valid until the answer | HWPE |
| `req.set_debug(true)` | Marks the access as not counting for timing; the memory model then skips its bank timing | read (the HWPE model does it for its weights) |
| `port.req(&req)` | Sends the request: a direct call into the slave's handler. Returns `IO_REQ_OK` (0), `IO_REQ_INVALID` (1), `IO_REQ_DENIED` (2) or `IO_REQ_PENDING` (3) | HWPE, all four |
| After `IO_REQ_OK` | The data is in the buffer. `req.get_latency()` is what the path charged, `req.get_duration()` the length of the transfer behind a bandwidth or a bank width. Waiting is up to the master | HWPE |
| After `IO_REQ_INVALID` | Nothing else happens: no message, no fault. From a router for an unmapped address, or from the slave | HWPE |
| `set_resp_meth(void (*)(vp::Block *, vp::IoReq *))` | The callback for the answer to a pending or denied request. It gets the master's own request object back, with the data in and a latency that may be non-zero. Not set: an empty default, so the answer is lost with no message | HWPE |
| `set_grant_meth(void (*)(vp::Block *, vp::IoReq *))` | The callback for `grant()` after `IO_REQ_DENIED`: the slave has now accepted the request; the response follows | HWPE |
| `req.get_addr()` after the call | What the path made of it: a router subtracts its mapping's base in the request. Keep the address in the model | HWPE |
| `port.is_bound()` | `false` when nothing is bound | read |
| `port.req_forward(&req)` | For a component in the middle (router, interleaver): passes a request on and leaves the response port as it is, so the answer goes back to the first master | read |

The stock accelerator models (HWPE tutorial, datamover) issue all requests
of a phase in one call, keep the largest latency and wait that plus one
cycle; they treat any answer but OK as fatal. A master that sends one beat
per cycle waits `get_latency() + 1` cycles after an OK, or for the response
callback after a pending answer.

## Wires

`vp/itf/wire.hpp`, implementation in `vp/itf/implem/wire_class.hpp`. A typed
point-to-point signal. `sync` is a direct call into the receiver's handler:
no event, no delay, no stored value.

```cpp
#include <vp/itf/wire.hpp>

vp::WireMaster<bool> notif_itf;                                   // output
vp::WireSlave<bool> in_itf;                                       // input
static void handle_in(vp::Block *__this, bool value);

// in the constructor
this->new_master_port("notif", &this->notif_itf);
this->in_itf.set_sync_meth(&MyComp::handle_in);
this->new_slave_port("in", &this->in_itf);
```

| Call | Arguments and meaning | Checked |
|---|---|---|
| `vp::WireMaster<T>` | An output of type `T`. `T` can be a pointer to a class of your own | T2 |
| `master.sync(T value)` | Sends the value: calls the handler of every bound slave, now, nested inside the caller | T2 |
| `master.is_bound()` | `false` when nothing is bound. `sync()` on an unbound master crashes with a segmentation fault, so guard optional outputs | T2 |
| `vp::WireSlave<T>` | An input of type `T` | T2 |
| `slave.set_sync_meth(void (*)(vp::Block *, T value))` | Stores the handler; static, the instance as first argument | T2 |
| `set_sync_meth_muxed(void (*)(vp::Block *, T, int), int id)` | One handler for an array of ports, with the port index as third argument (the stock cluster registers use it for one wire per core) | read |
| `sync_back`, `set_sync_back_meth` | The slave returning a value through a pointer | read |

The signature string in the generator (`'wire<bool>'`) is only a label both
ends must match; GVSoC never compares it with the C++ types. One master can
be bound to several slaves. A pointer sent on a wire that points into the
sender's stack is only valid during the handler.

## Traces: vp::Trace

`vp/trace/trace.hpp`, `vp/trace/block_trace.hpp`. Text lines that GVSoC
prints only when asked, with time, cycle and path in front.

```cpp
vp::Trace trace;

// in the constructor
this->traces.new_trace("trace", &this->trace);

// anywhere
this->trace.msg(vp::TraceLevel::DEBUG, "Received request at offset 0x%lx\n", req->get_addr());
```

| Call | Arguments and meaning | Checked |
|---|---|---|
| `traces.new_trace(std::string name, Trace *trace, TraceLevel level = vp::TraceLevel::DEBUG)` | Registers a trace. Its path is the component path plus `name`. `level` is the default level of `msg()` calls without one. A model can have several, each with its own name | T3 |
| `trace.msg(int level, const char *fmt, ...)` | Prints when the trace is enabled and the level passes. `printf` format; GVSoC adds the header | T3 |
| `trace.msg(const char *fmt, ...)` | Same, at the trace's default level | read |
| Levels | `vp::TraceLevel::ERROR`, `WARNING`, `INFO`, `DEBUG`, `TRACE`, from least to most detail | T3 |
| `trace.warning(fmt, ...)`, `trace.fatal(fmt, ...)` | A warning, an error that stops the run | read |
| `vp_warning_always(trace_ptr, fmt, ...)` | A warning printed whatever the options. With the default `werror` it ends the run with exit code 1; `--no-werror` lets it go on. `vp::regmap` uses it for an unknown offset | T5 |

Every component already has a trace called `trace` from `vp::Block` and one
called `comp`; give your own traces other names. Traces are compiled out of
the default build: any `--trace`, `--vcd` or `--event` switches the run to
the debug build, about 3.5 times slower.

## VCD signals: vp::Signal

`vp/signal.hpp`. A value that is written to the VCD file on every change.

```cpp
#include <vp/signal.hpp>

vp::Signal<uint32_t> vcd_value;

// in the initializer list
vcd_value(*this, "status", 32)
```

| Call | Arguments and meaning | Checked |
|---|---|---|
| `Signal(Block &parent, std::string name, int width, bool do_reset=true, T reset=0)` | Parent block, name (the VCD path is the component path plus `name`), width in bits, whether it is reset, reset value. `T` must be at least `width` bits wide | T4 |
| `Signal(Block &parent, std::string name, int width, ResetKind reset_kind, T reset_value=0)` | Same, with `ResetKind::HighZ` to start as `z` | read |
| `set(T value, int64_t cycle_delay=0, int64_t time_delay=0)` | Stores the value and dumps a change, now or after a delay | T4 without the delays |
| `get()` | The current value, so a signal can also be model state | read |
| `release(...)` | Dumps `z` (high impedance), for example for an idle period | T4 |
| `set_and_release(T value, ...)` | The value for one cycle, then `z`: a pulse | read |
| `inc(T value)`, `dec(T value)` | Change by `value` | read |

A signal also has a text trace at `TRACE` level, `<path>/trace`. Nothing is
dumped without `--vcd` and an `--event` expression that matches the path.

## Registers: vp::Register

`vp/register.hpp`, `engine/engine/src/register.cpp`. A value with a name,
partial access, a trace and a VCD signal.

```cpp
vp::Register<uint32_t> my_reg;

// in the initializer list
my_reg(*this, "my_reg", 32)

// in the request handler, for a register at offset 8
_this->my_reg.update(req->get_addr() - 8, req->get_size(), req->get_data(), req->get_is_write());
```

| Call | Arguments and meaning | Checked |
|---|---|---|
| `Register(Block &parent, std::string name, int width, bool do_reset=false, T reset_val=0)` | Parent block, name (path: component path plus `name`), width in bits, whether the block's reset writes `reset_val` into it. `T` holds the value: `uint8_t` to `uint64_t` | T5; `do_reset` through the generated classes |
| `update(uint64_t reg_offset, int size, uint8_t *value, bool is_write)` | The read or write of an access. `reg_offset`: byte offset inside the register, not a bus address. `size`: number of bytes. `value`: the request's data pointer, source on a write and destination on a read. `is_write`: the direction; with `false` it copies the register out. A `memcpy`, with no check that `reg_offset + size` fits the width | T5 |
| `get()` | The full value | T5 |
| `set(T value)` | Sets the full value, with trace and VCD change. Does not go through the callback | T5 |
| `set_field(T value, int offset, int width)`, `get_field(int offset, int width)` | One bit field; what the generated `<field>_set` / `<field>_get` call | T5 through the generated accessors |
| `inc(T)`, `dec(T)`, `=`, `\|=`, `&=`, conversion to `T` | Shorthands for `set` and `get` | read |
| `register_callback(std::function<void(uint64_t, int, uint8_t *, bool)> callback, bool exec_on_reset=false)` | `callback(reg_offset, size, value, is_write)` replaces the default handling in `access`, for loads and stores. It must call `update` itself to do the read or write. `exec_on_reset`: also call it when the register is reset, as a write of the reset value | T5 |
| `access(uint64_t reg_offset, int size, uint8_t *value, bool is_write)` | The callback when there is one, `update` otherwise. This is what `vp::regmap::access` calls; use it in place of `update` when a hand-placed register has a callback | T5 through the regmap |
| `release()` | Shows the register as `z` in the VCD | read |

Traces: `<path>/trace`, with `Modified register (value: ...)` at `TRACE`
level. Measured in T5: a 1-byte store at `reg_offset` 1 replaces one byte;
an 8-byte store into a 32-bit register is accepted and writes past the
value; a `write_mask` exists but `write` does not apply it, so read-only
needs a callback.

## Register maps: vp::regmap

`vp/register.hpp`, generated classes from `regmap-gen`. The tool, its input
format and a full example are in `docs/reference/regmap.md`.

```cpp
#include "headers/mycomp_regfields.h"      // first: the macros
#include "headers/mycomp_gvsoc.h"          // then the classes that use them

vp_regmap_regmap regmap;

// in the initializer list
regmap(*this, "regmap")

// in the constructor
this->regmap.build(this, &this->trace);
```

| Call | Arguments and meaning | Checked |
|---|---|---|
| `vp_regmap_<name>` | The generated map class, a `vp::regmap`, which is a `vp::Block`. `<name>` is `regmap-gen --name`, default `regmap` | T5 |
| `vp_regmap_<name>(vp::Block &top, std::string name)` | Parent and name. Registers get the paths `<component>/<name>/<register>` | T5 |
| `regmap.<register>` | One member per register, lower case: a `vp::Register<T>` with name, offset, width, reset value and fields filled in, built with `do_reset` on | T5 |
| `regmap.<register>.<field>_get()`, `<field>_set(v)` | Field accessors | T5 |
| `build(vp::Block *comp, vp::Trace *trace, std::string name="")` | Stores the trace on which an unknown offset is reported | T5; no visible effect when left out, the abort without it is read |
| `access(uint64_t offset, int size, uint8_t *value, bool is_write)` | `offset` is relative to the start of the map. Finds the register with `reg.offset <= offset` and `offset + size <= reg.offset + width/8`, and calls its `access` with the offset inside the register. Returns `false` when a register was found, `true` when not, after `Accessing invalid register (...)`, which with the default `werror` ends the run | T5 |

Traces: `<register path>/trace`, with `Register access (name: ..., value: {
FIELD=... })` at `DEBUG` level.

## Clock events: vp::ClockEvent

`vp/clock/clock_event.hpp` (every method is commented there),
`engine/engine/src/clock/clock_engine.cpp`. A function call that the clock
engine makes for the model at a later cycle. The only way a model gets a
duration of its own.

```cpp
static void handle_event(vp::Block *__this, vp::ClockEvent *event);
vp::ClockEvent event;

// in the initializer list
event(this, MyComp::handle_event)

// anywhere
this->event.enqueue(10);
```

| Call | Arguments and meaning | Checked |
|---|---|---|
| `ClockEvent(Block *comp, ClockEventMeth *meth)` | Owner block, which gives the event its clock, and the callback. No default constructor, so it goes in the initializer list | T6 |
| Callback: `void (vp::Block *__this, vp::ClockEvent *event)` | Static; the instance as first argument, the event that fired as second | T6 |
| `enqueue(int64_t cycles = 1)` | Calls the callback once, `cycles` cycles of the owner's clock from now, and returns at once. 0 runs it in the current cycle. On an event that is already pending: ignored when the new cycle is later or equal, replaces the pending one when it is earlier. One event holds one pending call | T6 |
| `is_enqueued()` | `true` from the enqueue until the callback starts or the event is cancelled; `false` inside the callback, so the callback can enqueue again | T6 |
| `cancel()` | Removes a pending call. Allowed when nothing is pending | T6; the second half read |
| `enable()` / `disable()` | The other way to use an event: the callback runs at every cycle, from the cycle after `enable()` until `disable()`. Do not mix with `enqueue` on the same event | T6 |
| `stall_cycle_set(n)`, `stall_cycle_inc(n)`, `stall_cycle_get()` | For an enabled event: skip the next `n` cycles | read |
| `get_args()` | `void **`, 8 slots for the model's own use, carried from the enqueue to the callback. They belong to the event: a second enqueue overwrites them | T6 |
| `set_callback(meth)`, `exec()` | Change the callback; run it now | read |
| `this->clock.get_cycles()` | In a model: the current cycle of its clock, `int64_t` | T6 |
| `this->clock.get_period()`, `get_frequency()` | Period in ps, frequency in Hz | read |

A pending event does not keep the simulation alive: the run ends when the
program exits, and what is still pending never runs. An event enabled at
every cycle with an empty callback cost about 25 % of run time on the
tutorial system (T6). The core is itself a clock event callback
(`Exec::exec_instr`; read).

Pattern for several operations in flight: keep a list of pending results
ordered by ready cycle, and one event set for the earliest entry
(`docs/tutorials/6_timing.md`, "Beyond the tutorial").

## Statistics and sub-blocks

| Call | Meaning | Checked |
|---|---|---|
| `this->stats.register_stat(StatCommon *stat, name, desc)` | Registers a counter; `--stats` writes all of them to `build/work/stats.txt` at the end of the run. Example in `gvsoc/core/models/memory/memory.cpp` | read; `--stats` output seen in T3 |
| A class derived from `vp::Block`, built with a parent and a name | A sub-unit inside one model: own path, traces, registers and clock events, no bindable ports. `vp::regmap` is one; the Snitch fast core's `Ssr` is another | T5 for `vp::regmap`; otherwise read |
| `std::string handle_command(gv::GvProxy *proxy, FILE *req_file, FILE *reply_file, std::vector<std::string> args, std::string req) override` | A virtual method of every block (`vp/block.hpp`, with `#include <vp/proxy.hpp>`). Called for the proxy command `component <handle> <args...>`; the returned string is the reply. The router implements `mem_read` and `mem_write` this way | T16 |

## Python generator of a component

`engine/python/gvsoc/systree_gvrun2.py`, imported as `gvsoc.systree`.

```python
import gvsoc.systree

class MyComp(gvsoc.systree.Component):
    def __init__(self, parent: gvsoc.systree.Component, name: str, value: int):
        super().__init__(parent, name)
        self.add_sources(['my_comp.cpp'])
        self.add_properties({"value": value})

    def i_INPUT(self) -> gvsoc.systree.SlaveItf:
        return gvsoc.systree.SlaveItf(self, 'input', signature='io')

    def o_NOTIF(self, itf: gvsoc.systree.SlaveItf):
        self.itf_bind('notif', itf, signature='wire<bool>')
```

| Call | Arguments and meaning | Checked |
|---|---|---|
| `Component.__init__(parent, name)` | Places the instance in the tree; its path is the parent's path plus `name` | T0, T1 |
| `add_sources([...])` | The C++ files of the model, relative to a module root. One library per set of sources and flags, named by a hash of the names, not the content. A component without sources is a pure container | T1 |
| `add_properties({...})` | Values for this instance, written to `gvsoc_config.json` and read in C++ with `get_js_config()`. Changing a value needs no rebuild | T1 |
| `gvsoc.systree.SlaveItf(self, 'name', signature='io')` | Describes an input port; `name` must be the name in `new_slave_port`. By convention returned by a method `i_NAME()` | T1 |
| `self.itf_bind('name', slave_itf, signature='...')` | Binds this component's output `name` (as in `new_master_port`) to another component's input. By convention inside a method `o_NAME(itf)` | T2 |
| Signatures | `'io'`, `'wire<bool>'`, `'wire<MyClass *>'`. A label: a mismatch between the two ends is `Invalid signature`, but the C++ types are not checked | T1, T2 |
| `self.bind(self, 'in_0', child, 'in_0')` | In a container, forwards its own port to a child, as `snitch_cluster.py` does | read |
| `def gen(self, builddir, installdir)` | Called for every component during `make gvsoc`, before the models compile. Used to generate headers, for example a register map | T5 |
| `def gen_gtkw(self, tree, comp_traces)` | Called when `gvrun` writes the GTKWave script; `tree.add_trace(self, self.name, vcd_signal='status[31:0]', tag='overview')` puts a signal in the prepared view. It does not decide what is dumped | T4 |

What GVSoC checks on a binding (T0): a misspelled method is a Python
`AttributeError`; a signature mismatch is `Invalid signature`; a port name
the C++ model does not have is `Binding from invalid slave port`. A missing
binding is not reported.

## Python generator of a system

The stock components used by the tutorial system `my_system.py`. Paths are
under `core/models/`.

| Component | Arguments and ports used | Checked |
|---|---|---|
| `vp.clock_domain.Clock_domain(parent, name, frequency)` | A clock generator, `frequency` in Hz. `clock.o_CLOCK(soc.i_CLOCK())` gives the clock to a component and everything under it | T0 |
| `interco.router.Router(parent, name, latency=0, bandwidth=0, synchronous=True, shared_rw_bandwidth=False, max_input_pending_size=0)` | A memory-mapped router. `latency`: cycles added to every request. `bandwidth`: bytes per cycle, 0 for no limit; a request takes the router for `ceil(size / bandwidth)` cycles and one that arrives meanwhile gets the remaining cycles as latency. `shared_rw_bandwidth`: one counter for reads and writes where there are two. `synchronous=False`: another C++ model that holds requests and answers later; needs a build, ignores latencies, breaks semihosting `printf`. `max_input_pending_size`: input FIFO of the asynchronous router | T0; `latency`, `bandwidth`, `shared_rw_bandwidth`, `synchronous` T10; the last one read |
| `ico.i_INPUT(id=0)` | The input port `input`, or `input_<id>`. Several masters can bind to one input and then share its bandwidth limiter; an `id` of its own gives a master its own limiter | T0; `id` T10 |
| `ico.o_MAP(itf, name=None, base=0, size=0, rm_base=True, remove_offset=0, latency=0)` | Maps `base .. base+size-1` to a slave. `rm_base`: subtract `base`, so the slave sees an offset. `latency`: cycles added to every request through this mapping, on top of the router's. Each mapping has its own bandwidth limiter | T0, T1; `latency` T10 |
| `memory.memory.Memory(parent, name, size)` | A memory of `size` bytes; `mem.i_INPUT()` | T0 |
| `cpu.iss.riscv.Riscv(parent, name, isa='rv64imafdc', binaries=[binary])` | The RV64 core, modelled by the instruction set simulator. `o_FETCH(itf)`, `o_DATA(itf)` (mandatory), `o_DATA_DEBUG(itf)` (GDB only), `i_FETCHEN()`, `i_ENTRY()` | T0 |
| `utils.loader.loader.ElfLoader(parent, name, binary=binary)` | Writes the ELF through `o_OUT(itf)`, then starts the core through `o_START(itf)` and `o_ENTRY(itf)`. Without these two the simulation never ends | T0 |
| `gvrun.parameter.TargetParameter(self, name='binary', value=None, description='...').get_value()` | A parameter of the target, set on the command line with `--parameter binary=<elf>` | T0 |
| `class Target(gvsoc.runner.Target)` with `model`, `name`, `description` | The top that `gvrun --target-dir=<dir> --target=<file name>` instantiates | T0 |

Router timing (T10, `docs/tutorials/10_interconnect_timing.md`): the
synchronous router forwards a request inside the master's call and only
writes `latency` and `duration` into it. A request passes the limiter of its
input port, then the one of its mapping. A request that finds the router
free gets latency 0, so the bandwidth limits a flow and is not a cost per
access. `latency`, `bandwidth` and the mappings are properties: changing
them needs no rebuild. Fetches and the loader's write go through the router
like data.

The generator runs twice: at build time, to list the models to compile, and
at run time, to write `build/work/gvsoc_config.json`. A change of values or
of the tree needs no rebuild as long as every model variant is already
compiled.

## gvrun options

Passed in the tutorials as `make run runner_args="..."`.

| Option | Effect | Checked |
|---|---|---|
| `--parameter binary=<elf>` | Sets a `TargetParameter` | T0 |
| `--trace=REGEX` | Enables the traces whose path matches; can be given several times. `REGEX:file` writes them to a file in the work directory | T3 |
| `--trace-level=error\|warning\|info\|debug\|trace` | The most detailed level that is printed | T3 |
| `--vcd` | Writes `build/work/all.vcd` and `view.gtkw` | T4 |
| `--event=REGEX` | Which signals are dumped. `--vcd` alone dumps almost nothing | T4 |
| `--stats` | Writes `build/work/stats.txt`; uses the profile build, about 2.7 times slower | T3 |
| `--no-werror` | A model warning no longer ends the run | T5 |
| `--debug-mode` | Uses the debug build without any `--trace`, so traces can be switched on later through the proxy | T16 |
| `--proxy`, `--proxy-port=<n>`, `--control-script=<file>` | See "Control from Python: the proxy" | T16 |

## Control from Python: the proxy

`engine/python/gvsoc/gvsoc_control.py` (installed in
`build/install/python`, on `PYTHONPATH` after `sourceme.sh`), engine side in
`engine/engine/src/proxy.cpp`. Walk-through and the rough edges in
`docs/tutorials/16_python_control.md`.

| Call | Arguments and meaning | Checked |
|---|---|---|
| `gvrun ... run --proxy --proxy-port=<n>` | Starts GVSoC with the proxy; it prints `Opened proxy on socket <n>` and waits for a client. Default port 42951 | T16 |
| `gvrun ... run --control-script=<file.py>` | Starts GVSoC on a free port, connects and calls `target_control(proxy)` of the file; its return value is the exit status | T16 |
| `gvsoc.Proxy(host='localhost', port=42951)` | Connects (`import gvsoc.gvsoc_control as gvsoc`) | T16 |
| `gv.run(duration)` | Runs for `duration` picoseconds and returns when stopped. Without a duration: starts and returns at once | T16 |
| `gv.step_cycles(clock_index, n)` | Runs `n` cycles of one clock; the index is the position in `gv.get_clock_domains()`. Returns the time in ps as a string | T16 |
| `gv.stop()`, `gv.join()` | Halts a running simulation; waits for the program to exit and returns its exit code | T16 |
| `gv.quit(status)`, `gv.terminate()`, `gv.close()` | This client leaves; force the simulation to end; close the socket. GVSoC exits when the simulation is over and every client has quit | T16 |
| `gv.reader.timestamp` | The time of the last stop, in ps | T16 |
| `gvsoc.Router(gv, path='**/soc/ico')` | A handle on a router. A path that matches nothing gives handle `0x0` and crashes GVSoC on the first command | T16 |
| `r.mem_read(addr, size)`, `r.mem_write(addr, size, bytes)`, `mem_read_int`, `mem_write_int` | An access through the router's own routing, with the debug flag. A read of an unmapped address returns garbage with no error | T16 |
| `gv._get_component(path)`, `gv._send_cmd('component %s <args>' % handle)` | The two calls under every wrapper class: a handle for a path, and a command to that component's `handle_command`. The reply string is returned | T16 |
| `gv.trace_add(regex)`, `trace_remove`, `trace_level` | Traces at run time; only with `--debug-mode` | T16 |
| `gv.event_add(regex)` | Never returns at the pin | T16 |

Each step and memory access takes 44 ms of host time unless the client
socket has `TCP_QUICKACK` set before each read and `TCP_NODELAY` set (code
in the tutorial page).

## Rules of thumb

- A request, a wire `sync` and a register access are plain function calls.
  They happen inside the caller and take no simulated time. Time comes from
  latency on a request (tutorial 7) or from a clock event (tutorial 6).
- Compute a result at once and delay only its arrival: the function is
  plain C++, the timing is the number given to `enqueue`.
- To make the core wait on an access: a latency for a fixed cost on a load,
  `IO_REQ_PENDING` and `resp()` when the wait depends on the model's state
  or when the access is a store. Every pending request needs exactly one
  `resp()`.
- Have the model's state consistent before driving a wire: the callee may
  call back into it.
- Check mandatory ports and properties in the model. GVSoC reports neither
  an unbound port nor a missing property.
- Return `IO_REQ_INVALID` for offsets and sizes the model does not serve, so
  a wrong access traps instead of reading stale data.
- Guard optional output wires with `is_bound()`.
- Give traces, signals and registers their own names; `trace` and `comp`
  are taken by the base classes.
- A latency delays one request; it does not make requests wait for each
  other. Something that serves one thing at a time needs a busy-until
  counter, as the router's bandwidth limiter has.
- One request object per request in flight. `init()` it before every reuse,
  and keep the address in the model.
- A master either handles all four answers of `req()` or checks in one place
  that its path can only answer OK. Unset response and grant callbacks lose
  the answer with no message.
- Profiling runs use no `--trace`, `--vcd` or `--event`. Numbers that are
  needed in every run are statistics.
