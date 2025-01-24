
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

class DenseMemory : public udb::Memory {
 public:
  DenseMemory(uint64_t size, uint64_t base_addr)
      : Memory(), m_offset(base_addr) {
    m_data.resize(size);
    m_addend = &m_data[0] - base_addr;
  }

  // subclasses only need to override these functions:
  virtual uint64_t read(uint64_t addr, size_t bytes) {
    switch (bytes) {
      case 1:
        return m_data[addr - m_offset];
      case 2:
        return *(uint16_t *)(addr + m_addend);
      case 4:
        return *(uint32_t *)(addr + m_addend);
      case 8:
        return *(uint64_t *)(addr + m_addend);
      default:
        udb_assert(false, "bad bytes");
    }
  }
  void write(uint64_t addr, uint64_t data, size_t bytes) override {
    switch (bytes) {
      case 1:
        m_data[addr - m_offset] = data;
      case 2:
        *(uint16_t *)(addr + m_addend) = data;
      case 4:
        *(uint32_t *)(addr + m_addend) = data;
      case 8:
        *(uint64_t *)(addr + m_addend) = data;
      default:
        udb_assert(false, "bad bytes");
    }
  }

 private:
  std::vector<uint8_t> m_data;
  uint64_t m_offset;
  uint8_t *m_addend = nullptr;
};

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

  DenseMemory mem(128, 0);
  auto hart =
      udb::HartFactory::create(opts.config_name, 0, opts.config_path, mem);

  return 0;
}
