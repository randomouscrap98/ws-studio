# GB Studio engine boot ROMs for the WonderSwan Color.
#
# One data/engine image, linked twice: the default start scene is the logo
# scene, and the town variant overrides the generated start scene and start
# position to exercise the runtime camera bounds.

PYTHON ?= python3

WONDERFUL_TOOLCHAIN ?= /opt/wonderful
TARGET = wswan/medium
include $(WONDERFUL_TOOLCHAIN)/target/$(TARGET)/makedefs.mk

GAMEROM_DIR	:= $(CURDIR)/
WSC_DIR		:= $(GAMEROM_DIR)..
ROOT_DIR	:= $(WSC_DIR)/..
GBVM_DIR	:= $(ROOT_DIR)/appData/engine/gbvm
GBVM_CORE	:= $(GBVM_DIR)/src/core
GBVM_STATES	:= $(GBVM_DIR)/src/states
GBVM_WSC	:= $(GBVM_DIR)/src/wsc
GBVM_INCLUDE	:= $(GBVM_DIR)/include

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

BUILDDIR	:= $(CURDIR)/build
OBJDIR		:= $(BUILDDIR)/obj
ROM_LOGO	:= $(CURDIR)/gamerom.wsc
ROM_TOWN	:= $(CURDIR)/gamerom_town.wsc
ROM_TOWN_WALK	:= $(CURDIR)/gamerom_town_walk.wsc
ROM_C13		:= $(CURDIR)/gamerom_c13.wsc
ELF_LOGO	:= $(BUILDDIR)/gamerom.elf
ELF_TOWN	:= $(BUILDDIR)/gamerom_town.elf
ELF_TOWN_WALK	:= $(BUILDDIR)/gamerom_town_walk.elf
ELF_C13		:= $(BUILDDIR)/gamerom_c13.elf
STAGE_LOGO	:= $(BUILDDIR)/gamerom_stage1.elf
STAGE_TOWN	:= $(BUILDDIR)/gamerom_town_stage1.elf
STAGE_TOWN_WALK	:= $(BUILDDIR)/gamerom_town_walk_stage1.elf
STAGE_C13	:= $(BUILDDIR)/gamerom_c13_stage1.elf
RAM_LOGO	:= $(BUILDDIR)/ram_logo.json
RAM_TOWN	:= $(BUILDDIR)/ram_town.json
RAM_WALK_FREE	:= $(BUILDDIR)/ram_walk_free.json
RAM_WALK_WALL	:= $(BUILDDIR)/ram_walk_wall.json

INCLUDEFLAGS	:= -I$(CURDIR)/include -I$(GEN_DIR)/include \
		   -I$(S2C_DIR) -I$(WSC_DIR)/host/include \
		   -I$(GBVM_INCLUDE) -I$(EXPORT_DIR)/include \
		   $(foreach path,$(WF_ARCH_LIBDIRS),-isystem $(path)/include)
LIBDIRSFLAGS	:= $(foreach path,$(WF_ARCH_LIBDIRS),-L$(path)/lib)

CFLAGS		+= -std=gnu11 -Wall $(WF_ARCH_CFLAGS) $(INCLUDEFLAGS) \
		   -ffunction-sections -fdata-sections -fno-common -O2 \
		   -fno-builtin -Wno-unknown-pragmas -Wno-pointer-sign \
		   -DHUGE_TRACKER -DGBVM_ENGINE_HANDLERS \
		   -include $(CURDIR)/include/gamerom_prelude.h
LDFLAGS		:= -T$(WF_LDSCRIPT) $(LIBDIRSFLAGS) $(WF_ARCH_LDFLAGS) \
		   -lwsx -lws

