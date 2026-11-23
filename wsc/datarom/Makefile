# WSC exported-data ROM: links every post-processed data object and the
# converted scripts, then reads scenes back through the banked helpers.

PYTHON ?= python3

WONDERFUL_TOOLCHAIN ?= /opt/wonderful
TARGET = wswan/medium
include $(WONDERFUL_TOOLCHAIN)/target/$(TARGET)/makedefs.mk

NAME		:= datarom
DATAROM_DIR	:= $(CURDIR)/
WSC_DIR		:= $(DATAROM_DIR)..
ROOT_DIR	:= $(WSC_DIR)/..
GBVM_DIR	:= $(ROOT_DIR)/appData/engine/gbvm
GBVM_CORE	:= $(GBVM_DIR)/src/core
GBVM_WSC	:= $(GBVM_DIR)/src/wsc
GBVM_INCLUDE	:= $(GBVM_DIR)/include

EXPORT_DIR	:= $(WSC_DIR)/build/export
EXPORT_READY	:= $(EXPORT_DIR)/src/data/scene_sample_town.c
PROJECT_DIR	:= $(ROOT_DIR)/appData/templates/gbs2

BUILD_DIR	:= $(WSC_DIR)/build/datarom
S2C_DIR		:= $(BUILD_DIR)/s2c
S2C_NAME	:= datarom
S2C_H		:= $(S2C_DIR)/$(S2C_NAME).h
S2C_C		:= $(S2C_DIR)/$(S2C_NAME).c
D2C_STAMP	:= $(BUILD_DIR)/d2c.stamp
ORACLE_RAM	:= $(BUILD_DIR)/oracle_ram.json

ROM		:= $(CURDIR)/$(NAME).wsc
BUILDDIR	:= $(CURDIR)/build
ELF		:= $(BUILDDIR)/$(NAME).elf
ELF_STAGE1	:= $(BUILDDIR)/$(NAME)_stage1.elf

INCLUDEFLAGS	:= -I$(CURDIR)/include -I$(BUILD_DIR)/include \
		   -I$(S2C_DIR) -I$(WSC_DIR)/host/include -I$(GBVM_INCLUDE) \
		   -I$(EXPORT_DIR)/include \
		   $(foreach path,$(WF_ARCH_LIBDIRS),-isystem $(path)/include)
LIBDIRSFLAGS	:= $(foreach path,$(WF_ARCH_LIBDIRS),-L$(path)/lib)

CFLAGS		+= -std=gnu11 -Wall $(WF_ARCH_CFLAGS) $(INCLUDEFLAGS) \
		   -ffunction-sections -fdata-sections -fno-common -O2 \
		   -fno-builtin -Wno-unknown-pragmas -Wno-pointer-sign \
		   -include $(CURDIR)/include/datarom_prelude.h
LDFLAGS		:= -T$(WF_LDSCRIPT) $(LIBDIRSFLAGS) $(WF_ARCH_LDFLAGS) \
		   -lwsx -lws

