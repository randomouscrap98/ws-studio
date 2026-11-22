CC ?= cc

WSRUN_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
ROOT := $(abspath $(WSRUN_DIR)../../..)
BUILD := $(ROOT)/wsc/build

CORE := $(BUILD)/mednafen_wswan_libretro.so
LIBRETRO_INC := $(BUILD)/beetle-wswan/libretro-common/include
TARGET := $(BUILD)/wsrun

CFLAGS := -O2 -Wall -Wextra -std=gnu99 -I$(LIBRETRO_INC) \
	-DWSRUN_BUILD_DIR=\"$(BUILD)\"
LDLIBS := -ldl -lm

.PHONY: all clean

all: $(TARGET)

$(CORE):
	bash $(WSRUN_DIR)fetch-core.sh

$(TARGET): $(WSRUN_DIR)wsrun.c $(WSRUN_DIR)stb_image_write.h $(CORE)
	$(CC) $(CFLAGS) -o $@ $(WSRUN_DIR)wsrun.c $(LDLIBS)

clean:
	rm -f $(TARGET)
