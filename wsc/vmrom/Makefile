# GBVM core on the WonderSwan Color test ROM.

WONDERFUL_TOOLCHAIN ?= /opt/wonderful
TARGET = wswan/medium
include $(WONDERFUL_TOOLCHAIN)/target/$(TARGET)/makedefs.mk

NAME		:= vmrom
VMROM_DIR	:= $(CURDIR)/
WSC_DIR		:= $(VMROM_DIR)..
ROOT_DIR	:= $(WSC_DIR)/..
GBVM_CORE	:= $(ROOT_DIR)/appData/engine/gbvm/src/core
GBVM_INCLUDE	:= $(ROOT_DIR)/appData/engine/gbvm/include

BUILDDIR	:= build
ELF		:= $(BUILDDIR)/$(NAME).elf
ELF_STAGE1	:= $(BUILDDIR)/$(NAME)_stage1.elf
ROM		:= $(NAME).wsc

INCLUDEFLAGS	:= -I$(WSC_DIR)/host/include -I$(GBVM_INCLUDE) \
		   -I$(WSC_DIR)/vmtest \
		   $(foreach path,$(WF_ARCH_LIBDIRS),-isystem $(path)/include)
LIBDIRSFLAGS	:= $(foreach path,$(WF_ARCH_LIBDIRS),-L$(path)/lib)

CFLAGS		+= -std=gnu11 -Wall $(WF_ARCH_CFLAGS) $(INCLUDEFLAGS) \
		   -ffunction-sections -fdata-sections -fno-common -O2 \
		   -fno-builtin -Wno-unknown-pragmas -Wno-pointer-sign
LDFLAGS		:= -T$(WF_LDSCRIPT) $(LIBDIRSFLAGS) $(WF_ARCH_LDFLAGS) \
		   -lwsx -lws

VPATH		:= src:$(WSC_DIR)/port:$(GBVM_CORE)
OBJS		:= $(BUILDDIR)/main.o $(BUILDDIR)/vm_wsc.o \
		   $(BUILDDIR)/vm.o $(BUILDDIR)/vm_dispatch.o

.PHONY: all clean usage

all: $(ROM)

$(ROM) $(ELF): $(ELF_STAGE1)
	@echo "  ROM     $@"
	$(BUILDROM) -o $(ROM) --output-elf $(ELF) $<

$(ELF_STAGE1): $(OBJS)
	@echo "  LD      $@"
	$(CC) -r -o $@ $(OBJS) $(WF_CRT0) $(LDFLAGS)

$(BUILDDIR)/%.o: %.c
	@echo "  CC      $<"
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -MMD -MP -c -o $@ $<

clean:
	@echo "  CLEAN"
	$(RM) $(ROM) $(BUILDDIR)

usage: $(ELF)
	$(ROMUSAGE) $< -g

-include $(OBJS:.o=.d)
