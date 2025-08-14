
#include <fmt/core.h>

#include <CLI/CLI.hpp>
#include <string>

#include "udb/defines.hpp"
#include "udb/elf_reader.hpp"
#include "udb/hart_factory.hxx"
#include "udb/inst.hpp"
#include "udb/iss_soc_model.hpp"

struct Options {
  std::string config_name;
  std::filesystem::path config_path;
  bool show_configs;
  std::string elf_file_path;

  Options() : show_configs(false) {}
};

static const int PARSE_OK = 1234;
int parse_cmdline(int argc, char **argv, Options &options) {
  CLI::App app("Bare-bones ISS");
  app.add_option("-m,--model", options.config_name, "Hart model");
  app.add_option("-c,--cfg", options.config_path, "Hart configuration file");
  app.add_flag("-l,--list-configs", options.show_configs,
               "List available configurations");

  app.add_option("elf_file", options.elf_file_path, "File to run");

  CLI11_PARSE(app, argc, argv);
  return PARSE_OK;
}

int main(int argc, char **argv) {
  Options opts;
  int ret;
  if ((ret = parse_cmdline(argc, argv, opts)) != PARSE_OK) {
    return ret;
  }

  if (opts.show_configs) {
    for (auto &config : udb::HartFactory::configs()) {
      fmt::print("{}\n", config);
    }
    return 0;
  }

  if (opts.config_path.empty()) {
    fmt::print("No configuration file provided\n");
    return 1;
  }

  udb::ElfReader elf_reader(opts.elf_file_path.c_str());

  // how much memory do we need?
  auto range = elf_reader.mem_range();
  uint64_t memsz = range.second - range.first + 1;

  // round up to a page for good measure
  memsz = (memsz & ~0xfffull) + 0x1000;

  udb::IssSocModel soc(memsz, range.first);

  auto hart = udb::HartFactory::create<udb::IssSocModel>(opts.config_name, 0,
                                                         opts.config_path, soc);
  auto tracer = udb::HartFactory::create_tracer<udb::IssSocModel>(
      "riscv-tests", opts.config_name, hart);
  hart->attach_tracer(tracer);
  auto entry_pc = elf_reader.loadLoadableSegments(soc);
  hart->reset(entry_pc);

  while (true) {
    auto stop_reason = hart->run_n(100);
    if (stop_reason != StopReason::InstLimitReached &&
        stop_reason != StopReason::Exception) {
      if (stop_reason == StopReason::ExitSuccess) {
        fmt::print("SUCCESS - {}\n", hart->exit_reason());
        break;
      } else if (stop_reason == StopReason::ExitFailure) {
        fmt::print(stderr, "FAIL - {}\n", hart->exit_reason());
        break;
      } else {
        fmt::print("EXIT - {}\n", hart->exit_reason());
        break;
      }
    }
  }
  return hart->exit_code();
}
