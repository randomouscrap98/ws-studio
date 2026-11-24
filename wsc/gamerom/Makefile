# GB Studio engine boot image for the WonderSwan Color.
#
# One data/engine image serves every WSC engine test. The start scene and
# position come from a run-time table in src/platform.c selected by a boot id
# that wsrun patches into the ROM image (see wsc/tests/run.py).

PYTHON ?= python3

# Set to 1 to link the capacity-test filler (48 KiB of code plus 150 KiB of
# far const data). wsc/tools/capacity_check.sh owns that build.
CAPACITY_FILLER ?= 0

GAMEROM_DIR	:= $(CURDIR)/
include $(GAMEROM_DIR)../engine.mk

EXPORT_DIR	:= $(WSC_DIR)/build/export
EXPORT_READY	:= $(EXPORT_DIR)/src/data/scene_sample_town.c
PROJECT_DIR	:= $(ROOT_DIR)/appData/templates/gbs2

GEN_DIR		:= $(WSC_DIR)/build/gamerom
S2C_DIR		:= $(GEN_DIR)/s2c
S2C_NAME	:= gamerom
S2C_H		:= $(S2C_DIR)/$(S2C_NAME).h
S2C_C		:= $(S2C_DIR)/$(S2C_NAME).c
D2C_STAMP	:= $(GEN_DIR)/d2c.stamp
C13_TEST_SCRIPT	:= $(CURDIR)/src/script_c13_test.s
C14_TEST_SCRIPT	:= $(CURDIR)/src/script_c14_test.s
C15_TEST_SCRIPTS	:= $(CURDIR)/src/script_c15_instant.s \
			   $(CURDIR)/src/script_c15_speed.s \
			   $(CURDIR)/src/script_c15_var.s
C16_TEST_SCRIPT	:= $(CURDIR)/src/script_c16_choice.s
C17_TEST_SCRIPT	:= $(CURDIR)/src/script_c17_edge.s
C18_TEST_SCRIPTS	:= $(CURDIR)/src/script_c18_stop.s \
			   $(CURDIR)/src/script_c18_blank.s
C18_GEN		:= $(WSC_DIR)/tools/gen_c18_tiles.py
C18_DATA_DIR	:= $(GEN_DIR)/c18
C18_DATA_C	:= $(C18_DATA_DIR)/c18_bg_data.c
LAYOUT_PAD_SCRIPT := $(CURDIR)/src/script_layout_pad.s

BUILDDIR	?= $(CURDIR)/build
OBJDIR		:= $(BUILDDIR)/obj
ROM		?= $(CURDIR)/gamerom.wsc
ELF		:= $(BUILDDIR)/gamerom.elf
STAGE		:= $(BUILDDIR)/gamerom_stage1.elf
RAM_LOGO	:= $(BUILDDIR)/ram_logo.json
RAM_TOWN	:= $(BUILDDIR)/ram_town.json
RAM_WALK_FREE	:= $(BUILDDIR)/ram_walk_free.json
RAM_WALK_WALL	:= $(BUILDDIR)/ram_walk_wall.json
IRAM_CHECK	:= $(WSC_DIR)/tools/iram_check.py
IRAM_STAMP	:= $(BUILDDIR)/iram_check.stamp

INCLUDEFLAGS	:= -I$(GEN_DIR)/include -I$(C18_DATA_DIR) \
		   -I$(S2C_DIR) -I$(EXPORT_DIR)/include \
		   $(foreach path,$(WF_ARCH_LIBDIRS),-isystem $(path)/include)

CFLAGS		:= $(WSC_CFLAGS)
LDFLAGS		:= $(WSC_LDFLAGS)

