# Architectural Parameter Classification Taxonomy

This document defines the classification system used to categorize architectural
parameters extracted from the RISC-V privileged and unprivileged specifications.

Every parameter gets exactly one **class** and one **value type**.

---

## Parameter Classes

### `NORM_DIRECT` — Normative, Directly Configurable

An implementation-defined choice that the spec explicitly leaves to the
implementer. Not controlled by or derived from any CSR field.

**How to identify**: The spec says an implementer "may", "can", or "optionally"
choose a value, or describes a quantity whose value is not fixed by the spec.
The choice is made at design time and does not change at runtime via CSR writes.

**Typical spec wording**:
- "Implementations may implement zero, 16, or 64 PMP entries"
- "The number of bits in a single vector register, _VLEN_ ≥ ELEN"
- "MXLEN is a constant"

**Examples**: `MXLEN`, `NUM_PMP_ENTRIES`, `PHYS_ADDR_WIDTH`, `VLEN`, `ELEN`,
`CACHE_BLOCK_SIZE`, `TRAP_ON_UNIMPLEMENTED_INSTRUCTION`

**Disambiguation**:
- If the choice is controlled by a CSR field's legal values → `NORM_CSR_WARL`
- If the choice is about whether a CSR field is read-only vs read-write → `NORM_CSR_RW`
- If the behavior becomes determinate when software follows spec rules → `SW_RULE`

---

### `NORM_CSR_WARL` — Normative, CSR WARL Legal Values

The parameter defines the set of legal values that a WARL (Write Any, Read
Legal) CSR field will accept. When software writes an illegal value, the field
retains its previous value or takes an implementation-defined legal value.

**How to identify**: The spec describes a CSR field as "WARL" and the legal
values are implementation-defined. The parameter IS the set of legal values.

**Typical spec wording**:
- "The `mtvec` register is an MXLEN-bit WARL read/write register"
- "The MODE field is WARL"
- "A write to `hgatp` with an unsupported MODE value..."

**Examples**: `MTVEC_MODES`, `SATP_MODE_BARE`, `MSTATUS_FS_LEGAL_VALUES`,
`GSTAGE_MODE_BARE`, `SV39X4_TRANSLATION`

**Disambiguation**:
- If the field is described as WARL but the parameter controls whether the
  field is read-only vs read-write (not which values are legal) → `NORM_CSR_RW`
- If the WARL behavior is described in a NOTE block → still `NORM_CSR_WARL`
  (WARL field definitions are normative even when discussed in notes)

---

### `NORM_CSR_RW` — Normative, CSR Read-Write Behavior

The parameter controls whether a CSR or CSR field is read-only, read-write,
or has a specific fixed value. This is about the mutability of the field, not
the set of legal values.

**How to identify**: The spec says a field "may be read-only zero", "can be
read-only", or that the field's type (RO/RW) depends on implementation choices.

**Typical spec wording**:
- "The `mtvec` register ... can contain a read-only value"
- "Bits of `misa` that correspond to implemented extensions are writable..."
- "MBE, SBE, and UBE bits in `mstatus` are WARL fields" (where the parameter
  controls whether they are read-only-0, read-only-1, or read-write)

**Examples**: `MTVEC_ACCESS`, `MUTABLE_MISA_C`, `M_MODE_ENDIANNESS`,
`HSTATEEN_CONTEXT_TYPE`, `SCOUNTENABLE_EN`

**Disambiguation**:
- If the parameter controls which values are legal in a writable field → `NORM_CSR_WARL`
- If the parameter controls whether a CSR/feature exists at all → `NORM_DIRECT`
  (e.g., `TIME_CSR_IMPLEMENTED`, `MISA_CSR_IMPLEMENTED`)

---

### `SW_RULE` — Software-Deterministic

Behavior that appears implementation-defined but whose outcome is fully
determined if software follows the spec's prescribed rules (e.g., fencing,
cache operations, proper sequencing).

**How to identify**: The spec describes hardware behavior that varies by
implementation, but also prescribes software rules that make the outcome
predictable. Often involves hardware state updates that software can control
through proper synchronization.

