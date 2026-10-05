<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Native Bits test replacement contract (review ID34)

The approved scope replaces `cpp/test/gen_test_bits.rb` and its six generated
translation units with handwritten native C++ randomized/property tests.
It does **not** substitute Python assertions for native coverage, introduce
another test-source generator or Ruby facade, or change retained hart/ISS
generation. The FP stimulus generator
(ID35) is retired separately and is not a dependency of this capability.

## Source trace and coverage map

The old Ruby generator implements an independent integer model, chooses seed
1234, and emits six files for widths **1, 8, 16, 32, 64, 128**. Its loop draws
two samples per operation at width 1 and ten at each other width; zero divisors
are skipped. All generated operands are unsigned and of the same width.
Each sample exercises all four Bits families with known values, checks result
value and width, and chooses six true comparisons among operands/result.
The existing handwritten `test_bits_directed.cpp` is retained unchanged.

| Old coverage / source | Native replacement obligation |
| --- | --- |
| `Bits::BINARY_ARITH_OPS`: `+`, `-`, `*` | Independent arbitrary-precision arithmetic followed by modulo 2^result-width; boundary cross product and randomized operands for all six widths and all four families. |
| `` `+ ``, `` `- `` | Check full carry/borrow and width `max(lhs.width,rhs.width)+1`, including the 128-to-129 native/GMP transition. |
| `` `* `` | Check full product and width `lhs.width+rhs.width`, including 64-to-128 and 128-to-256 transitions. |
| `/`, `%`; skip zero divisor | Check nonzero division/remainder against arbitrary precision. Unsigned division is exact Euclidean division; added signed tests use C++ truncation toward zero. Never execute native division by zero or signed minimum/-1 (undefined, not an exception contract). |
| `>>`, `>>>` (`sra`), `<<` | Logical shifts use raw unsigned bits, arithmetic right shift interprets the high bit as sign even on unsigned Bits. Check zero, 1, width-1, width, width+1, 2*width-1, plus randomized counts. |
| `` `<< `` (`widening_sll`) | Check mathematical left shift and width `lhs.width+count`, preserving bits for counts past the input width. Runtime return width is asserted, not inferred from storage capacity. |
| Four `gen_binary_expr_testcase` blocks | `_Bits`, `_RuntimeBits`, `_PossiblyUnknownBits`, `_PossiblyUnknownRuntimeBits`; unknown-capable objects have a zero unknown mask in this parity matrix. |
| `relation` and six operand/result comparisons | Assert all six relations (`== != < <= > >=`) in both directions for lhs/rhs, lhs/result, rhs/result against independent mathematical values. |
| Unsigned same-width inputs | Preserve those exact operation/type/width dimensions; extend with signed and mixed-width/signedness cases, sub-capacity runtime widths, and storage boundaries. |
| Masking in Ruby `Bits.new` | Explicit wrap, borrow, carry, product truncation, construction truncation, all-zero/all-one/high-bit/minimum/maximum patterns. |
| Deterministic generator seed | Fixed seed 1234 in native execution, plus explicit replay seed support and failure context (seed, case, type, widths, raw operands, operation/count). Randomness never rewrites source. |
| No unknown values or exception tests generated | Retain directed tests; add independent checks for unknown-value errors, unsupported arithmetic, invalid bounded runtime widths, and the documented negative infinite-precision unsigned error. Do not invent division-by-zero exceptions. |

`udb/bits.hpp` selects 8/16/32/64/128-bit native storage, then GMP storage.
The replacement uses GMP arithmetic as the test oracle at **every** width,
without using production `to_gmp`, `from_gmp`, Bits arithmetic, masks, or
comparisons to compute expected results. The oracle uses GMP modular reduction,
explicit signed decoding, and floor right shift; no native signed arithmetic
overflow or shifts by the storage width are needed to obtain an expectation.
Result decoding exports unsigned native storage limbs independently.

