# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#=======================================================================
# Makefile for riscv-tests/isa
#-----------------------------------------------------------------------

XLEN ?= 64

src_dir := .
riscv_tests_dir := $(src_dir)/../../ext/riscv-tests

ifeq ($(XLEN),64)
include $(src_dir)/rv64uv/Makefrag
endif
include $(src_dir)/rv32uv/Makefrag

default: all

#--------------------------------------------------------------------
# Build rules
#--------------------------------------------------------------------

RISCV_PREFIX ?= riscv$(XLEN)-unknown-elf-
RISCV_GCC ?= $(RISCV_PREFIX)gcc
RISCV_GCC_OPTS ?= -static -mcmodel=medany -fvisibility=hidden -nostdlib -nostartfiles -I/usr/include/newlib
RISCV_OBJDUMP ?= $(RISCV_PREFIX)objdump --disassemble-all --disassemble-zeroes --section=.text --section=.text.startup --section=.text.init --section=.data


vpath %.S $(src_dir)

#------------------------------------------------------------
# Build assembly tests

%.dump: %
	$(RISCV_OBJDUMP) $< > $@

define compile_template

$$($(1)_p_tests): $(1)-p-%: $(1)/%.S
	$$(RISCV_GCC) $(2) $$(RISCV_GCC_OPTS) -I$(riscv_tests_dir)/env/p -I$(riscv_tests_dir)/isa/macros/scalar -T$(riscv_tests_dir)/env/p/link.ld $$< -o $$@
$(1)_tests += $$($(1)_p_tests)

$$($(1)_v_tests): $(1)-v-%: $(1)/%.S
	$$(RISCV_GCC) $(2) $$(RISCV_GCC_OPTS) -DENTROPY=0x$$(shell echo \$$@ | md5sum | cut -c 1-7) -std=gnu99 -O2 -I$(riscv_tests_dir)/env/v -I$(riscv_tests_dir)/isa/macros/scalar -T$(riscv_tests_dir)/env/v/link.ld $(riscv_tests_dir)/env/v/entry.S $(riscv_tests_dir)/env/v/*.c $$< -o $$@
$(1)_tests += $$($(1)_v_tests)

$(1)_tests_dump = $$(addsuffix .dump, $$($(1)_tests))

$(1): $$($(1)_tests_dump)

.PHONY: $(1)

COMPILER_SUPPORTS_$(1) := $$(shell $$(RISCV_GCC) $(2) -c -x c /dev/null -o /dev/null 2> /dev/null; echo $$$$?)

ifeq ($$(COMPILER_SUPPORTS_$(1)),0)
tests += $$($(1)_tests)
endif

endef

$(eval $(call compile_template,rv32uv,-march=rv32gv -mabi=ilp32))
ifeq ($(XLEN),64)
$(eval $(call compile_template,rv64uv,-march=rv64gv -mabi=lp64))
endif

tests_dump = $(addsuffix .dump, $(tests))

junk += $(tests) $(tests_dump)

#------------------------------------------------------------
# Default

all: $(tests_dump) riscv_tests

#------------------------------------------------------------
# riscv-tests targets
riscv_tests:
	$(MAKE) -C $(riscv_tests_dir)/isa RISCV_GCC_OPTS='$(RISCV_GCC_OPTS)'

#------------------------------------------------------------
# Clean up

clean:
	$(MAKE) -C $(riscv_tests_dir)/isa clean
	rm -rf $(junk)
