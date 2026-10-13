# Include a useful set of utils. Run-time make.
UTILS_DIR = ../../tutorials/utils/
RT_SRCS = $(UTILS_DIR)init.c $(UTILS_DIR)crt0.S $(UTILS_DIR)alloc.c $(UTILS_DIR)io.c $(UTILS_DIR)prf.c $(UTILS_DIR)string.c $(UTILS_DIR)fprintf.c
RT_FLAGS = -march=rv64imafdc -O3 -fno-tree-loop-distribute-patterns -I$(UTILS_DIR) -T$(UTILS_DIR)link.ld -nostartfiles -nostdlib -Wl,--no-warn-rwx-segments

# Need to run this on every new container
# source gvsoc/sourceme.sh

# Note that this is relative to the container
GVSOC_ROOT=$(CURDIR)/../../gvsoc/
GVSOC_WORKDIR=$(CURDIR)/build

ifdef BUILDDIR
FULL_BUILDDIR := $(GVSOC_WORKDIR)/$(BUILDDIR)
else
FULL_BUILDDIR := $(GVSOC_WORKDIR)
endif

clean:
	rm -rf $(FULL_BUILDDIR)/test
	make -C $(GVSOC_ROOT) TARGETS=simple_system MODULES=$(CURDIR) BUILDDIR=$(FULL_BUILDDIR)/build INSTALLDIR=$(FULL_BUILDDIR)/install $(OPTIONS) clean

# Note that RT_SRCS and RT_FLAGS come from the utils/rt.mk file included at the top
# The -g option generates the default level of debugging information (usually level 2) using the standard DWARF format natively used by RISC-V.
all:
	mkdir -p $(FULL_BUILDDIR)/test
	riscv64-unknown-elf-gcc -g -o $(FULL_BUILDDIR)/test/test main.c $(RT_SRCS) $(RT_FLAGS)

# The TARGETS needs to align with the .py system you are using
gvsoc:
	make -C $(GVSOC_ROOT) TARGETS=simple_system MODULES=$(CURDIR) BUILDDIR=$(FULL_BUILDDIR)/build INSTALLDIR=$(FULL_BUILDDIR)/install $(OPTIONS) build

run:
	$(FULL_BUILDDIR)/install/bin/gvrun --target-dir=$(CURDIR) --target=simple_system --work-dir=$(FULL_BUILDDIR)/work --parameter binary=$(FULL_BUILDDIR)/test/test run $(runner_args)

print:
	@echo "GVSOC_ROOT=$(GVSOC_ROOT)"
	@echo "GVSOC_WORKDIR=$(GVSOC_WORKDIR)"
	@echo "FULL_BUILDDIR=$(FULL_BUILDDIR)"


