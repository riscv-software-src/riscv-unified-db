// SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
// SPDX-License-Identifier: BSD-3-Clause-Clear

#include <fstream>
#include <memory>
#include <stdexcept>
#include "udb/hart_factory.hxx"
#include "udb/iss_soc_model.hpp"

int main(int argc, char** argv) {
  if (argc != 2) throw std::runtime_error("configuration directory argument");
  udb::IssSocModel soc(4096, 0);
  const auto names = udb::HartFactory::configs();
  if (names.size() != 2 || names[0] != "cpp-smoke" || names[1] != "cpp-second")
    throw std::runtime_error("configuration selectors");
  for (const auto name : names) {
    std::ifstream input(std::filesystem::path(argv[1]) / (std::string(name) + ".json"));
    nlohmann::json config;
    input >> config;
    std::unique_ptr<udb::HartBase<udb::IssSocModel>> hart(
        udb::HartFactory::create(std::string(name), 0, config, soc));
    hart->reset(0);
    hart->set_xreg(1, 19);
    if (hart->mxlen() != 32 || hart->xreg(1) != 19)
      throw std::runtime_error("selected hart");
  }
}
