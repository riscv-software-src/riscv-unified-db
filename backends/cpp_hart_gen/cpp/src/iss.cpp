
#include <fmt/core.h>

#include <CLI/CLI.hpp>
#include <string>

#include "udb/defines.hpp"
#include "udb/hart_factory.hxx"

struct Options {
  std::string config_name;
  std::filesystem::path config_path;
  bool show_configs;

  Options() : show_configs(false) {}
};

static const int PARSE_OK = 1234;
int parse_cmdline(int argc, char **argv, Options &options) {
  CLI::App app("Bare-bones ISS");
  app.add_option("-m,--model", options.config_name, "Hart model");
  app.add_option("-c,--cfg", options.config_path, "Hart configuration file");
  app.add_flag("-l,--list-configs", options.show_configs,
               "List available configurations");

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

  udb::Memory mem;
  auto hart =
      udb::HartFactory::create(opts.config_name, 0, opts.config_path, mem);

  return 0;
}