EXPORT_SCRIPTS	:= $(wildcard $(EXPORT_DIR)/src/data/*.s)
EXPORT_DEPS	:= $(shell find $(EXPORT_DIR)/src/data \
			$(EXPORT_DIR)/include/data -type f 2>/dev/null)
PROJECT_DEPS	:= $(shell find $(PROJECT_DIR)/project \
			$(PROJECT_DIR)/assets/backgrounds \
			-name '*.gbsres' 2>/dev/null)

DATA_SOURCES	:= $(shell find $(BUILD_DIR)/data -name '*.c' 2>/dev/null | sort)
DATA_OBJS	:= $(patsubst $(BUILD_DIR)/data/%.c,$(BUILDDIR)/obj/data/%.o,$(DATA_SOURCES))
MAIN_OBJ	:= $(BUILDDIR)/obj/main.o
STUBS_OBJ	:= $(BUILDDIR)/obj/data_stubs.o
TEST_STUB_OBJ	:= $(BUILDDIR)/obj/stubs.o
S2C_OBJ		:= $(BUILDDIR)/obj/$(S2C_NAME).o
ENGINE_OBJS	:= $(BUILDDIR)/obj/engine/bankdata_wsc.o \
		   $(BUILDDIR)/obj/engine/hal_wsc.o \
		   $(BUILDDIR)/obj/engine/hal_wsc_bg.o \
		   $(BUILDDIR)/obj/engine/hal_wsc_spr.o
OBJS		:= $(MAIN_OBJ) $(STUBS_OBJ) $(TEST_STUB_OBJ) $(S2C_OBJ) \
		   $(ENGINE_OBJS) $(DATA_OBJS)

.PHONY: all _rom clean usage export-data

# Generated data sources only exist after d2c runs. The first make pass
# creates them, then re-enters this Makefile so the source list is complete.
all: $(ORACLE_RAM)
	@$(MAKE) --no-print-directory -C $(CURDIR) _rom

_rom: $(ROM)

# The export is generated, not committed. Recreate it if it is missing.
export-data $(EXPORT_READY):
	$(WSC_DIR)/export/run.sh

$(S2C_H) $(S2C_C): $(EXPORT_SCRIPTS) $(WSC_DIR)/tools/s2c.py $(EXPORT_READY) \
		$(GBVM_INCLUDE)/vm.i $(GBVM_INCLUDE)/macro.i
	@echo "  S2C     $(S2C_DIR)"
	@mkdir -p $(S2C_DIR)
	@$(if $(EXPORT_SCRIPTS),,test -f $(EXPORT_READY) || $(WSC_DIR)/export/run.sh)
	$(PYTHON) $(WSC_DIR)/tools/s2c.py --include $(EXPORT_DIR)/include \
		--out $(S2C_DIR) --name $(S2C_NAME) \
		$$(find $(EXPORT_DIR)/src/data -name '*.s' | sort)

$(D2C_STAMP): $(WSC_DIR)/tools/d2c.py $(S2C_H) $(S2C_C) $(EXPORT_DEPS)
	@echo "  D2C     $(BUILD_DIR)"
	$(RM) $(BUILD_DIR)/data $(BUILD_DIR)/include
	$(PYTHON) $(WSC_DIR)/tools/d2c.py --export $(EXPORT_DIR) \
		--out $(BUILD_DIR) --s2c-header $(S2C_H) --s2c-source $(S2C_C)
	@touch $@

$(ORACLE_RAM): $(WSC_DIR)/tools/datarom_oracle.py $(D2C_STAMP) $(S2C_H) \
		$(S2C_C) $(PROJECT_DEPS)
	@echo "  ORACLE  $@"
	$(PYTHON) $(WSC_DIR)/tools/datarom_oracle.py \
		--project $(PROJECT_DIR)/project.gbsproj \
		--project-dir $(PROJECT_DIR) --export $(EXPORT_DIR) \
		--s2c-header $(S2C_H) --s2c-source $(S2C_C) \
		--manifest $(BUILD_DIR)/include/d2c_manifest.h --out $@

$(ROM) $(ELF): $(ELF_STAGE1)
	@echo "  ROM     $@"
	$(BUILDROM) -o $(ROM) --output-elf $(ELF) $<

$(ELF_STAGE1): $(OBJS) $(D2C_STAMP) $(S2C_C)
	@echo "  LD      $@"
	$(CC) -r -o $@ $(OBJS) $(WF_CRT0) $(LDFLAGS)

$(MAIN_OBJ): src/main.c $(D2C_STAMP)
	@echo "  CC      $<"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $@ $<

$(STUBS_OBJ): $(BUILD_DIR)/data_stubs.c $(D2C_STAMP)
	@echo "  CC      $<"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $@ $<

$(TEST_STUB_OBJ): src/stubs.c
	@echo "  CC      $<"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $@ $<

$(S2C_OBJ): $(S2C_C) $(S2C_H)
	@echo "  CC      $<"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $@ $<

$(BUILDDIR)/obj/data/%.o: $(BUILD_DIR)/data/%.c $(D2C_STAMP)
	@echo "  CC      $<"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $@ $<

$(BUILDDIR)/obj/engine/%.o: $(GBVM_WSC)/%.c
	@echo "  CC      $<"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $@ $<

clean:
	@echo "  CLEAN"
	$(RM) $(ROM) $(BUILDDIR) $(BUILD_DIR)

usage: $(ELF)
	$(ROMUSAGE) $< -g

-include $(OBJS:.o=.d)