**Typical spec wording**:
- "It is implementation-defined whether FS transitions to Dirty"
  (but software can prevent this by managing FS correctly)
- "dirtiness might not be tracked at all"
  (but software can use fencing to ensure correctness)

**Examples**: `HW_MSTATUS_FS_DIRTY_UPDATE`, `HW_MSTATUS_VS_DIRTY_UPDATE`

**Disambiguation**:
- If the behavior is truly a fixed design choice with no software workaround → `NORM_DIRECT`
- The key question: "Can software guarantee a specific outcome regardless of
  the implementation choice?" If yes → `SW_RULE`. If no → `NORM_DIRECT`.

---

### `NON_ISA` — Non-ISA / Platform

A choice that is outside the ISA scope — platform-level, electrical, or
physical rather than architectural. These are not governed by the ISA
specification.

**How to identify**: The choice involves physical characteristics, platform
integration, or debug infrastructure rather than instruction execution behavior.

**Typical spec wording**:
- "The reset vector is platform-specified"
- "NMI vector address is implementation-specific"

**Examples**: Reset vector address, NMI vector, physical memory attributes,
debug transport mechanism

---

### `NON_NORM` — Non-Normative

Text that appears in a NOTE, TIP, WARNING, or other informative block. These
blocks describe rationale, design intent, or implementation suggestions but
do not constitute requirements.

**How to identify**: The text is enclosed in AsciiDoc `[NOTE]`/`====` blocks,
or is explicitly labeled as informative.

**Critical rule**: Even if a NOTE block discusses implementation choices using
words like "may" or "optionally", the content is non-normative and should NOT
be extracted as a parameter. Only normative prose outside of such blocks
defines actual parameters.

**Example of a false positive (do NOT extract)**:
> [NOTE]
> Some platforms may choose to disallow speculatively writing FS to close a
> potential side channel.

This is a suggestion, not a requirement — no parameter.

---

### `DOC_RULE` — Documentation Rule

A requirement about how something should be documented, reported, or
described, rather than about architectural behavior.

**How to identify**: The spec requires reporting or documenting a value, but
the value itself is not an architectural choice that affects execution.

**Examples**: Requirements about what must appear in documentation, how
extensions should be described

---

### `UNKNOWN` — Needs Further Analysis

Cannot be confidently classified into any of the above categories. Use this
sparingly — it flags items for human review.

---

## Value Types

Value types are orthogonal to classes. Every parameter has exactly one.

| Type | Definition | Example |
|---|---|---|
| `binary` | Exactly 2 choices (boolean, or 2-value enum) | `TRAP_ON_UNIMPLEMENTED_INSTRUCTION` (true/false) |
| `enum` | Finite set of 3+ discrete values | `LRSC_RESERVATION_STRATEGY` (4 choices) |
| `range` | Integer range with min/max bounds | `NUM_PMP_ENTRIES` (0-64) |
| `set` | Subset selection from a fixed universe | `MTVEC_MODES` (subset of {0, 1}) |
| `bitmask` | Fixed-length boolean array (one bit per feature) | `SCOUNTENABLE_EN` (32 booleans) |
| `value` | Single unconstrained value (no enumerated choices or bounds) | `VLEN` (any power of 2 ≥ ELEN) |

---

## Decision Tree

When classifying a parameter, follow this order:

1. **Is the text in a NOTE/TIP/WARNING block?** → `NON_NORM`
2. **Is the choice about platform/physical/debug, not ISA?** → `NON_ISA`
3. **Is it about documenting/reporting, not behavior?** → `DOC_RULE`
4. **Does the text describe a WARL CSR field's legal values?** → `NORM_CSR_WARL`
5. **Does the text describe whether a CSR field is RO/RW/fixed?** → `NORM_CSR_RW`
6. **Does the behavior become deterministic with proper software?** → `SW_RULE`
7. **Is it a normative implementation choice?** → `NORM_DIRECT`
8. **None of the above?** → `UNKNOWN`
