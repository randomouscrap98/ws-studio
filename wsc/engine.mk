# Shared build definitions for the WSC engine ROMs.
#
# Included by wsc/gamerom/Makefile (the test image) and
# wsc/product/Makefile (a build of an exported GB Studio project). The
# portable engine source list, compiler flags and linker flags live here so
# the two images cannot drift apart.

ENGINE_MK	:= $(abspath $(lastword $(MAKEFILE_LIST)))
WSC_DIR		:= $(dir $(ENGINE_MK))

PYTHON ?= python3

WONDERFUL_TOOLCHAIN ?= /opt/wonderful
TARGET = wswan/medium
include $(WONDERFUL_TOOLCHAIN)/target/$(TARGET)/makedefs.mk

ROOT_DIR	:= $(WSC_DIR)..
GBVM_DIR	:= $(ROOT_DIR)/appData/engine/gbvm
GBVM_CORE	:= $(GBVM_DIR)/src/core
GBVM_STATES	:= $(GBVM_DIR)/src/states
GBVM_WSC	:= $(GBVM_DIR)/src/wsc
GBVM_INCLUDE	:= $(GBVM_DIR)/include

WSC_INCLUDE	:= $(WSC_DIR)include
WSC_PRELUDE	?= $(WSC_INCLUDE)/wsc_prelude.h

# The portable engine, all implemented scene states except the platform state
# whose source is named like the image's own platform.c, and the WSC HAL.
# states/platform.c is added by each image under its own object name.
WSC_ENGINE_SOURCES := \
	$(GBVM_DIR)/src/main.c \
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
	$(GBVM_CORE)/load_save.c \
	$(GBVM_CORE)/vm_load_save.c $(GBVM_CORE)/game_time.c \
	$(GBVM_CORE)/math.c $(GBVM_CORE)/math_atan2.c \
	$(GBVM_CORE)/system.c \
	$(GBVM_CORE)/ui.c $(GBVM_CORE)/vm_ui.c \
	$(GBVM_STATES)/topdown.c \
	$(GBVM_STATES)/adventure.c \
	$(GBVM_STATES)/shmup.c $(GBVM_STATES)/pointnclick.c \
	$(GBVM_WSC)/bankdata_wsc.c $(GBVM_WSC)/hal_wsc.c \
	$(GBVM_WSC)/hal_wsc_sram.c \
	$(GBVM_WSC)/hal_wsc_bg.c $(GBVM_WSC)/hal_wsc_spr.c \
	$(GBVM_WSC)/parallax_wsc.c \
	$(GBVM_WSC)/orient_wsc.c \
	$(GBVM_WSC)/scroll_wsc.c $(GBVM_WSC)/stubs_wsc.c \
	$(GBVM_WSC)/ui_wsc.c \
	$(WSC_DIR)src/platform_common.c

WSC_COMMON_INCLUDES := -I$(WSC_INCLUDE) -I$(WSC_DIR)host/include \
		       -I$(GBVM_INCLUDE)

WSC_CFLAGS = -std=gnu11 -Wall $(WF_ARCH_CFLAGS) $(INCLUDEFLAGS) \
	     $(WSC_COMMON_INCLUDES) -ffunction-sections -fdata-sections \
	      -fno-common -O2 -fno-builtin -Wno-unknown-pragmas \
	      -Wno-pointer-sign -DHUGE_TRACKER -DGBVM_ENGINE_HANDLERS \
	      -include $(WSC_PRELUDE)

WSC_LIBDIRSFLAGS := $(foreach path,$(WF_ARCH_LIBDIRS),-L$(path)/lib)
WSC_LDFLAGS := -T$(WF_LDSCRIPT) $(WSC_LIBDIRSFLAGS) $(WF_ARCH_LDFLAGS) \
	       -lwsx -lws

# Every image compiles each engine source into one object under its own
# build directory. D2C_STAMP must be defined by the including Makefile.
define WSC_ENGINE_RULE
$(OBJDIR)/engine/$(notdir $(basename $(1))).o: $(1) $(D2C_STAMP)
	@echo "  CC      $(1)"
	@mkdir -p $$(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $$@ $(1)
endef
