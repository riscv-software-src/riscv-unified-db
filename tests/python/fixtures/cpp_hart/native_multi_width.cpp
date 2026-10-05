// SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
// SPDX-License-Identifier: BSD-3-Clause-Clear

#include <fstream>
#include <memory>
#include <stdexcept>
#include "udb/hart_factory.hxx"
#include "udb/iss_soc_model.hpp"

static void require(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}

int main(int argc, char** argv) {
  require(argc == 2, "configuration directory argument");
  udb::IssSocModel soc(4096, 0);
  const auto names = udb::HartFactory::configs();
  require(names.size() == 2 && names[0] == "cpp-smoke" && names[1] == "cpp-wide",
          "configuration selectors");
  for (const auto name : names) {
    const unsigned xlen = name == "cpp-smoke" ? 32 : 64;
    const uint64_t value = 0x1122334455667788ULL;
    const uint64_t expected = xlen == 32 ? 0x55667788ULL : value;
    std::ifstream input(std::filesystem::path(argv[1]) / (std::string(name) + ".json"));
    nlohmann::json config;
    input >> config;
    std::unique_ptr<udb::HartBase<udb::IssSocModel>> hart(
        udb::HartFactory::create(std::string(name), 0, config, soc));
    hart->reset(0);
    require(hart->mxlen() == xlen, "selected hart width");
    hart->set_xreg(1, value);
    require(hart->xreg(1) == expected, "per-hart register width");
    auto* scratch = hart->csr("mscratch");
    require(scratch != nullptr, "per-hart CSR lookup");
    scratch->hw_write(udb::PossiblyUnknownBits<64>{udb::Bits<64>{value}}, udb::Bits<8>{xlen});
    require(scratch->hw_read(udb::Bits<8>{xlen}).get() == expected, "per-hart CSR width");
    if (xlen == 64) {
      auto& wide = static_cast<udb::CppWide_Hart<udb::IssSocModel>&>(*hart);
      wide.execute_instruction(udb::Bits<32>{0x00108193});  // addi x3, x1, 1
      require(wide.xreg(3) == value + 1, "RV64 arithmetic preserves high bits");
      wide.set_xreg(1, 0x180000000ULL);
      wide.execute_instruction(udb::Bits<32>{0x0010811b});  // addiw x2, x1, 1
      require(wide.xreg(2) == 0xffffffff80000001ULL, "RV64 word arithmetic sign extension");
    }
  }
}
