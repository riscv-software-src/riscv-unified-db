// SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
// SPDX-License-Identifier: BSD-3-Clause-Clear

#include <cassert>
#include <fstream>
#include "udb/db_data.hxx"
#include "udb/bitfield.hxx"
#include "udb/cfgs/cpp-smoke/params.hxx"

using namespace udb;

int main(int argc, char** argv) {
  assert(argc == 2);
  std::ifstream input(argv[1]);
  nlohmann::json json;
  input >> json;
  udb::Config cfg(json["implemented_extensions"], json["params"]);
  udb::CppSmoke_Params params(cfg);
  assert(params.MXLEN.value() == 32_b);
  assert(params.PHYS_ADDR_WIDTH.value() == 32_b);
  assert(params.M_MODE_ENDIANNESS.value() == "little");
  assert(cfg.ext_req_is_met(udb::ExtensionName::I, udb::VersionRequirement(">= 2.0"sv)) == udb::Yes);
  assert(cfg.ext_req_is_met(udb::ExtensionName::F, udb::VersionRequirement(">= 0"sv)) == udb::No);
  assert(udb::to_s(udb::PrivilegeMode{udb::PrivilegeMode::M}) == "M");
  assert(udb::PrivilegeMode::from_s("M").value() == udb::PrivilegeMode::M);
  assert(udb::DbData::SCHEMAS.at("config_schema.json").find("$id") != std::string::npos);
  auto pairs = nlohmann::json::array({{"Sm", "1.11.0"}, {"I", "2.1"}, {"Zicsr", "2.0"}});
  udb::Config legacy(pairs, json["params"]);
  udb::CppSmoke_Params legacy_params(legacy);
  assert(legacy_params.MXLEN.value() == params.MXLEN.value());
}