EXPORT_SCRIPTS	:= $(wildcard $(EXPORT_DIR)/src/data/*.s)
EXPORT_DEPS	:= $(shell find $(EXPORT_DIR)/src/data \
			$(EXPORT_DIR)/include/data -type f 2>/dev/null)
PROJECT_DEPS	:= $(shell find $(PROJECT_DIR)/project \
			$(PROJECT_DIR)/assets/backgrounds \
			-name '*.gbsres' 2>/dev/null)
# The export is compiler output. Re-export whenever the compiler sources or
# event definitions are newer than the cached export.
COMPILER_DEPS	:= $(shell find $(ROOT_DIR)/src/lib/compiler \
			$(ROOT_DIR)/src/lib/events \
			$(ROOT_DIR)/src/shared/lib/resources \
			$(ROOT_DIR)/src/shared/lib/helpers -type f 2>/dev/null) \
			$(ROOT_DIR)/src/consts.ts

DATA_SOURCES	:= $(shell find $(GEN_DIR)/data -name '*.c' 2>/dev/null | sort)
DATA_OBJS	:= $(patsubst $(GEN_DIR)/data/%.c,$(OBJDIR)/data/%.o,$(DATA_SOURCES))

ENGINE_SOURCES	:= $(WSC_ENGINE_SOURCES) \
		   $(CURDIR)/src/platform.c $(CURDIR)/src/c13_test_scene.c \
		   $(CURDIR)/src/c14_test_scene.c \
		   $(CURDIR)/src/c15_test_scene.c \
		   $(CURDIR)/src/c16_test_scene.c \
		   $(CURDIR)/src/c17_test_scene.c \
		   $(CURDIR)/src/c18_test_scene.c
ifeq ($(CAPACITY_FILLER),1)
CFLAGS		+= -DWSC_CAPACITY_TEST
ENGINE_SOURCES	+= $(CURDIR)/src/capacity_filler.c
endif
ENGINE_OBJS	:= $(addprefix $(OBJDIR)/engine/,$(notdir $(ENGINE_SOURCES:.c=.o)))
# The gamerom's own src/platform.c shares its basename with the engine's
# states/platform.c, so the state gets its own object name.
STATE_PLATFORM_SRC := $(GBVM_STATES)/platform.c
STATE_PLATFORM_OBJ := $(OBJDIR)/engine/platform_state.o
C18_DATA_OBJ	:= $(OBJDIR)/engine/c18_bg_data.o
BOOTSTRAP_OBJ	:= $(OBJDIR)/bootstrap.o
STATES_OBJ	:= $(OBJDIR)/states.o
S2C_OBJ		:= $(OBJDIR)/$(S2C_NAME).o

COMMON_OBJS	:= $(ENGINE_OBJS) $(STATE_PLATFORM_OBJ) $(DATA_OBJS) $(STATES_OBJ) $(S2C_OBJ) \
		   $(C18_DATA_OBJ)

.PHONY: all all-rom clean usage usage-rom export-data iram-check

# The data source list only exists after d2c runs. Generate it first, then
# re-enter make so DATA_SOURCES is complete.
all: $(D2C_STAMP)
	@$(MAKE) --no-print-directory -C $(CURDIR) all-rom

all-rom: $(ROM) $(ELF) $(IRAM_STAMP) $(RAM_LOGO) $(RAM_TOWN) \
	 $(RAM_WALK_FREE) $(RAM_WALK_WALL)

# The walking tests start in the open area around tile (14, 41).
WALK_FREE_INPUT	:= $(WSC_DIR)/tests/walk-free/input.txt
WALK_WALL_INPUT	:= $(WSC_DIR)/tests/walk-wall/input.txt

$(RAM_LOGO): $(ROM) $(ELF) $(WSC_DIR)/tools/boot_oracle.py
	$(PYTHON) $(WSC_DIR)/tools/boot_oracle.py --ram-out $@ \
		--elf $(ELF) --scene scene_logo

$(RAM_TOWN): $(ROM) $(ELF) $(WSC_DIR)/tools/boot_oracle.py
	$(PYTHON) $(WSC_DIR)/tools/boot_oracle.py --ram-out $@ \
		--elf $(ELF) --scene scene_sample_town \
		--start-x 400 --start-y 400

$(RAM_WALK_FREE): $(ROM) $(ELF) $(WSC_DIR)/tools/walk_oracle.py \
		$(WSC_DIR)/tools/boot_oracle.py $(WALK_FREE_INPUT)
	$(PYTHON) $(WSC_DIR)/tools/walk_oracle.py --ram-out $@ \
		--elf $(ELF) --scene scene_sample_town \
		--start-x 112 --start-y 328 --frames 117 \
		--input $(WALK_FREE_INPUT)

$(RAM_WALK_WALL): $(ROM) $(ELF) $(WSC_DIR)/tools/walk_oracle.py \
		$(WSC_DIR)/tools/boot_oracle.py $(WALK_WALL_INPUT)
	$(PYTHON) $(WSC_DIR)/tools/walk_oracle.py --ram-out $@ \
		--elf $(ELF) --scene scene_sample_town \
		--start-x 112 --start-y 328 --frames 117 \
		--input $(WALK_WALL_INPUT)

export-data:
	$(WSC_DIR)/export/run.sh

$(EXPORT_READY): $(COMPILER_DEPS) $(PROJECT_DEPS)
	$(WSC_DIR)/export/run.sh

# One script bank. The layout-pad script is always last, so the whole suite
# runs with the moved far-data/far-code layout that exposed the C16a bug.
$(S2C_H) $(S2C_C): $(EXPORT_SCRIPTS) $(C13_TEST_SCRIPT) $(C14_TEST_SCRIPT) \
		$(C15_TEST_SCRIPTS) $(C16_TEST_SCRIPT) $(C17_TEST_SCRIPT) \
		$(C18_TEST_SCRIPTS) $(LAYOUT_PAD_SCRIPT) \
		$(WSC_DIR)/tools/s2c.py $(EXPORT_READY) \
		$(GBVM_INCLUDE)/vm.i $(GBVM_INCLUDE)/macro.i
	@echo "  S2C     $(S2C_DIR)"
	@mkdir -p $(S2C_DIR)
	@$(if $(EXPORT_SCRIPTS),,test -f $(EXPORT_READY) || $(WSC_DIR)/export/run.sh)
	$(PYTHON) $(WSC_DIR)/tools/s2c.py --include $(EXPORT_DIR)/include \
		--out $(S2C_DIR) --name $(S2C_NAME) \
		$$(find $(EXPORT_DIR)/src/data -name '*.s' | sort) \
		$(C13_TEST_SCRIPT) $(C14_TEST_SCRIPT) $(C15_TEST_SCRIPTS) \
		$(C16_TEST_SCRIPT) $(C17_TEST_SCRIPT) $(C18_TEST_SCRIPTS) \
		$(LAYOUT_PAD_SCRIPT)

$(D2C_STAMP): $(WSC_DIR)/tools/d2c.py $(C18_GEN) $(S2C_H) $(S2C_C) $(EXPORT_DEPS)
	@echo "  D2C     $(GEN_DIR)"
	$(RM) $(GEN_DIR)/data $(GEN_DIR)/include
	$(PYTHON) $(WSC_DIR)/tools/d2c.py --export $(EXPORT_DIR) \
		--out $(GEN_DIR) --s2c-header $(S2C_H) --s2c-source $(S2C_C) \
		--states topdown,platform,shmup,pointnclick,adventure
	$(PYTHON) $(C18_GEN) --out $(C18_DATA_DIR)
	@touch $@

$(ROM): $(STAGE) $(CURDIR)/wfconfig.toml
	@echo "  ROM     $@"
	$(BUILDROM) -o $(ROM) --output-elf $(ELF) $<

$(ELF): $(ROM) $(CURDIR)/wfconfig.toml
	@echo "  ROM     $(ROM) (ELF rebuilt)"
	$(BUILDROM) -o $(ROM) --output-elf $(ELF) $(STAGE)

$(IRAM_STAMP): $(ELF) $(IRAM_CHECK)
	@echo "  CHECK   $(ELF)"
	$(PYTHON) $(IRAM_CHECK) --elf $(ELF)
	@touch $@

$(STAGE): $(COMMON_OBJS) $(BOOTSTRAP_OBJ)
	@echo "  LD      $@"
	$(CC) -r -o $@ $^ $(WF_CRT0) $(LDFLAGS)

$(foreach src,$(ENGINE_SOURCES),$(eval $(call WSC_ENGINE_RULE,$(src))))

$(STATE_PLATFORM_OBJ): $(STATE_PLATFORM_SRC) $(D2C_STAMP)
	@echo "  CC      $<"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $@ $<

$(C18_DATA_OBJ): $(C18_DATA_C) $(D2C_STAMP)
	@echo "  CC      $<"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $@ $<

$(OBJDIR)/data/%.o: $(GEN_DIR)/data/%.c $(D2C_STAMP)
	@echo "  CC      $<"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $@ $<

$(STATES_OBJ): $(GEN_DIR)/states.c $(D2C_STAMP)
	@echo "  CC      $<"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $@ $<

$(S2C_OBJ): $(S2C_C) $(S2C_H)
	@echo "  CC      $<"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $@ $<

$(BOOTSTRAP_OBJ): $(GEN_DIR)/bootstrap.c $(D2C_STAMP)
	@echo "  CC      $<"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $@ $<

clean:
	@echo "  CLEAN"
	$(RM) $(ROM) $(BUILDDIR) $(GEN_DIR)

# The generated data source list only exists after D2C. Re-enter make like
# the "all" target so a fresh tree can run usage directly.
usage: $(D2C_STAMP)
	@$(MAKE) --no-print-directory -C $(CURDIR) usage-rom

usage-rom: $(ELF) $(IRAM_STAMP)
	$(ROMUSAGE) $< -g

-include $(wildcard $(OBJDIR)/*.d $(OBJDIR)/engine/*.d $(OBJDIR)/data/*.d)
