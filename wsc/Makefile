PYTHON ?= python3

WSC_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

.PHONY: test test-negative wsrun

wsrun:
	$(MAKE) -C $(WSC_DIR)tools/wsrun

test: wsrun
	cd $(WSC_DIR) && $(PYTHON) tests/run.py

test-negative: wsrun
	cd $(WSC_DIR) && $(PYTHON) tests/run.py --expect-fail tests/_negative/*
