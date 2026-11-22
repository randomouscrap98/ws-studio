PYTHON ?= python3

WSC_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
ROOT_DIR := $(WSC_DIR)..
GBVM_CORE := $(ROOT_DIR)/appData/engine/gbvm/src/core
GBVM_INCLUDE := $(ROOT_DIR)/appData/engine/gbvm/include

HOST_CC ?= cc
HOST_CFLAGS := -std=gnu99 -Wall -Wextra -Werror=pointer-to-int-cast \
	-Werror=int-to-pointer-cast -fsanitize=address,undefined \
	-fno-omit-frame-pointer -fno-builtin -Wno-unknown-pragmas \
	-Wno-pointer-sign -DNINTENDO
HOST_INCLUDES := -I$(WSC_DIR)host/include -I$(GBVM_INCLUDE)
HOST_BIN := $(WSC_DIR)build/vmtest
HOST_SRCS := $(GBVM_CORE)/vm.c $(GBVM_CORE)/vm_dispatch.c \
	$(WSC_DIR)host/vm_host.c $(WSC_DIR)vmtest/vmtest.c
HOST_DEPS := $(HOST_SRCS) $(GBVM_INCLUDE)/vm.h $(WSC_DIR)vmtest/vm_bytecode.h

.PHONY: test test-negative wsrun host-test gen-dispatch

wsrun:
	$(MAKE) -C $(WSC_DIR)tools/wsrun

test: wsrun
	cd $(WSC_DIR) && $(PYTHON) tests/run.py

test-negative: wsrun
	cd $(WSC_DIR) && $(PYTHON) tests/run.py --expect-fail tests/_negative/*

gen-dispatch:
	$(PYTHON) $(WSC_DIR)tools/gen_dispatch.py --check

$(HOST_BIN): $(HOST_DEPS)
	@mkdir -p $(dir $@)
	$(HOST_CC) $(HOST_CFLAGS) $(HOST_INCLUDES) -o $@ $(HOST_SRCS)

host-test: gen-dispatch $(HOST_BIN)
	$(HOST_BIN)
