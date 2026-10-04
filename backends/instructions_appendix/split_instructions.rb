#!/usr/bin/env ruby
# frozen_string_literal: true
#
# split_instructions.rb
#
# Splits an AsciiDoc instruction appendix produced by the riscv-unified-db
# `gen:instruction_appendix_adoc` task into four files:
#
#   unpriv_rv32.adoc  — Unprivileged instructions valid in RV32
#   unpriv_rv64.adoc  — Unprivileged instructions valid in RV64
#   priv_rv32.adoc    — Privileged instructions valid in RV32
#   priv_rv64.adoc    — Privileged instructions valid in RV64
#
# Instructions valid in both RV32 and RV64 appear in both width files.
#
# Privilege classification: an instruction is privileged if any of its
# "Included in" extensions begins with 'S' (supervisor/machine-mode in the
# RISC-V naming convention: Sm*, Ss*, Sh*, Sv*, or bare S) or 'H' (hypervisor).
#
# Usage:
#   ruby split_instructions.rb [INPUT] [OUTPUT_DIR]
#
#   INPUT       Path to all_instructions.adoc
#               Default: ./gen/instructions_appendix/all_instructions.adoc
#   OUTPUT_DIR  Directory to write the four output files
#               Default: same directory as INPUT

require "fileutils"
require "set"

HELP = <<~HELP
  Usage: ruby split_instructions.rb [OPTIONS] [INPUT] [OUTPUT_DIR]

  Splits all_instructions.adoc into four files by ISA base and privilege level.

  Arguments:
    INPUT       Path to all_instructions.adoc
                (default: ./gen/instructions_appendix/all_instructions.adoc)
    OUTPUT_DIR  Directory to write the four output files
                (default: same directory as INPUT)

  Options:
    -h, --help  Show this message

  Output files:
    unpriv_rv32.adoc  Unprivileged instructions for RV32
    unpriv_rv64.adoc  Unprivileged instructions for RV64
    priv_rv32.adoc    Privileged instructions for RV32
    priv_rv64.adoc    Privileged instructions for RV64

  Instructions supported in both RV32 and RV64 appear in both width output files.

  Privilege detection:
    An instruction is privileged if any required extension starts with 'S'
    (supervisor/machine-mode: Sm*, Ss*, Sh*, Sv*, or bare S) or 'H' (hypervisor).
HELP

if ARGV.include?("--help") || ARGV.include?("-h")
  puts HELP
  exit
end

# Extensions whose names match this pattern are privileged.
# RISC-V spec naming: all S-prefixed extensions are supervisor- or machine-mode;
# H is the hypervisor extension.
PRIV_EXT_RE = /\A[SH]/

input  = ARGV[0] || File.join("gen", "instructions_appendix", "all_instructions.adoc")
outdir = ARGV[1] || File.dirname(File.expand_path(input))

abort "Error: input file not found: #{input}" unless File.exist?(input)
FileUtils.mkdir_p(outdir)

# ── Parse ─────────────────────────────────────────────────────────────────────

lines    = File.readlines(input, encoding: "UTF-8")
header   = []
current  = nil
sections = []

lines.each do |line|
  if line.start_with?("[#udb:doc:inst:")
    current = [line]
    sections << current
  elsif current
    current << line
  else
    header << line
  end
end

warn "Parsed #{sections.size} instruction sections from #{input}"

# ── Classification helpers ────────────────────────────────────────────────────

# Returns [rv32_supported, rv64_supported] by inspecting the Base table:
#
#   | RV32 | RV64          <- header row
#                          <- blank separator
#   | &#x2713;             <- RV32 cell  (checkmark = supported, blank = not)
#   | &#x2713;             <- RV64 cell
#
def base_support(section)
  idx = section.find_index { |l| l.strip == "| RV32 | RV64" }
  return [false, false] unless idx

  # Skip the blank separator between the header row and the data rows.
  data = idx + 1
  data += 1 while data < section.size && section[data].strip.empty?
  return [false, false] if data >= section.size

  rv32 = section[data].include?("&#x2713;")
  rv64 = (data + 1) < section.size && section[data + 1].include?("&#x2713;")
  [rv32, rv64]
end

# Returns true if any "Included in" extension matches PRIV_EXT_RE.
# Extension lines in the table look like:  | *ExtName*
def privileged?(section)
  in_included = false
  section.each do |line|
    in_included = true if line.strip == "Included in::"
    next unless in_included
    return true if line =~ /^\| \*([^*]+)\*/ && $1.match?(PRIV_EXT_RE)
  end
  false
end

# Replace the document-level title (= Some Title) while preserving all attrs.
# Also strips the :wavedrom: attribute line because it contains a machine-local
# absolute path that must not be committed to riscv-isa-manual.
def titled_header(header, title)
  header
    .reject { |l| l.start_with?(":wavedrom:") }
    .map    { |l| l.start_with?("= ") ? "[appendix]\n== #{title}\n" : l }
    .join
