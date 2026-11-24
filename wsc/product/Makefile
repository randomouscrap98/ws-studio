# WSC product ROM. Builds a WonderSwan Color image from a GB Studio export
# with the portable engine and no test scenes, test scripts or boot table.
#
# Usually driven by the CLI's `make:wsc` command or wsc/tools/build_product.sh:
#   make -C wsc/product EXPORT_DIR=... PROJECT_DIR=... ROM=... BUILDDIR=...

PYTHON ?= python3

PRODUCT_DIR	:= $(CURDIR)/
include $(PRODUCT_DIR)../engine.mk
WSC_DIR		:= $(PRODUCT_DIR)../

EXPORT_DIR	?= $(WSC_DIR)build/product/export
PROJECT_DIR	?= $(ROOT_DIR)
GEN_DIR		?= $(WSC_DIR)build/product/gen
S2C_DIR		:= $(GEN_DIR)/s2c
S2C_NAME	:= product
S2C_H		:= $(S2C_DIR)/$(S2C_NAME).h
S2C_C		:= $(S2C_DIR)/$(S2C_NAME).c
D2C_STAMP	:= $(GEN_DIR)/d2c.stamp

BUILDDIR	?= $(WSC_DIR)build/product/build
OBJDIR		:= $(BUILDDIR)/obj
ROM		?= $(BUILDDIR)/product.wsc
ELF		:= $(BUILDDIR)/product.elf
STAGE		:= $(BUILDDIR)/product_stage1.elf
D2C		 := $(WSC_DIR)tools/d2c.py
D2C_TS_RUNNER	 := $(WSC_DIR)tools/d2c-ts.js
D2C_TS		 := $(ROOT_DIR)/src/lib/compiler/wsc/d2c.ts
S2C		 := $(WSC_DIR)tools/s2c.py
S2C_TS_RUNNER	 := $(WSC_DIR)tools/s2c-ts.js
S2C_TS		 := $(ROOT_DIR)/src/lib/compiler/wsc/s2c.ts

# Both converters run from TypeScript by default so make:wsc no longer needs
# python3. `S2C_IMPL=py` / `D2C_IMPL=py` keep the Python oracles available.
S2C_IMPL	?= ts
D2C_IMPL	?= ts
ifeq ($(filter $(S2C_IMPL),ts py),)
$(error S2C_IMPL must be ts or py, got '$(S2C_IMPL)')
endif
ifeq ($(filter $(D2C_IMPL),ts py),)
$(error D2C_IMPL must be ts or py, got '$(D2C_IMPL)')
endif
S2C_CMD_ts	:= node $(S2C_TS_RUNNER)
S2C_CMD_py	:= $(PYTHON) $(S2C)
S2C_CMD		:= $(S2C_CMD_$(S2C_IMPL))
S2C_DEPS_ts	:= $(S2C_TS) $(S2C_TS_RUNNER)
S2C_DEPS_py	:= $(S2C)
S2C_DEPS	:= $(S2C_DEPS_$(S2C_IMPL))
D2C_CMD_ts	:= node $(D2C_TS_RUNNER)
D2C_CMD_py	:= $(PYTHON) $(D2C)
D2C_CMD		:= $(D2C_CMD_$(D2C_IMPL))
D2C_DEPS_ts	:= $(D2C_TS) $(D2C_TS_RUNNER)
D2C_DEPS_py	:= $(D2C)
D2C_DEPS	:= $(D2C_DEPS_$(D2C_IMPL))

# `make:wsc` runs both converters in-process and passes CONVERTERS=prebuilt,
# so make only compiles the generated tree. Direct make invocations run the
# converter commands above.
CONVERTERS	?= make
ifeq ($(filter $(CONVERTERS),make prebuilt),)
$(error CONVERTERS must be make or prebuilt, got '$(CONVERTERS)')
endif
ifeq ($(CONVERTERS),prebuilt)
CONVERTER_STAMP	:=
else
CONVERTER_STAMP	:= $(D2C_STAMP)
endif

INCLUDEFLAGS	:= -I$(GEN_DIR)/include -I$(S2C_DIR) \
		   -I$(EXPORT_DIR)/include \
		   $(foreach path,$(WF_ARCH_LIBDIRS),-isystem $(path)/include)

CFLAGS		:= $(WSC_CFLAGS)
LDFLAGS		:= $(WSC_LDFLAGS)

EXPORT_SCRIPTS	:= $(shell find $(EXPORT_DIR)/src/data -name '*.s' 2>/dev/null | sort)
EXPORT_DEPS	:= $(shell find $(EXPORT_DIR)/src/data \
			$(EXPORT_DIR)/include/data -type f 2>/dev/null)
PROJECT_DEPS	:= $(shell find $(PROJECT_DIR)/project \
			$(PROJECT_DIR)/assets/backgrounds \
			-name '*.gbsres' 2>/dev/null)

