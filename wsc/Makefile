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
S2C := $(WSC_DIR)tools/s2c.py
# Every config in wsc/oracle/ is run. platform.json is the GB-only jump trace
# used by gb-platform-smoke, so gb-oracle invokes it in --platform-smoke mode.
ORACLE_CONFIGS := $(wildcard $(WSC_DIR)oracle/*.json)
S2C_TEST_SRCS := $(WSC_DIR)tests/scripts/s2c_main.s $(WSC_DIR)tests/scripts/s2c_far.s
S2C_TEST_DIR := $(WSC_DIR)build/scripts_test
S2C_TEST_C := $(S2C_TEST_DIR)/s2c_test.c
S2C_TEST_H := $(S2C_TEST_DIR)/s2c_test.h

HOST_INCLUDES := -I$(WSC_DIR)host/include -I$(GBVM_INCLUDE) -I$(S2C_TEST_DIR)
HOST_BIN := $(WSC_DIR)build/vmtest
HOST_SRCS := $(GBVM_CORE)/vm.c $(GBVM_CORE)/vm_dispatch.c \
	$(WSC_DIR)host/vm_host.c $(WSC_DIR)vmtest/vmtest.c $(S2C_TEST_C)
HOST_DEPS := $(HOST_SRCS) $(GBVM_INCLUDE)/vm.h $(WSC_DIR)vmtest/vm_bytecode.h

.PHONY: test test-negative wsrun gb-core gb-oracle gb-platform-smoke \
	parallax-visual host-test gen-dispatch s2c-check product

# Build a product ROM from an exported project. The CLI command `make:wsc`
# does the export itself; this target is the scripted entry point for tests.
PROJECT ?= $(ROOT_DIR)/appData/templates/gbs2/project.gbsproj
PRODUCT_ROM ?= $(WSC_DIR)build/product/product.wsc
PRODUCT_STATE ?= $(WSC_DIR)build/product/state
product:
	$(WSC_DIR)tools/build_product.sh $(PROJECT) $(PRODUCT_ROM) $(PRODUCT_STATE)

wsrun:
	$(MAKE) -C $(WSC_DIR)tools/wsrun

gb-core:
	bash $(WSC_DIR)tools/wsrun/fetch-gb-core.sh

gb-oracle: wsrun gb-core
	$(MAKE) -C $(WSC_DIR)gamerom
	@set -e; for config in $(ORACLE_CONFIGS); do \
		echo "== $$(basename $$config)"; \
		case "$$config" in \
			*/oracle/platform.json) extra=--platform-smoke ;; \
			*) extra= ;; \
		esac; \
		$(PYTHON) $(WSC_DIR)tools/gbdiff.py --config $$config $$extra; \
	done

gb-platform-smoke: wsrun gb-core
	$(PYTHON) $(WSC_DIR)tools/gbdiff.py --config $(WSC_DIR)oracle/platform.json \
		--platform-smoke

# Captures GB and WSC frames at a few ticks and checks each parallax band's
# horizontal offset against the GB reference render.
parallax-visual: wsrun gb-core
	$(PYTHON) $(WSC_DIR)tools/parallax_visual.py \
		--config $(WSC_DIR)oracle/platform-parallax.json

test: wsrun
	cd $(WSC_DIR) && $(PYTHON) tests/run.py

test-negative: wsrun
	cd $(WSC_DIR) && $(PYTHON) tests/run.py --expect-fail tests/_negative/*

gen-dispatch:
	$(PYTHON) $(WSC_DIR)tools/gen_dispatch.py --check

s2c-check:
	$(PYTHON) $(WSC_DIR)tools/s2c_check.py

$(S2C_TEST_C) $(S2C_TEST_H): $(S2C_TEST_SRCS) $(S2C) $(GBVM_INCLUDE)/vm.i $(GBVM_INCLUDE)/macro.i
	@mkdir -p $(S2C_TEST_DIR)
	$(PYTHON) $(S2C) --include $(GBVM_INCLUDE) --out $(S2C_TEST_DIR) \
		--name s2c_test --bank s2c_far=2 $(S2C_TEST_SRCS)

$(HOST_BIN): $(HOST_DEPS)
	@mkdir -p $(dir $@)
	$(HOST_CC) $(HOST_CFLAGS) $(HOST_INCLUDES) -o $@ $(HOST_SRCS)

host-test: gen-dispatch $(HOST_BIN)
	$(HOST_BIN)