Additional width cases straddle 8/16/32/64/128-bit storage transitions;
the test matrix and exact implementation names will be recorded in the lane
report. Assertions are not weakened to accommodate production defects. A true
Bits defect is a separate blocker with a small native reproducer, not one of
the seven pre-existing unclassified register-storage failures or the retained
ISS `Invalid $schema` consumer failure.

## Native build boundary

The existing backend CMake builds generated hart libraries and links Bits tests
against `hart`, although the Bits implementation is header-only apart from
fmt/GMP. The new test-specific CMake entry point must support building directly
from `backends/cpp_hart_gen/cpp/test`, using only C++23, fmt, Catch2 and GMP,
with no architecture resolution, generated hart headers, Ruby, or Python.
Its targets are also integrated into the retained backend CMake test build.

The Ruby generator, six obsolete generated files and `tasks.rake` authoring
invocation are removed. Rake copies the handwritten C++ sources, shared test
header and CMake module into its generated tree. Its existing
`test_bits_random` aggregate and CTest invocation remain supported.
`regress-native-bits` also configures and runs all native Bits cases directly,
without depending on successful hart generation or unrelated register tests.
Python regression checks protect the retirement and CI wiring; they do not
replace native assertions.

## Validation and acceptance

Run only native Bits targets, cap compilation at one job, and serialize heavy
configure/build/test work with the session `heavy-tests.lock`. Reuse
already-fetched repository dependencies offline: exact Catch2 v3.16.0 and
fmt 12.2.0, matching the CMake declarations.
Record configure/build/test commands, seed replay results, native test counts,
any independent defect reproduction, and outstanding integration in
`gen/handoff/bits-report.md`. Source generation is not a build prerequisite.
No full repository regression or unrelated register/ISS repair is authorized.

## Implemented coverage and native review gate

`bits_property.hpp` implements the independent GMP oracle, boundary cross
products, 64 randomized arithmetic pairs and 64 randomized shift samples per
legacy width/family, result width/signedness checks and twelve directional
relation checks per operand pair. The six legacy-width cases are in
`test_bits_properties_{small,wide}.cpp`. Fixed signed versions of all six widths
are in `test_bits_properties_signed.cpp`. They use truncation-toward-zero
division and skip only zero divisors and minimum/-1.

`test_bits_properties_boundaries.cpp` adds widths 7/9/15/17/31/33/63/65/127
(all operations), 129 (arithmetic), unequal unsigned widths 7/17 and 64/128 in
both directions, unequal signed widths 7/17 in both directions, positive
mixed-signedness inputs and one-bit operands with wide shift counts.
`test_bits_properties_runtime.cpp` exercises unsigned known/unknown-capable
capacities 64/128 at active widths 1/7/8/9/16/17/31/32/33/63/64/65/127/128,
unequal active widths, fixed/runtime operands, and active-width construction
truncation. `test_bits_properties_contracts.cpp` covers oracle/replay sentinels,
constructor truncation and signed interpretation, unknown-value exceptions,
unsigned-only shift counts, non-default-constructible runtime classes,
bounded-width errors and negative unsigned infinite-precision rejection.

The resumed lane has explicit ownership of six narrow production fixes:
signed native storage conversion, the signed unknown-mask initializer, the GMP
sign-bit condition, unknown-capable runtime `sra` masking/sign fill, signed
runtime widening arithmetic, and active-width signed runtime access. The last
also corrects `get_ignore_unknown()`, relations and signed arithmetic at that
same active-sign boundary. These are native C++ defects, independent of Ruby
IDL compiler/registry behavior.

`test_bits_compile_defects.cpp` now contains continuously compiled Catch tests,
not excluded diagnostic targets. Together with `test_bits_runtime_defects.cpp`
it checks signed runtime addition/widening across capacities 32/64/128 and
smaller active widths, signed logical shifts with known/unknown masks, GMP
129-bit sign/oversized shifts, active-width signed access at capacities 64/128,
and known/unknown runtime sign propagation at capacities 64/128/129. The original
three literal semantic reproducers remain unchanged. The default-built
`test_bits_runtime_defects` target is registered with CTest and is also a
dependency of the compatibility aggregate. Original failure logs are retained.