DATA_SOURCES	:= $(shell find $(GEN_DIR)/data -name '*.c' 2>/dev/null | sort)
DATA_OBJS	:= $(patsubst $(GEN_DIR)/data/%.c,$(OBJDIR)/data/%.o,$(DATA_SOURCES))

ENGINE_SOURCES	:= $(WSC_ENGINE_SOURCES) $(PRODUCT_DIR)src/boot.c \
		   $(GBVM_STATES)/platform.c
ENGINE_OBJS	:= $(addprefix $(OBJDIR)/engine/,$(notdir $(ENGINE_SOURCES:.c=.o)))
BOOTSTRAP_OBJ	:= $(OBJDIR)/bootstrap.o
STATES_OBJ	:= $(OBJDIR)/states.o
S2C_OBJ		:= $(OBJDIR)/$(S2C_NAME).o
COMMON_OBJS	:= $(ENGINE_OBJS) $(DATA_OBJS) $(STATES_OBJ) $(S2C_OBJ)

.PHONY: all all-rom clean usage usage-rom product-check

# DATA_SOURCES only exists after d2c runs, so generate it first and re-enter
# make with the complete source list.
all: $(CONVERTER_STAMP)
	@$(MAKE) --no-print-directory -C $(CURDIR) all-rom

all-rom: $(ROM) $(ELF)

product-check:
	@test -d $(EXPORT_DIR)/src/data || { \
		echo "error: no exported project at $(EXPORT_DIR)" >&2; \
		echo "run the GB Studio CLI 'export' (or 'make:wsc') first" >&2; \
		exit 1; }

$(S2C_H) $(S2C_C): $(EXPORT_SCRIPTS) $(S2C_DEPS) $(GBVM_INCLUDE)/vm.i \
		$(GBVM_INCLUDE)/macro.i | product-check
	@echo "  S2C     $(S2C_DIR) ($(S2C_IMPL))"
	@mkdir -p $(S2C_DIR)
	$(S2C_CMD) --include $(EXPORT_DIR)/include \
		--out $(S2C_DIR) --name $(S2C_NAME) $(EXPORT_SCRIPTS)

$(D2C_STAMP): $(D2C_DEPS) $(S2C_H) $(S2C_C) $(EXPORT_DEPS) $(PROJECT_DEPS) \
		| product-check
	@echo "  D2C     $(GEN_DIR) ($(D2C_IMPL))"
	$(RM) $(GEN_DIR)/data $(GEN_DIR)/include
	$(D2C_CMD) --export $(EXPORT_DIR) \
		--out $(GEN_DIR) --s2c-header $(S2C_H) --s2c-source $(S2C_C) \
		--states topdown,platform,shmup,pointnclick,adventure
	@touch $@

$(ROM): $(STAGE) $(PRODUCT_DIR)wfconfig.toml
	@echo "  ROM     $@"
	@$(BUILDROM) -o $(ROM) --output-elf $(ELF) $< || { \
		echo "error: WSC ROM build failed; see the linker/allocator error above" >&2; \
		exit 1; }

$(ELF): $(ROM) $(PRODUCT_DIR)wfconfig.toml
	@echo "  ROM     $(ROM) (ELF rebuilt)"
	$(BUILDROM) -o $(ROM) --output-elf $(ELF) $(STAGE)

$(STAGE): $(COMMON_OBJS) $(BOOTSTRAP_OBJ)
	@echo "  LD      $@"
	@$(CC) -r -o $@ $^ $(WF_CRT0) $(LDFLAGS) || { \
		echo "error: WSC link failed; see the linker error above (IRAM may be full)" >&2; \
		exit 1; }

$(foreach src,$(ENGINE_SOURCES),$(eval $(call WSC_ENGINE_RULE,$(src))))

$(OBJDIR)/data/%.o: $(GEN_DIR)/data/%.c $(CONVERTER_STAMP)
	@echo "  CC      $<"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $@ $<

$(STATES_OBJ): $(GEN_DIR)/states.c $(CONVERTER_STAMP)
	@echo "  CC      $<"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $@ $<

$(S2C_OBJ): $(S2C_C) $(S2C_H)
	@echo "  CC      $<"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $@ $<

$(BOOTSTRAP_OBJ): $(GEN_DIR)/bootstrap.c $(CONVERTER_STAMP)
	@echo "  CC      $<"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $@ $<

clean:
	@echo "  CLEAN"
	$(RM) $(ROM) $(BUILDDIR) $(GEN_DIR)

usage: $(CONVERTER_STAMP)
	@$(MAKE) --no-print-directory -C $(CURDIR) usage-rom

usage-rom: $(ELF)
	$(ROMUSAGE) $< -g

-include $(wildcard $(OBJDIR)/*.d $(OBJDIR)/engine/*.d $(OBJDIR)/data/*.d)
