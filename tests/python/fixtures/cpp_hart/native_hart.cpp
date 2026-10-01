// SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
// SPDX-License-Identifier: BSD-3-Clause-Clear

#include <fstream>
#include <stdexcept>
#include "udb/cfgs/cpp-smoke/hart.hxx"
#include "udb/iss_soc_model.hpp"

using namespace udb;

static void require(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}

int main(int argc, char** argv) {
  require(argc == 2, "generated configuration argument");
  std::ifstream input(argv[1]);
  nlohmann::json json;
  input >> json;
  Config config(json["implemented_extensions"], json["params"]);
  IssSocModel soc(4096, 0);
  CppSmoke_Hart<IssSocModel> hart(0, soc, config);
  hart.reset(0);
  require(hart.mxlen() == 32 && hart.pc() == 0, "RV32 reset");
  hart.set_xreg(0, 42);
  require(hart.xreg(0) == 0, "zero register");
  auto* decoded = hart._decode(Bits<32>{0}, Bits<32>{0x00500093});
  require(decoded && decoded->name() == "addi", "addi decoding");
  require(decoded->srcRegs().size() == 1 && decoded->dstRegs().size() == 1,
          "decoded register interface");
  decoded->execute();
  delete decoded;
  require(hart.xreg(1) == 5, "addi execution");
  hart.execute_instruction(Bits<32>{0xfff08113});
  require(hart.xreg(2) == 4, "signed immediate execution");
  auto* scratch = hart.csr("mscratch");
  require(scratch != nullptr, "CSR namespace");
  scratch->hw_write(PossiblyUnknownBits<64>{42_b}, Bits<8>{32});
  require(scratch->hw_read(Bits<8>{32}).get() == 42, "CSR write/read");
  hart.reset(16);
  require(hart.pc() == 16, "second reset");
  return 0;
}