Claude's first review held acceptance because widening and active-sign fixes
were incomplete across coupled members. Known runtime widening now consistently
uses typed operands for add/sub/mul; unknown-capable widening delegates to that
known implementation after retaining its explicit unknown checks. Signed
unknown-capable relations use active-width `get()`. Its signed arithmetic path
also uses typed runtime operands: the review log contained 400 division and
381 remainder value failures from evaluating the active sign at capacity width.
Unsigned and mixed-signedness arithmetic paths are unchanged.

`test_bits_properties_runtime_signed.cpp` enforces full arithmetic, all six
relations in both directions against operands/results, and all four shifts
for known/unknown-capable runtime capacities 64/128 at active widths
1/7/8/9/16/17/31/32/33/63/64/65/127/128. It includes boundary cross products,
64 random pairs at equal/unequal active widths, 64 random shift samples,
generic known fixed/runtime operands, unknown-error contracts and literal
width1/-1 widening-sub0, signed division/remainder and relation reproducers.
The independent oracle and all pre-review assertions are retained unchanged.

The follow-up native-only gate passed **31 property cases / 7,154,343 assertions**,
**8 defect cases / 20,852 assertions**, and the unchanged **56 directed cases /
493,948 assertions**, using seed 1234. Alternate native seed 4294967297 passed
all property/defect cases (7,156,153 and 20,852 assertions respectively).
CTest passed **95/95**. No cases are skipped or marked expected-failure to gain
green; actual results are not masked/normalized. The same independent reviewer
accepted the follow-up and reran its original signed-runtime probe: all
707,982 assertions passed. Shared backend integration remains a separate gate.

The review also identified unchanged limitations outside this replacement's
original same-family unsigned coverage: unsigned unknown-runtime arithmetic
with known-runtime operands can return storage-capacity width, and
mixed-signedness unknown-capable arithmetic can disagree with known-runtime
arithmetic. This migration does not claim those combinations are repaired.
They remain separate follow-up work, not relaxed assertions in the retained
or expanded matrices.

`UDB_BITS_SEED` is a decimal uint64 override; the default is 1234.
`std::mt19937_64` plus explicit width-labelled substreams makes sample generation
independent of Catch execution order and of library distribution algorithms.
CTest discovery fixes Catch's own seed to 1234. Each failure records native
seed, widths, signedness, sample/family, raw operands and operation/count.
Replay never writes test source.

The standalone CMake entry point and backend module build only handwritten
sources, fmt/Catch2 and GMP. `test_bits_random` is a compatibility aggregate depending on
`test_bits_properties` and `test_bits_runtime_defects`, not a source-generation
target. Backend property coverage instrumentation is retained.
`UDB_BITS_UBSAN` instruments property and defect targets. Bounded UBSan
validation passed **7 cases / 2,978 assertions** covering conversions, shifts,
unknown propagation and literal reproducers. Randomized signed arithmetic and
the complete repository were not sanitizer-qualified by that bounded run.

## Retained backend integration

Actual Rake asset rules prepared an isolated generated-layout tree, including
the new test header and CMake module. The unmodified backend CMake entry point
then built the compatibility aggregate and ran **39/39** property/defect CTest
cases, without building a hart or invoking test-source generation. Existing
native `db_data.cxx` and `enum.cxx` outputs supplied the unrelated hart target's
configure-time source paths; they were not compiled or used as a new hart
generation acceptance claim. No schema or register-storage repair was made.

GMP discovery probes headers and linking through the selected C++ compiler,
then links `gmpxx`/`gmp` by name. Host-side `find_library` paths must not leak
into `bin/g++` invocations that run in the toolchain container. The updated
probe/link wiring passed the backend's 39 cases and a standalone relink of
all targets plus the eight defect cases. Exact offline dependency caches,
one build job and the heavy-test lock were used. Logs are
`gen/handoff/bits-{rake-integration,backend-integration,toolchain-link}.log`.

See `gen/handoff/bits-report.md` for exact commands, cache versions, failing
reproducers and the original independent native review evidence.
