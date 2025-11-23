# QEMU generator

## Usage

```sh
python3 generate_insn32_decode.py \
  --inst-dir ../../../spec/std/isa/inst/ \
  --extensions I,Zicsr \
  --arch RV64 \
  --output ./insn32.snippet
```

Arguments:

- `--extensions` – comma-separated list of enabled extensions. Use
  `--include-all` to bypass filtering.
- `--arch` – target architecture (`RV32`, `RV64`, or `BOTH`).
- `--output` – destination file (`-` for stdout).

Run with `--verbose` to see which instructions cannot yet be mapped to a QEMU
instruction format tag.
