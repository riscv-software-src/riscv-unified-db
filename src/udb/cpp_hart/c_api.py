# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Retained native callback and opaque-hart declarations."""

CALLBACKS = """
uint64_t (*read_hpm_counter)(uint64_t counternum);
uint64_t (*read_mcycle)();
uint64_t (*read_mtime)();
uint64_t (*sw_write_mcycle)(uint64_t new_value);
void (*cache_block_zero)(uint64_t paddr);
void (*eei_ecall_from_m)();
void (*eei_ecall_from_s)();
void (*eei_ecall_from_u)();
void (*eei_ecall_from_vs)();
void (*eei_ebreak)();
void (*memory_model_acquire)();
void (*memory_model_release)();
void (*notify_mode_change)(PrivilegeModeValueType from, PrivilegeModeValueType to);
void (*prefetch_instruction)(uint64_t paddr);
void (*prefetch_read)(uint64_t paddr);
void (*prefetch_write)(uint64_t paddr);
void (*fence)(uint8_t pi, uint8_t pr, uint8_t po, uint8_t pw, uint8_t si, uint8_t sr, uint8_t so, uint8_t sw);
void (*fence_tso)();
void (*ifence)();
void (*order_pgtbl_writes_before_vmafence)();
void (*order_pgtbl_reads_after_vmafence)();
uint64_t (*read_physical_memory_8)(uint64_t paddr);
uint64_t (*read_physical_memory_16)(uint64_t paddr);
uint64_t (*read_physical_memory_32)(uint64_t paddr);
uint64_t (*read_physical_memory_64)(uint64_t paddr);
void (*write_physical_memory_8)(uint64_t paddr, uint64_t value);
void (*write_physical_memory_16)(uint64_t paddr, uint64_t value);
void (*write_physical_memory_32)(uint64_t paddr, uint64_t value);
void (*write_physical_memory_64)(uint64_t paddr, uint64_t value);
int (*memcpy_from_host)(uint64_t guest_paddr, const uint8_t* host_ptr, uint64_t size);
int (*memcpy_to_host)(uint8_t* host_ptr, uint64_t guest_paddr, uint64_t size);
uint8_t (*atomic_check_then_write_32)(uint64_t, uint32_t, uint32_t);
uint8_t (*atomic_check_then_write_64)(uint64_t, uint64_t, uint64_t);
uint8_t (*atomically_set_pte_a)(uint64_t, uint64_t, uint32_t);
uint8_t (*atomically_set_pte_a_d)(uint64_t, uint64_t, uint32_t);
uint64_t (*atomic_read_modify_write_32)(uint64_t, uint64_t, AmoOperationValueType);
uint64_t (*atomic_read_modify_write_64)(uint64_t, uint64_t, AmoOperationValueType);
uint8_t (*pma_applies_Q_)(PmaAttributeValueType pma, uint64_t paddr, uint32_t len);
"""


def header(context, *, renode=False):
    out = [
        '#pragma once\n#include <stddef.h>\n#include <stdint.h>\n#ifdef __cplusplus\n#define LINKAGE extern "C"\n#else\n#define LINKAGE\n#endif'
    ]
    if renode:
        out.append("#include <exports.h>")
    types = (
        context.enum_types
        if hasattr(context, "enum_types")
        else (enum.type(context.table) for enum in context.global_ast.enums)
    )
    for dtype in types:
        typ = "uint32_t" if dtype.width <= 32 else "uint64_t"
        members = "\n".join(
            f"static const {typ} {name} = {value};"
            for name, value in zip(dtype.element_names, dtype.element_values, strict=True)
        )
        out.append(
            f"typedef struct _{dtype.name} {{\n#ifdef __cplusplus\n{members}\n#endif\n{typ} m_value;\n}} {dtype.name};\ntypedef {typ} {dtype.name}ValueType;"
        )
    out += ["typedef int StopReasonValueType;\ntypedef struct {", CALLBACKS, "} FnPointerSocModel;"]
    if renode:
        out += ['#include "udb/stop_reason.h"', "LINKAGE int32_t tlib_init(char* cpu_name);"]
    else:
        out += [
            """
typedef void UdbHart;
LINKAGE UdbHart* libhart_create(const char* config_name, uint64_t hart_id, const char* config_file_path, FnPointerSocModel callbacks);
LINKAGE void libhart_set_pc(UdbHart* hart, uint64_t pc);
LINKAGE StopReasonValueType libhart_run_one(UdbHart* hart);
LINKAGE StopReasonValueType libhart_run_bb(UdbHart* hart);
LINKAGE StopReasonValueType libhart_run_n(UdbHart* hart, uint64_t n);
typedef struct _ExceptionClass {
#ifdef __cplusplus
  static const unsigned External = 1;
  static const unsigned Software = 2;
  static const unsigned Timer = 3;
#endif
} ExceptionClass;
typedef int ExceptionClassValueType;
LINKAGE void libhart_set_int(UdbHart* hart, PrivilegeModeValueType target_mode, ExceptionClassValueType klass);
LINKAGE void libhart_clear_int(UdbHart* hart, PrivilegeModeValueType target_mode, ExceptionClassValueType klass);
"""
        ]
    return "\n".join(out) + "\n"
