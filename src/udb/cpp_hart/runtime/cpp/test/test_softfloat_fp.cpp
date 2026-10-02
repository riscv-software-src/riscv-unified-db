#include <catch2/catch_test_macros.hpp>
#include <fmt/format.h>
#include <nlohmann/json.hpp>

#include <cstdint>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#include <udb/bits.hpp>
#include <udb/cfgs/rv64/hart.hxx>
#include <udb/csr.hpp>
#include <udb/db_data.hxx>
#include <udb/enum.hxx>

extern "C" {
#include <internals.h>
#include <softfloat.h>
}

using namespace udb;

namespace {

struct NullSocModel {
  uint64_t read_hpm_counter(uint64_t) { return 0; }
  uint64_t read_mcycle() { return 0; }
  uint64_t read_mtime() { return 0; }
  uint64_t sw_write_mcycle(uint64_t value) { return value; }
  void cache_block_zero(uint64_t) {}
  void eei_ecall_from_m() {}
  void eei_ecall_from_s() {}
  void eei_ecall_from_u() {}
  void eei_ecall_from_vs() {}
  void eei_ebreak() {}
  void memory_model_acquire() {}
  void memory_model_release() {}
  void notify_mode_change(PrivilegeMode::ValueType, PrivilegeMode::ValueType) {}
  void prefetch_instruction(uint64_t) {}
  void prefetch_read(uint64_t) {}
  void prefetch_write(uint64_t) {}
  void fence(uint8_t, uint8_t, uint8_t, uint8_t, uint8_t, uint8_t, uint8_t, uint8_t) {}
  void fence_tso() {}
  void ifence() {}
  void order_pgtbl_writes_before_vmafence() {}
  void order_pgtbl_reads_after_vmafence() {}
  uint64_t read_physical_memory_8(uint64_t) { return 0; }
  uint64_t read_physical_memory_16(uint64_t) { return 0; }
  uint64_t read_physical_memory_32(uint64_t) { return 0; }
  uint64_t read_physical_memory_64(uint64_t) { return 0; }
  void write_physical_memory_8(uint64_t, uint64_t) {}
  void write_physical_memory_16(uint64_t, uint64_t) {}
  void write_physical_memory_32(uint64_t, uint64_t) {}
  void write_physical_memory_64(uint64_t, uint64_t) {}
  int memcpy_from_host(uint64_t, const uint8_t*, uint64_t) { return 0; }
  int memcpy_to_host(uint8_t*, uint64_t, uint64_t) { return 0; }
  uint8_t atomic_check_then_write_32(uint64_t, uint32_t, uint32_t) { return 0; }
  uint8_t atomic_check_then_write_64(uint64_t, uint64_t, uint64_t) { return 0; }
  uint8_t atomically_set_pte_a(uint64_t, uint64_t, uint32_t) { return 0; }
  uint8_t atomically_set_pte_a_d(uint64_t, uint64_t, uint32_t) { return 0; }
  uint64_t atomic_read_modify_write_32(uint64_t, uint32_t, AmoOperation::ValueType) { return 0; }
  uint64_t atomic_read_modify_write_64(uint64_t, uint64_t, AmoOperation::ValueType) { return 0; }
  uint8_t pma_applies_Q_(PmaAttribute::ValueType, uint64_t, uint32_t) { return 1; }
  void delay(uint64_t) {}
  void iss_syscall(uint64_t, uint64_t) {}
  uint32_t read_device_32(uint64_t) { return 0; }
  void write_device_32(uint64_t, uint32_t) {}
  void sync_read_after_write_device(bool, uint32_t) {}
  void sync_write_after_read_device(bool, uint32_t) {}
};

using TestHart = Rv64_Hart<NullSocModel>;

struct TestVector {
  std::string source;
  std::string op;
  std::string rm;
  std::string muladd_op;
  std::string a;
  std::string b;
  std::string c;
};

uint64_t parse_hex_u64(const std::string& text) {
  size_t idx = 0;
  uint64_t value = std::stoull(text, &idx, 16);
  if (idx != text.size()) {
    throw std::runtime_error(fmt::format("invalid hex literal '{}'", text));
  }
  return value;
}

uint32_t parse_hex_u32(const std::string& text) {
  return static_cast<uint32_t>(parse_hex_u64(text));
}

std::vector<TestVector> load_vectors(const std::string& path) {
  std::ifstream in(path);
  if (!in) {
    throw std::runtime_error(fmt::format("unable to open vector file '{}'", path));
  }

  std::vector<TestVector> vectors;
  std::string line;
  while (std::getline(in, line)) {
    if (line.empty()) {
      continue;
    }

    auto obj = nlohmann::json::parse(line);
    TestVector v;
    v.source = obj.value("source", "");
    v.op = obj.at("op").get<std::string>();
    v.rm = obj.value("rm", "RNE");
    v.muladd_op = obj.value("muladd_op", "");
    v.a = obj.value("a", "");
    v.b = obj.value("b", "");
    v.c = obj.value("c", "");
    vectors.push_back(std::move(v));
  }

  return vectors;
}

RoundingMode parse_rounding_mode(std::string_view rm) {
  if (rm == "RNE") return RoundingMode{RoundingMode::RNE};
  if (rm == "RTZ") return RoundingMode{RoundingMode::RTZ};
  if (rm == "RDN") return RoundingMode{RoundingMode::RDN};
  if (rm == "RUP") return RoundingMode{RoundingMode::RUP};
  if (rm == "RMM") return RoundingMode{RoundingMode::RMM};
  throw std::runtime_error(fmt::format("unsupported rounding mode '{}'", rm));
}

uint_fast8_t get_softfloat_rm(std::string_view rm) {
  if (rm == "RNE") return softfloat_round_near_even;
  if (rm == "RTZ") return softfloat_round_minMag;
  if (rm == "RDN") return softfloat_round_min;
  if (rm == "RUP") return softfloat_round_max;
  if (rm == "RMM") return softfloat_round_near_maxMag;
  throw std::runtime_error(fmt::format("unsupported rounding mode '{}'", rm));
}

F32MulAddOp parse_muladd_op(std::string_view op) {
  if (op == "Softfloat_mulAdd_addC") return F32MulAddOp{F32MulAddOp::Softfloat_mulAdd_addC};
  if (op == "Softfloat_mulAdd_subC") return F32MulAddOp{F32MulAddOp::Softfloat_mulAdd_subC};
  if (op == "Softfloat_mulAdd_subProd") return F32MulAddOp{F32MulAddOp::Softfloat_mulAdd_subProd};
  throw std::runtime_error(fmt::format("unsupported muladd op '{}'", op));
}

uint_fast8_t get_softfloat_muladd_op(std::string_view op) {
  if (op == "Softfloat_mulAdd_addC") return 0;
  if (op == "Softfloat_mulAdd_subC") return softfloat_mulAdd_subC;
  if (op == "Softfloat_mulAdd_subProd") return softfloat_mulAdd_subProd;
  throw std::runtime_error(fmt::format("unsupported muladd op '{}'", op));
}

Config make_test_config() {
  nlohmann::json implemented_exts = nlohmann::json::array(
      {nlohmann::json::array({"I", "2.1.0"}),
       nlohmann::json::array({"M", "2.0.0"}),
       nlohmann::json::array({"Zicsr", "2.0.0"}),
       nlohmann::json::array({"Zifencei", "2.0.0"}),
       nlohmann::json::array({"F", "2.2.0"})});

  nlohmann::json param_values = nlohmann::json::object();
  param_values["MXLEN"] = 64;
  return Config(implemented_exts, param_values);
}

uint32_t read_fflags(TestHart& hart) {
  CsrBase* csr = hart.csr("fflags");
  if (csr == nullptr) {
    throw std::runtime_error("fflags CSR is unavailable");
  }
  return static_cast<uint32_t>(csr->sw_read(Bits<8>{hart.mxlen()}).to_defined().get());
}

void clear_fflags(TestHart& hart) {
  CsrBase* csr = hart.csr("fflags");
  if (csr == nullptr) {
    throw std::runtime_error("fflags CSR is unavailable");
  }
  const bool ok = csr->sw_write(Bits<64>{0}, Bits<8>{hart.mxlen()});
  if (!ok) {
    throw std::runtime_error("failed to clear fflags CSR");
  }
}

struct HartResult {
  uint64_t bits;
  uint32_t fflags;
};

uint64_t normalize_integer_result(const TestVector& v, uint32_t a32, uint64_t bits, uint32_t fflags) {
  if ((fflags & softfloat_flag_invalid) == 0) {
    return bits;
  }

  const bool is_nan_input = ((a32 & 0x7f800000U) == 0x7f800000U) && ((a32 & 0x007fffffU) != 0);

  if (v.op == "f32_to_i32") {
    return (!is_nan_input && (a32 & 0x80000000U)) ? 0x80000000ULL : 0x7fffffffULL;
  }
  if (v.op == "f32_to_ui32") {
    return (!is_nan_input && (a32 & 0x80000000U)) ? 0ULL : 0xffffffffULL;
  }
  if (v.op == "f32_to_i64") {
    return (!is_nan_input && (a32 & 0x80000000U)) ? 0x8000000000000000ULL : 0x7fffffffffffffffULL;
  }
  if (v.op == "f32_to_ui64") {
    return (!is_nan_input && (a32 & 0x80000000U)) ? 0ULL : 0xffffffffffffffffULL;
  }

  return bits;
}

void check_operation(TestHart& hart, const TestVector& v) {
  clear_fflags(hart);
  const auto rm = parse_rounding_mode(v.rm);

  softfloat_roundingMode = get_softfloat_rm(v.rm);
  softfloat_exceptionFlags = 0;

  const uint32_t a32 = v.a.empty() ? 0u : parse_hex_u32(v.a);
  const uint64_t a64 = v.a.empty() ? 0u : parse_hex_u64(v.a);
  const uint32_t b32 = v.b.empty() ? 0u : parse_hex_u32(v.b);
  const uint32_t c32 = v.c.empty() ? 0u : parse_hex_u32(v.c);

  HartResult hart_res{};
  HartResult softfloat_res{};

  if (v.op == "f32_add") {
    auto out = hart.f32_add(Bits<32>{a32}, Bits<32>{b32}, rm);
    hart_res = {out.to_defined().get(), read_fflags(hart)};
    softfloat_res.bits = f32_add(float32_t{a32}, float32_t{b32}).v;
    softfloat_res.fflags = softfloat_exceptionFlags;
  }
  else if (v.op == "f32_sub") {
    auto out = hart.f32_sub(Bits<32>{a32}, Bits<32>{b32}, rm);
    hart_res = {out.to_defined().get(), read_fflags(hart)};
    softfloat_res.bits = f32_sub(float32_t{a32}, float32_t{b32}).v;
    softfloat_res.fflags = softfloat_exceptionFlags;
  }
  else if (v.op == "f32_mul") {
    auto out = hart.f32_mul(Bits<32>{a32}, Bits<32>{b32}, rm);
    hart_res = {out.to_defined().get(), read_fflags(hart)};
    softfloat_res.bits = f32_mul(float32_t{a32}, float32_t{b32}).v;
    softfloat_res.fflags = softfloat_exceptionFlags;
  }
  else if (v.op == "f32_div") {
    auto out = hart.f32_div(Bits<32>{a32}, Bits<32>{b32}, rm);
    hart_res = {out.to_defined().get(), read_fflags(hart)};
    softfloat_res.bits = f32_div(float32_t{a32}, float32_t{b32}).v;
    softfloat_res.fflags = softfloat_exceptionFlags;
  }
  else if (v.op == "f32_sqrt") {
    auto out = hart.f32_sqrt(Bits<32>{a32}, rm);
    hart_res = {out.to_defined().get(), read_fflags(hart)};
    softfloat_res.bits = f32_sqrt(float32_t{a32}).v;
    softfloat_res.fflags = softfloat_exceptionFlags;
  }
  else if (v.op == "f32_muladd") {
    auto out = hart.f32_muladd(Bits<32>{a32},
                               Bits<32>{b32},
                               Bits<32>{c32},
                               parse_muladd_op(v.muladd_op),
                               rm);
    hart_res = {out.to_defined().get(), read_fflags(hart)};
    softfloat_res.bits = softfloat_mulAddF32(a32, b32, c32, get_softfloat_muladd_op(v.muladd_op)).v;
    softfloat_res.fflags = softfloat_exceptionFlags;
  }
  else if (v.op == "f32_to_i32") {
    auto out = hart.f32_to_i32(Bits<32>{a32}, rm);
    hart_res = {out.to_defined().get(), read_fflags(hart)};
    softfloat_res.bits = static_cast<uint32_t>(f32_to_i32(float32_t{a32}, softfloat_roundingMode, true));
    softfloat_res.fflags = softfloat_exceptionFlags;
  }
  else if (v.op == "f32_to_ui32") {
    auto out = hart.f32_to_ui32(Bits<32>{a32}, rm);
    hart_res = {out.to_defined().get(), read_fflags(hart)};
    softfloat_res.bits = static_cast<uint32_t>(f32_to_ui32(float32_t{a32}, softfloat_roundingMode, true));
    softfloat_res.fflags = softfloat_exceptionFlags;
  }
  else if (v.op == "f32_to_i64") {
    auto out = hart.f32_to_i64(Bits<32>{a32}, rm);
    hart_res = {out.to_defined().get(), read_fflags(hart)};
    softfloat_res.bits = static_cast<uint64_t>(f32_to_i64(float32_t{a32}, softfloat_roundingMode, true));
    softfloat_res.fflags = softfloat_exceptionFlags;
  }
  else if (v.op == "f32_to_ui64") {
    auto out = hart.f32_to_ui64(Bits<32>{a32}, rm);
    hart_res = {out.to_defined().get(), read_fflags(hart)};
    softfloat_res.bits = static_cast<uint64_t>(f32_to_ui64(float32_t{a32}, softfloat_roundingMode, true));
    softfloat_res.fflags = softfloat_exceptionFlags;
  }
  else if (v.op == "i32_to_f32") {
    auto out = hart.i32_to_f32(Bits<32>{a32}, rm);
    hart_res = {out.to_defined().get(), read_fflags(hart)};
    softfloat_res.bits = i32_to_f32(static_cast<int32_t>(a32)).v;
    softfloat_res.fflags = softfloat_exceptionFlags;
  }
  else if (v.op == "ui32_to_f32") {
    auto out = hart.ui32_to_f32(Bits<32>{a32}, rm);
    hart_res = {out.to_defined().get(), read_fflags(hart)};
    softfloat_res.bits = ui32_to_f32(a32).v;
    softfloat_res.fflags = softfloat_exceptionFlags;
  }
  else if (v.op == "i64_to_f32") {
    auto out = hart.i64_to_f32(Bits<64>{a64}, rm);
    hart_res = {out.to_defined().get(), read_fflags(hart)};
    softfloat_res.bits = i64_to_f32(static_cast<int64_t>(a64)).v;
    softfloat_res.fflags = softfloat_exceptionFlags;
  }
  else if (v.op == "ui64_to_f32") {
    auto out = hart.ui64_to_f32(Bits<64>{a64}, rm);
    hart_res = {out.to_defined().get(), read_fflags(hart)};
    softfloat_res.bits = ui64_to_f32(a64).v;
    softfloat_res.fflags = softfloat_exceptionFlags;
  }
  else {
    throw std::runtime_error(fmt::format("unsupported operation '{}'", v.op));
  }

  // Softfloat may generate different NaN payloads than the RISC-V canonical NaN.
  // In RISC-V, if an invalid operation occurs, the result MUST be the canonical NaN (0x7fc00000).
  if (softfloat_res.fflags & softfloat_flag_invalid) {
    if (v.op == "f32_add" || v.op == "f32_sub" || v.op == "f32_mul" || v.op == "f32_div" ||
        v.op == "f32_sqrt" || v.op == "f32_muladd" || v.op == "i32_to_f32" ||
        v.op == "ui32_to_f32" || v.op == "i64_to_f32" || v.op == "ui64_to_f32") {
      softfloat_res.bits = 0x7fc00000;
    }
  }

  softfloat_res.bits = normalize_integer_result(v, a32, softfloat_res.bits, softfloat_res.fflags);

  CHECK(hart_res.bits == softfloat_res.bits);
  CHECK(hart_res.fflags == softfloat_res.fflags);
}

std::string vector_file_path() {
#ifndef UDB_FP_DIRECTED_JSONL
  throw std::runtime_error("UDB_FP_DIRECTED_JSONL compile definition is missing");
#else
  return UDB_FP_DIRECTED_JSONL;
#endif
}

}  // namespace

TEST_CASE("Directed floating-point vectors execute on generated fp.idl helpers", "[cpp_hart][fp]") {
  const auto vectors = load_vectors(vector_file_path());

  NullSocModel soc;
  Config cfg = make_test_config();
  TestHart hart(0, soc, cfg);
  hart.reset(0);

  REQUIRE_FALSE(vectors.empty());

  for (const auto& v : vectors) {
    CAPTURE(v.source, v.op, v.rm, v.muladd_op, v.a, v.b, v.c);
    check_operation(hart, v);
  }
}
