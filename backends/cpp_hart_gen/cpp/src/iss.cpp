
#include <fmt/core.h>

#include <CLI/CLI.hpp>
#include <string>

#include "udb/defines.hpp"
#include "udb/elf_reader.hpp"
#include "udb/hart_factory.hxx"
#include "udb/inst.hpp"

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

class DenseMemory : public udb::Memory {
 public:
  DenseMemory(uint64_t size, uint64_t base_addr)
      : Memory(), m_offset(base_addr) {
    m_data.resize(size);
    m_addend = &m_data[0] - base_addr;
  }
  ~DenseMemory() = default;

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
    udb_assert((addr - m_offset) + bytes <= m_data.size(), "overflow");
    switch (bytes) {
      case 1:
        m_data[addr - m_offset] = data;
        break;
      case 2:
        *(uint16_t *)(addr + m_addend) = data;
        break;
      case 4:
        *(uint32_t *)(addr + m_addend) = data;
        break;
      case 8:
        *(uint64_t *)(addr + m_addend) = data;
        break;
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

  udb::ElfReader elf_reader(opts.elf_file_path.c_str());

  // how much memory do we need?
  auto range = elf_reader.mem_range();
  uint64_t memsz = range.second - range.first + 1;

  // round up to a page for good measure
  memsz = (memsz & ~0xfffull) + 0x1000;

  DenseMemory mem(memsz, range.first);
  auto hart =
      udb::HartFactory::create(opts.config_name, 0, opts.config_path, mem);
  auto tracer =
      udb::HartFactory::create_tracer("riscv-tests", opts.config_name, hart);
  hart->attach_tracer(tracer);
  hart->set_pc(elf_reader.loadLoadableSegments(mem));

  // get the first instruction
  while (true) {
    fmt::print("PC {:x}\n", hart->pc());
    uint32_t enc = mem.read(hart->pc(), 4);
    fmt::print("Encoding @ {:x}: {:x}\n", hart->pc(), enc);
    auto inst = hart->decode(hart->pc(), enc);
    if (inst == nullptr) {
      fmt::print(stderr, "Decode failed\n");
      return -1;
    }
    fmt::print("inst {}\n", inst->name());

    hart->set_next_pc(hart->pc() + inst->enc_len());
    try {
      inst->execute();
    } catch (const udb::ExitEvent &e) {
      if (e.code() == 0) {
        fmt::print("{}", e.what());
      } else {
        fmt::print(stderr, "{}", e.what());
      }
      return e.code();
    }
    hart->advance_pc();
  }

  return 0;
}
