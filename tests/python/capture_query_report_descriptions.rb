# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Independent evidence: the native resolver deletes a quoted scalar's blank
# line; even Psych agrees with the accepted Python source parser before that loss.
require "digest"
require "json"
require "yaml"

names = %w[MUTABLE_MISA_C MUTABLE_MISA_D MUTABLE_MISA_F MUTABLE_MISA_H MUTABLE_MISA_M MUTABLE_MISA_Q MUTABLE_MISA_S MUTABLE_MISA_U VMID_WIDTH]
output = names.to_h do |name|
  source = "spec/std/isa/param/#{name}.yaml"
  resolved = "gen/query-report-native/resolved_spec/_/param/#{name}.yaml"
  unless File.file?(resolved)
    resolved = "gen/query-report-native/show-parameter-MXLEN/resolved_spec/_/param/#{name}.yaml"
  end
  [name, {
    "source_sha256" => Digest::SHA256.file(source).hexdigest,
    "psych_source_description" => YAML.safe_load(File.read(source))["description"],
    "psych_native_resolved_description" => YAML.safe_load(File.read(resolved))["description"]
  }]
end
File.write("tests/python/fixtures/query_reports/native-description-observations.json", JSON.pretty_generate(output) + "\n")
File.binwrite(
  "tests/python/fixtures/query_reports/native-full-config.yaml",
  File.binread("cfgs/mc100-32-full-example.yaml")
)
auxiliary = {
  "description_command" => "bundle exec --gemfile /home/jcarlin/riscv-projects/riscv-unified-db/Gemfile ruby tests/python/capture_query_report_descriptions.rb",
  "condition_command" => "RUBYLIB=tools/ruby-gems/udb/lib:tools/ruby-gems/idlc/lib:tools/ruby-gems/udb_helpers/lib bundle exec --gemfile /home/jcarlin/riscv-projects/riscv-unified-db/Gemfile ruby tests/python/capture_query_report_conditions.rb",
  "required_outer_transport" => "UV_NO_SYNC=1 flock /home/jcarlin/.copilot/session-state/e7cf3328-386d-40d9-b677-2d92e44c2ebb/files/ruby.lock mise exec --no-deps --",
  "outputs" => %w[native-description-observations.json native-condition-observations.json native-full-config.yaml native-first.stdout.txt native-first.stderr.txt].to_h do |name|
    [name, Digest::SHA256.file("tests/python/fixtures/query_reports/#{name}").hexdigest]
  end
}
File.write("tests/python/fixtures/query_reports/native-auxiliary-manifest.json", JSON.pretty_generate(auxiliary) + "\n")
license = <<~LICENSE
  SPDX-FileCopyrightText: Qualcomm Technologies, Inc. and/or its subsidiaries.
  SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
  SPDX-License-Identifier: BSD-3-Clause-Clear
LICENSE
Dir.glob("tests/python/fixtures/query_reports/*.{txt,json}").each do |file|
  File.write("#{file}.license", license)
end
File.write("tests/python/fixtures/query_reports/native-full-config.yaml.license", license)