end

# Increment every heading level in a section body by one = sign so that
# instruction headings (== name) are subordinate to the appendix title (== Title).
#
#   == add   →  === add
#   === foo  →  ==== foo
def increment_heading_levels(text)
  text.gsub(/^(=+) /) { "#{$1}= " }
end

# Returns the lowercase instruction name from a section's anchor/heading pair.
def insn_name_from_section(sect)
  idx = sect.find_index { |l| l.start_with?("[#udb:doc:inst:") }
  return nil unless idx

  heading = sect[idx + 1]
  m = heading&.match(/^=+ (.+)/)
  m ? m[1].strip.downcase : nil
end

# Replace the udb:doc:inst: block anchor with a plain insn: anchor so that
# the riscv-isa-manual's insnlink: macro can cross-reference the appendix.
#
# When skip_set is provided, instructions whose name is in that set get their
# anchor stripped rather than replaced — this prevents duplicate-ID warnings
# for instructions that appear in both the rv32 and rv64 split files.
#
#   [#udb:doc:inst:rv32:add]  →  [[insn:add]]
#   === add                      === add
def replace_udb_anchors(text, skip_set = nil)
  text.gsub(/\[#udb:doc:inst:[^\]]+\]\n(={3,} )(.+\n)/) do
    name = $2.chomp.downcase
    if skip_set&.include?(name)
      "#{$1}#{$2}"
    else
      "[[insn:#{name}]]\n#{$1}#{$2}"
    end
  end
end

# Convert Antora-style extension xrefs to the riscv-isa-manual ext: macro.
#
# The generated adoc uses Antora cross-references for extensions:
#   xref:exts:D.adoc#udb:doc:ext:D[D]
#
# riscv-isa-manual registers ext: as a custom inline macro (macros.rb).
# AsciiDoc's scanner finds ext:D[D] embedded inside those xref targets and
# errors with "macro ext:D[] does not accept arguments". Converting to the
# native macro fixes the error and renders the extension name correctly.
#
#   xref:exts:D.adoc#udb:doc:ext:D[D]  →  ext:D[]
EXT_XREF_RE = /xref:exts:[^.]+\.adoc#udb:doc:ext:[^\[]+\[([^\]]+)\]/

def convert_ext_xrefs(text)
  text.gsub(EXT_XREF_RE, 'ext:\1[]')
end

# ── Partition ─────────────────────────────────────────────────────────────────

buckets = { unpriv_rv32: [], unpriv_rv64: [], priv_rv32: [], priv_rv64: [] }

# Pre-pass: collect instruction names that appear in each rv64 bucket so we
# can suppress duplicate anchors in the corresponding rv32 file.  An instruction
# valid in both bases must carry [[insn:name]] in exactly one included file;
# we arbitrarily pick rv64 as the canonical home.
rv64_unpriv_names = Set.new
rv64_priv_names   = Set.new

sections.each do |sect|
  _rv32, rv64 = base_support(sect)
  next unless rv64

  name = insn_name_from_section(sect)
  next unless name

  privileged?(sect) ? rv64_priv_names.add(name) : rv64_unpriv_names.add(name)
end

sections.each do |sect|
  rv32, rv64 = base_support(sect)
  priv       = privileged?(sect)
  text       = sect.join
  skip       = priv ? rv64_priv_names : rv64_unpriv_names

  if priv
    buckets[:priv_rv32] << replace_udb_anchors(increment_heading_levels(convert_ext_xrefs(text)), skip) if rv32
    buckets[:priv_rv64] << replace_udb_anchors(increment_heading_levels(convert_ext_xrefs(text))) if rv64
  else
    buckets[:unpriv_rv32] << replace_udb_anchors(increment_heading_levels(convert_ext_xrefs(text)), skip) if rv32
    buckets[:unpriv_rv64] << replace_udb_anchors(increment_heading_levels(convert_ext_xrefs(text))) if rv64
  end
end

# ── Write output files ────────────────────────────────────────────────────────

TITLES = {
  unpriv_rv32: "Unprivileged RV32 Instructions",
  unpriv_rv64: "Unprivileged RV64 Instructions",
  priv_rv32:   "Privileged RV32 Instructions",
  priv_rv64:   "Privileged RV64 Instructions"
}.freeze

buckets.each do |key, blocks|
  path = File.join(outdir, "#{key}.adoc")
  File.open(path, "w", encoding: "UTF-8") do |f|
    f.write(titled_header(header, TITLES[key]))
    blocks.each { |b| f.write(b) }
    f.write("\n") # ensure single trailing newline
  end
  # Rewrite via String to strip any trailing blank lines before the final newline
  content = File.read(path, encoding: "UTF-8")
  File.write(path, content.rstrip + "\n", encoding: "UTF-8")
  puts "  #{path}  (#{blocks.size} instructions)"
end

total = buckets.values.sum(&:size)
warn "Done. #{total} instruction-file entries written (instructions in both bases counted twice)."
