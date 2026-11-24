# WSC run test for scripts converted by wsc/tools/s2c.py.

WONDERFUL_TOOLCHAIN ?= /opt/wonderful
TARGET = wswan/medium
include $(WONDERFUL_TOOLCHAIN)/target/$(TARGET)/makedefs.mk

NAME		:= scriptconv
TEST_DIR	:= $(CURDIR)
WSC_DIR		:= $(TEST_DIR)/../..
ROOT_DIR	:= $(WSC_DIR)/..
GBVM_CORE	:= $(ROOT_DIR)/appData/engine/gbvm/src/core
GBVM_INCLUDE	:= $(ROOT_DIR)/appData/engine/gbvm/include

S2C		:= $(WSC_DIR)/tools/s2c.py
S2C_TEST_DIR	:= $(WSC_DIR)/build/scripts_test
S2C_TEST_SRCS	:= $(WSC_DIR)/tests/scripts/s2c_main.s $(WSC_DIR)/tests/scripts/s2c_far.s
S2C_TEST_C	:= $(S2C_TEST_DIR)/s2c_test.c
S2C_TEST_H	:= $(S2C_TEST_DIR)/s2c_test.h

BUILDDIR	:= $(WSC_DIR)/build/tests/scriptconv
ELF		:= $(BUILDDIR)/$(NAME).elf
ELF_STAGE1	:= $(BUILDDIR)/$(NAME)_stage1.elf
ROM		:= $(BUILDDIR)/$(NAME).wsc

INCLUDEFLAGS	:= -I$(WSC_DIR)/host/include -I$(GBVM_INCLUDE) \
		   -I$(S2C_TEST_DIR) \
		   $(foreach path,$(WF_ARCH_LIBDIRS),-isystem $(path)/include)
LIBDIRSFLAGS	:= $(foreach path,$(WF_ARCH_LIBDIRS),-L$(path)/lib)

CFLAGS		+= -std=gnu11 -Wall $(WF_ARCH_CFLAGS) $(INCLUDEFLAGS) \
		   -ffunction-sections -fdata-sections -fno-common -O2 \
		   -fno-builtin -Wno-unknown-pragmas -Wno-pointer-sign
LDFLAGS		:= -T$(WF_LDSCRIPT) $(LIBDIRSFLAGS) $(WF_ARCH_LDFLAGS) \
		   -lwsx -lws

VPATH		:= src:$(GBVM_CORE):$(S2C_TEST_DIR)
OBJS		:= $(BUILDDIR)/main.o $(BUILDDIR)/vm_hooks.o \
		   $(BUILDDIR)/vm.o $(BUILDDIR)/vm_dispatch.o \
		   $(BUILDDIR)/s2c_test.o

.PHONY: all clean usage

all: $(ROM)

$(S2C_TEST_C) $(S2C_TEST_H): $(S2C_TEST_SRCS) $(S2C) \
		$(GBVM_INCLUDE)/vm.i $(GBVM_INCLUDE)/macro.i
	@mkdir -p $(S2C_TEST_DIR)
	python3 $(S2C) --include $(GBVM_INCLUDE) --out $(S2C_TEST_DIR) \
		--name s2c_test --bank s2c_far=2 $(S2C_TEST_SRCS)

$(BUILDDIR)/main.o: $(S2C_TEST_H)
$(BUILDDIR)/vm_hooks.o: $(S2C_TEST_H)
$(BUILDDIR)/s2c_test.o: $(S2C_TEST_C)

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
	$(RM) -r $(BUILDDIR)

usage: $(ELF)
	$(ROMUSAGE) $< -g

-include $(OBJS:.o=.d)