EXPORT_SCRIPTS	:= $(wildcard $(EXPORT_DIR)/src/data/*.s)
EXPORT_DEPS	:= $(shell find $(EXPORT_DIR)/src/data \
			$(EXPORT_DIR)/include/data -type f 2>/dev/null)
PROJECT_DEPS	:= $(shell find $(PROJECT_DIR)/project \
			$(PROJECT_DIR)/assets/backgrounds \
			-name '*.gbsres' 2>/dev/null)

DATA_SOURCES	:= $(shell find $(GEN_DIR)/data -name '*.c' 2>/dev/null | sort)
DATA_OBJS	:= $(patsubst $(GEN_DIR)/data/%.c,$(OBJDIR)/data/%.o,$(DATA_SOURCES))

ENGINE_SOURCES	:= $(GBVM_DIR)/src/main.c \
		   $(GBVM_CORE)/core.c $(GBVM_CORE)/data_manager.c \
		   $(GBVM_CORE)/actor.c $(GBVM_CORE)/scroll.c \
		   $(GBVM_CORE)/camera.c $(GBVM_CORE)/palette.c \
		   $(GBVM_CORE)/input.c $(GBVM_CORE)/events.c \
		   $(GBVM_CORE)/trigger.c $(GBVM_CORE)/collision.c \
		   $(GBVM_CORE)/projectiles.c $(GBVM_CORE)/vm.c \
		   $(GBVM_CORE)/vm_dispatch.c \
		   $(GBVM_CORE)/vm_actor.c $(GBVM_CORE)/vm_gameboy.c \
		   $(GBVM_CORE)/vm_scene.c $(GBVM_CORE)/vm_camera.c \
		   $(GBVM_CORE)/vm_palette.c $(GBVM_CORE)/vm_math.c \
		   $(GBVM_CORE)/vm_music.c $(GBVM_CORE)/vm_projectiles.c \
		   $(GBVM_CORE)/vm_load_save.c $(GBVM_CORE)/game_time.c \
		   $(GBVM_CORE)/math.c $(GBVM_CORE)/math_atan2.c \
		   $(GBVM_CORE)/system.c \
		   $(GBVM_STATES)/topdown.c \
		   $(GBVM_WSC)/bankdata_wsc.c $(GBVM_WSC)/hal_wsc.c \
		   $(GBVM_WSC)/hal_wsc_bg.c $(GBVM_WSC)/hal_wsc_spr.c \
		   $(GBVM_WSC)/scroll_wsc.c $(GBVM_WSC)/stubs_wsc.c \
		   $(CURDIR)/src/platform.c $(CURDIR)/src/c13_test_scene.c
ENGINE_OBJS	:= $(addprefix $(OBJDIR)/engine/,$(notdir $(ENGINE_SOURCES:.c=.o)))

BOOTSTRAP_LOGO	:= $(OBJDIR)/bootstrap_logo.o
BOOTSTRAP_TOWN	:= $(OBJDIR)/bootstrap_town.o
BOOTSTRAP_TOWN_WALK := $(OBJDIR)/bootstrap_town_walk.o
BOOTSTRAP_C13	:= $(OBJDIR)/bootstrap_c13.o
STATES_OBJ	:= $(OBJDIR)/states.o
S2C_OBJ		:= $(OBJDIR)/$(S2C_NAME).o

COMMON_OBJS	:= $(ENGINE_OBJS) $(DATA_OBJS) $(STATES_OBJ) $(S2C_OBJ)

.PHONY: all all-rom clean usage export-data

# The data source list only exists after d2c runs. Generate it first, then
# re-enter make so DATA_SOURCES is complete.
all: $(D2C_STAMP)
	@$(MAKE) --no-print-directory -C $(CURDIR) all-rom

all-rom: $(RAM_LOGO) $(RAM_TOWN) $(RAM_WALK_FREE) $(RAM_WALK_WALL) $(ROM_C13)

# Generated data sources only exist after d2c runs. The first make pass
# creates them, then re-enters this Makefile so the source lists are complete.
$(RAM_LOGO): $(ROM_LOGO) $(ROM_TOWN) $(WSC_DIR)/tools/boot_oracle.py
	$(PYTHON) $(WSC_DIR)/tools/boot_oracle.py --ram-out $@ \
		--elf $(ELF_LOGO) --scene scene_logo
$(RAM_TOWN): $(ROM_TOWN) $(ROM_LOGO) $(WSC_DIR)/tools/boot_oracle.py
	$(PYTHON) $(WSC_DIR)/tools/boot_oracle.py --ram-out $@ \
		--elf $(ELF_TOWN) --scene scene_sample_town \
		--start-x 400 --start-y 400

# The walking tests use the same town image with a start in the open area
# around tile (14, 41).
WALK_FREE_INPUT	:= $(WSC_DIR)/tests/walk-free/input.txt
WALK_WALL_INPUT	:= $(WSC_DIR)/tests/walk-wall/input.txt

$(RAM_WALK_FREE): $(ROM_TOWN_WALK) $(ELF_TOWN_WALK) \
		$(WSC_DIR)/tools/walk_oracle.py $(WALK_FREE_INPUT)
	$(PYTHON) $(WSC_DIR)/tools/walk_oracle.py --ram-out $@ \
		--elf $(ELF_TOWN_WALK) --scene scene_sample_town \
		--start-x 112 --start-y 328 --frames 140 \
		--input $(WALK_FREE_INPUT)

$(RAM_WALK_WALL): $(ROM_TOWN_WALK) $(ELF_TOWN_WALK) \
		$(WSC_DIR)/tools/walk_oracle.py $(WALK_WALL_INPUT)
	$(PYTHON) $(WSC_DIR)/tools/walk_oracle.py --ram-out $@ \
		--elf $(ELF_TOWN_WALK) --scene scene_sample_town \
		--start-x 112 --start-y 328 --frames 140 \
		--input $(WALK_WALL_INPUT)

export-data $(EXPORT_READY):
	$(WSC_DIR)/export/run.sh

$(S2C_H) $(S2C_C): $(EXPORT_SCRIPTS) $(C13_TEST_SCRIPT) \
		$(WSC_DIR)/tools/s2c.py $(EXPORT_READY) \
		$(GBVM_INCLUDE)/vm.i $(GBVM_INCLUDE)/macro.i
	@echo "  S2C     $(S2C_DIR)"
	@mkdir -p $(S2C_DIR)
	@$(if $(EXPORT_SCRIPTS),,test -f $(EXPORT_READY) || $(WSC_DIR)/export/run.sh)
	$(PYTHON) $(WSC_DIR)/tools/s2c.py --include $(EXPORT_DIR)/include \
		--out $(S2C_DIR) --name $(S2C_NAME) \
		$$(find $(EXPORT_DIR)/src/data -name '*.s' | sort) \
		$(C13_TEST_SCRIPT)

$(D2C_STAMP): $(WSC_DIR)/tools/d2c.py $(S2C_H) $(S2C_C) $(EXPORT_DEPS)
	@echo "  D2C     $(GEN_DIR)"
	$(RM) $(GEN_DIR)/data $(GEN_DIR)/include
	$(PYTHON) $(WSC_DIR)/tools/d2c.py --export $(EXPORT_DIR) \
		--out $(GEN_DIR) --s2c-header $(S2C_H) --s2c-source $(S2C_C) \
		--states topdown
	@touch $@

$(ROM_LOGO) $(ELF_LOGO): $(STAGE_LOGO)
	@echo "  ROM     $@"
	$(BUILDROM) -o $(ROM_LOGO) --output-elf $(ELF_LOGO) $<

$(ROM_TOWN) $(ELF_TOWN): $(STAGE_TOWN)
	@echo "  ROM     $@"
	$(BUILDROM) -o $(ROM_TOWN) --output-elf $(ELF_TOWN) $<

$(ROM_TOWN_WALK) $(ELF_TOWN_WALK): $(STAGE_TOWN_WALK)
	@echo "  ROM     $@"
	$(BUILDROM) -o $(ROM_TOWN_WALK) --output-elf $(ELF_TOWN_WALK) $<

$(ROM_C13) $(ELF_C13): $(STAGE_C13)
	@echo "  ROM     $@"
	$(BUILDROM) -o $(ROM_C13) --output-elf $(ELF_C13) $<

$(STAGE_LOGO): $(COMMON_OBJS) $(BOOTSTRAP_LOGO)
	@echo "  LD      $@"
	$(CC) -r -o $@ $^ $(WF_CRT0) $(LDFLAGS)

$(STAGE_TOWN): $(COMMON_OBJS) $(BOOTSTRAP_TOWN)
	@echo "  LD      $@"
	$(CC) -r -o $@ $^ $(WF_CRT0) $(LDFLAGS)

$(STAGE_TOWN_WALK): $(COMMON_OBJS) $(BOOTSTRAP_TOWN_WALK)
	@echo "  LD      $@"
	$(CC) -r -o $@ $^ $(WF_CRT0) $(LDFLAGS)

$(STAGE_C13): $(COMMON_OBJS) $(BOOTSTRAP_C13)
	@echo "  LD      $@"
	$(CC) -r -o $@ $^ $(WF_CRT0) $(LDFLAGS)

define ENGINE_RULE
$(OBJDIR)/engine/$(notdir $(basename $(1))).o: $(1) $(D2C_STAMP)
	@echo "  CC      $(1)"
	@mkdir -p $$(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $$@ $(1)
endef

$(foreach src,$(ENGINE_SOURCES),$(eval $(call ENGINE_RULE,$(src))))

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

$(BOOTSTRAP_LOGO): $(GEN_DIR)/bootstrap.c $(D2C_STAMP)
	@echo "  CC      $< (logo)"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $@ $<

$(BOOTSTRAP_TOWN): $(GEN_DIR)/bootstrap.c $(D2C_STAMP)
	@echo "  CC      $< (town)"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -DBOOT_START_SCENE=scene_sample_town \
		-DBOOT_START_X=12800 -DBOOT_START_Y=12800 -MMD -MP -c -o $@ $<

$(BOOTSTRAP_TOWN_WALK): $(GEN_DIR)/bootstrap.c $(D2C_STAMP)
	@echo "  CC      $< (town walk)"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -DBOOT_START_SCENE=scene_sample_town \
		-DBOOT_START_X=3584 -DBOOT_START_Y=10496 -MMD -MP -c -o $@ $<

$(BOOTSTRAP_C13): $(GEN_DIR)/bootstrap.c $(D2C_STAMP)
	@echo "  CC      $< (c13 script test)"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -DBOOT_START_SCENE=scene_c13_test \
		-DBOOT_START_X=1536 -DBOOT_START_Y=2560 -MMD -MP -c -o $@ $<

clean:
	@echo "  CLEAN"
	$(RM) $(ROM_LOGO) $(ROM_TOWN) $(ROM_TOWN_WALK) $(ROM_C13) $(BUILDDIR) $(GEN_DIR)

usage: $(ELF_LOGO)
	$(ROMUSAGE) $< -g

-include $(wildcard $(OBJDIR)/*.d $(OBJDIR)/engine/*.d $(OBJDIR)/data/*.d)
