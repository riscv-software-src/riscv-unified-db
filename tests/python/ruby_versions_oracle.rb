# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Transitional oracle for the low-level Ruby RISC-V version implementation.

require "json"

repo_root = File.expand_path("../..", __dir__)
$LOAD_PATH.unshift(File.join(repo_root, "tools", "ruby-gems", "udb", "lib"))
require "udb/version_spec"

# Sorbet resolves this constant when RequirementSpec#satisfied_by? is first called.
module Udb
  class Extension; end unless const_defined?(:Extension)
end

input = JSON.parse($stdin.read)

versions = input.fetch("versions").to_h do |text|
  begin
    version = Udb::VersionSpec.new(text)
    [text, {
      "accepted" => true,
      "canonical" => version.canonical,
      "rvi" => version.to_rvi_s,
      "components" => [version.major, version.minor, version.patch, version.pre]
    }]
  rescue ArgumentError => error
    [text, {"accepted" => false, "error" => error.class.name}]
  end
end

comparisons = input.fetch("comparisons").map do |left, right|
  Udb::VersionSpec.new(left) <=> Udb::VersionSpec.new(right)
end

requirements = input.fetch("requirements").map do |entry|
  requirement = Udb::RequirementSpec.new(entry.fetch("requirement"))
  extension = {
    "versions" => entry.fetch("versions", []).map do |metadata|
      metadata.transform_keys(&:to_s)
    end
  }
  requirement.satisfied_by?(entry.fetch("candidate"), extension)
end

original = Udb::VersionSpec.new("1.2.3")
bumped = original.increment_patch
decremented = original.decrement_patch

puts JSON.generate({
  "versions" => versions,
  "comparisons" => comparisons,
  "requirements" => requirements,
  "mutation_boundaries" => {
    "increment" => [bumped.to_s, bumped.canonical, bumped.eql?(original)],
    "decrement" => [decremented.to_s, decremented.canonical, decremented.eql?(original)]
  }
})
