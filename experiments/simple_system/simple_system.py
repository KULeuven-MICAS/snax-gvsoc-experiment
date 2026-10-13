import gvsoc.systree
import gvsoc.runner

import cpu.iss.riscv
import memory.memory
import vp.clock_domain
import interco.router
import utils.loader.loader
import gdbserver.gdbserver
from gvrun.parameter import TargetParameter

GAPY_TARGET = True

# Define SoC class, coming from a parent class gvsoc.systree.Component
class SoC(gvsoc.systree.Component):

    # Define the constructor for the SoC class
    # So what it expects when you make this
    def __init__(self, parent, name, binary):
        # Calls the constructor of the parent class, so
        # it initializes the SoC with the given parent, name, and binary file.
        super().__init__(parent, name)

        # Create main memory
        # Arguments are: name, and size. Check gvsoc model for more details
        mem = memory.memory.Memory(self, 'mem', size=0x00100000)

        # Crate the main interconnect. This is a normal "crossbar" if you think about it.
        # According to the documents it's an AXI-like router.
        # Inputs one for independent intiators (requesters),
        # Outputs go toward the memory
        # The argument is the name
        # Other arguments include:
        # - latency: global latency
        # - bandwidth: bytes per cycle
        # - sycnyronous: true if the router is synchronous
        # So much more so check the documentations
        ico = interco.router.Router(self, 'ico')

        # Connect the memory into the interconnect
        # o_MAP: Technically it binds the output to a memory region
        # The arguments are: 
        # - name
        # - base address of targe memory area
        # - size of target memory area
        # - rmbase: if true the base address is subtracted to the address of any request going throgh the mapping
        # also has latency and so on
        # i_INPUT: Returns the input port.
        # Incoming requests to be handled by the memory should be sent to this port.
        ico.o_MAP(mem.i_INPUT(), 'mem', base=0x00000000, size = 0x00100000, rm_base=True)


        # Instantiating the host
        # Arguments are:
        # - name
        # - isa: string describing the isa to be simulated
        # - binaries: list of binary files to be simulated
        # also has fetch_enable, boot_addr, timed, and core_id. So check the source.
        host = cpu.iss.riscv.Riscv(self, 'host', isa='rv64imafdc', binaries=[binary])
        # Make the connections from the output of the host towards the input of the interconnects
        # Recall that inputs to interconnect are the "requesters" or initiators
        # These ones are actually inherited from RiscvCommon class
        # Binds the fetch port. This port is used for fetching instructions from memory.
        host.o_FETCH (ico.i_INPUT())
        # Binds the data port. This port is used for issuing data accesses to the memory.
        host.o_DATA (ico.i_INPUT())
        # Binds the data debug port. This port is used for issuing data accesses from gdb server to the memory.
        host.o_DATA_DEBUG(ico.i_INPUT())

        # Connect the ELF loader
        # This model can be used to load an ELF binary from the workstation into a simulated memory.
        # Arguments are:
        # - name
        # - binary: path to the ELF binary file to be loaded
        #  Then optional entry, and entry_addr see the main documents
        loader = utils.loader.loader.ElfLoader(self, 'loader', binary=binary)
        # Some connections from output of loader that needs to be connected to other modules
        # o_OUT: Binds the output port. This ports is used by the loader to inject memory requests to transfer the binary into the target memory
        loader.o_OUT(ico.i_INPUT())
        # o_START: Binds the fetch enable port. This ports is used by the loader to tell to another component that the loading is done, so that for example a core starts execution.
        # i_FETCHEN: Returns the fetch enable port. This can be used to control whether the core should execute instructions or not.
        loader.o_START(host.i_FETCHEN())
        # o_ENTRY: Binds the entry port. This ports is used by the loader to tell to another component what is the entry point of
        # the loaded binary so that for example a core starts execution directly at the entry point.
        # i_ENTRY: Returns the boot address port. This can be used to set the address of the first instruction to be executed,
        #  i.e. when the core executes instructions for the first time, or after reset.
        loader.o_ENTRY(host.i_ENTRY())

        # added to attach a GDB server
        gdbserver.gdbserver.Gdbserver(self, 'gdbserver')

# This is a wrapping component of the real one in order to connect a clock generator to it
# so that it automatically propagate to other components
# Think of it like the top system where we attach inputs and the clock generation
class topSys(gvsoc.systree.Component):
    def __init__(self, parent, name=None):
        super().__init__(parent, name)

        binary = TargetParameter(
            self, name='binary', value=None, description='Binary to be simulated'
        ).get_value()

        clock = vp.clock_domain.Clock_domain(self, 'clock', frequency=100000000)
        soc = SoC(self, 'soc', binary)
        # o_CLOCK: Binds the output clock port. This port can be connected to any component which should be clocked by this clock generator.
        # i_CLOCK: Returns the clock port. A clock generator should be bound on this port if this component is clocked.
        clock.o_CLOCK(soc.i_CLOCK())

# This is the top target that gapy will instantiate
class Target(gvsoc.runner.Target):
    gapy_description = "Simple system test"
    model = topSys
    name = "test"


    
