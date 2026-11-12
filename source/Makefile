# SPDX-FileCopyrightText: Copyright (c) 2023-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
#
# FRAMOS: NVIDIA's L4T 39.2.1 top-level OOT Makefile (kernel_oot_modules_src.tbz2),
# for building on stock Jetpack 7.2.1. This repo carries hwpm and nvidia-oot only,
# so the nvgpu, display and devicetree targets are removed; overlays are built and
# modules installed by build/target_build.sh. Changes are marked "FRAMOS:".

KERNEL_HEADERS ?= /lib/modules/$(shell uname -r)/build
# FRAMOS: kernel flavour of stock Jetpack 7.2.1 (Ubuntu noble)
kernel_name ?= noble
KERNEL_OUTPUT ?= $(KERNEL_HEADERS)

MAKEFILE_DIR := $(abspath $(shell dirname $(lastword $(MAKEFILE_LIST))))
NVIDIA_CONFTEST ?= $(MAKEFILE_DIR)/out/nvidia-conftest

ifdef OE_BUILD
  LD_BFD := $(LD)
else
  AR := $(CROSS_COMPILE)ar
  CC := $(CROSS_COMPILE)gcc
  CXX := $(CROSS_COMPILE)g++
  LD := $(CROSS_COMPILE)ld
  LD_BFD := $(CROSS_COMPILE)ld.bfd
  OBJCOPY := $(CROSS_COMPILE)objcopy
  NPROC ?= $(shell nproc)
  PARALLEL := -j$(NPROC)
endif

HOSTCC ?= gcc
V ?= 0

ifneq ($(words $(subst :, ,$(MAKEFILE_DIR))), 1)
  $(error source directory cannot contain spaces or colons)
endif


.PHONY : help modules clean conftest hwpm nvidia-oot conftest-clean

# help is default target!
help:
	@echo   "================================================================================"
	@echo   "Usage:"
	@echo   "   make modules          # to build NVIDIA OOT drivers"
	@echo   "   make clean            # to make clean driver sources"
	@echo   "   overlays, install:      see build/target_build.sh"
	@echo   "================================================================================"

# FRAMOS: no nvgpu/display sources, no modules_install (it would overwrite
# the stock modules in updates/), no dtbs
modules: hwpm nvidia-oot
clean: hwpm nvidia-oot conftest-clean

conftest:
ifeq ($(MAKECMDGOALS), modules)
	@echo   "================================================================================"
	@echo   "make $(MAKECMDGOALS) - conftest ..."
	@echo   "================================================================================"
	mkdir -p $(NVIDIA_CONFTEST)/nvidia;
	cp -av $(MAKEFILE_DIR)/nvidia-oot/scripts/conftest/* $(NVIDIA_CONFTEST)/nvidia/;
	$(MAKE) $(PARALLEL) ARCH=arm64 \
		src=$(NVIDIA_CONFTEST)/nvidia obj=$(NVIDIA_CONFTEST)/nvidia \
		CC="$(CC)" LD="$(LD)" \
		NV_KERNEL_SOURCES=$(KERNEL_HEADERS) \
		NV_KERNEL_OUTPUT=$(KERNEL_OUTPUT) \
		-f $(NVIDIA_CONFTEST)/nvidia/Makefile
endif

hwpm: conftest
	@if [ ! -d "$(MAKEFILE_DIR)/hwpm" ] ; then \
		echo "Directory hwpm is not found, exiting.."; \
		false; \
	fi
	@echo   "================================================================================"
	@echo   "make $(MAKECMDGOALS) - hwpm ..."
	@echo   "================================================================================"
	$(MAKE) $(PARALLEL) ARCH=arm64 \
		-C $(KERNEL_OUTPUT) \
		M=$(MAKEFILE_DIR)/hwpm/drivers/tegra/hwpm \
		CONFIG_TEGRA_OOT_MODULE=m \
		srctree.hwpm=$(MAKEFILE_DIR)/hwpm \
		srctree.nvconftest=$(NVIDIA_CONFTEST) \
		$(MAKECMDGOALS)

nvidia-oot: conftest hwpm
	@if [ ! -d "$(MAKEFILE_DIR)/nvidia-oot" ] ; then \
		echo "Directory nvidia-oot is not found, exiting.."; \
		false; \
	fi
	@echo   "================================================================================"
	@echo   "make $(MAKECMDGOALS) - nvidia-oot ..."
	@echo   "================================================================================"
	$(MAKE) $(PARALLEL) ARCH=arm64 \
		-C $(KERNEL_OUTPUT) \
		M=$(MAKEFILE_DIR)/nvidia-oot \
		CONFIG_TEGRA_OOT_MODULE=m \
		srctree.nvidia-oot=$(MAKEFILE_DIR)/nvidia-oot \
		srctree.hwpm=$(MAKEFILE_DIR)/hwpm \
		srctree.nvconftest=$(NVIDIA_CONFTEST) \
		kernel_name=${kernel_name} \
		system_type=l4t \
		KBUILD_EXTRA_SYMBOLS=$(MAKEFILE_DIR)/hwpm/drivers/tegra/hwpm/Module.symvers \
		$(MAKECMDGOALS)

conftest-clean:
	@echo   "================================================================================"
	@echo   "make $(MAKECMDGOALS) - conftest ..."
	@echo   "================================================================================"
	rm -fr $(NVIDIA_CONFTEST)
