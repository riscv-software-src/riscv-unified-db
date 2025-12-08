# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require "erb"

pend_template = <<~YAML
  # Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
  # SPDX-License-Identifier: BSD-3-Clause-Clear

  # yaml-language-server: $schema=../../../../../schemas/csr_schema.json

  $schema: csr_schema.json#
  kind: csr
  name: qc.mclicip<%= num %>
  long_name: IRQ Pending <%= num %>
  address: 0x<%= (0x7f0 + num).to_s(16) %>
  length: 32
  priv_mode: M
  definedBy:
    allOf:
      - xlen: 32
      - extension:
          name: Xqciint
  writable: true
  description: |
    Pending bits for IRQs <%= num*32 %>-<%= (num + 1)*32 - 1 %>
  fields:
    <%- 32.times do |i| -%>
    IRQ<%= num*32 + i %>:
      type: RW
      reset_value: 0
      location: <%= i %>
      description: IRQ<%= num*32 + i %> pending
    <%- end -%>
YAML

en_template = <<~YAML
  # Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
  # SPDX-License-Identifier: BSD-3-Clause-Clear

  # yaml-language-server: $schema=../../../../../schemas/csr_schema.json

  $schema: csr_schema.json#
  kind: csr
  name: qc.mclicie<%= num %>
  long_name: IRQ Enable <%= num %>
  address: 0x<%= (0x7f8 + num).to_s(16) %>
  length: 32
  priv_mode: M
  definedBy:
    allOf:
      - xlen: 32
      - extension:
          name: Xqciint
  writable: true
  description: |
    Enable bits for IRQs <%= num*32 %>-<%= (num + 1)*32 - 1 %>
  fields:
    <%- 32.times do |i| -%>
    IRQ<%= num*32 + i %>:
      type: RW
      reset_value: 0
      location: <%= i %>
      description: IRQ<%= num*32 + i %> enabled
    <%- end -%>
YAML

level_template = <<~YAML
  # Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
  # SPDX-License-Identifier: BSD-3-Clause-Clear

  # yaml-language-server: $schema=../../../../../schemas/csr_schema.json

  $schema: csr_schema.json#
  kind: csr
  name: qc.mclicilvl<%= num.to_s.rjust(2, "0") %>
  long_name: IRQ Level <%= num %>
  address: 0x<%= (0xbc0 + num).to_s(16) %>
  length: 32
  priv_mode: M
  definedBy:
    allOf:
      - xlen: 32
      - extension:
          name: Xqciint
          version: ">=0.4"
  writable: true
  description: |
    Level bits for IRQs <%= num*8 %>-<%= (num + 1)*8 - 1 %>
  fields:
    <%- 8.times do |i| -%>
    IRQ<%= num*8 + i %>:
      type: RW
      reset_value: 0
      location: <%= i * 4 + 3 %>-<%= i * 4 %>
      description: IRQ<%= num*8 + i %> level
    <%- end -%>
YAML

wp_start_template = <<~YAML
  # Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
  # SPDX-License-Identifier: BSD-3-Clause-Clear

  # yaml-language-server: $schema=../../../../../schemas/csr_schema.json

  $schema: csr_schema.json#
  kind: csr
  name: qc.mwpstartaddr<%= num %>
  long_name: Watchpoint start address for region <%= num %>
  address: 0x<%= (0x7d0 + num).to_s(16) %>
  length: 32
  priv_mode: M
  definedBy:
    allOf:
      - xlen: 32
      - extension:
          name: Xqciint
          version: ">=0.4"
  writable: true
  description: |
    Watchpoint start address for region <%= num %>
  fields:
    ADDR:
      type: RW
      reset_value: 0
      location: 31-0
      description: Watchpoint start address
YAML

wp_end_template = <<~YAML
  # Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
  # SPDX-License-Identifier: BSD-3-Clause-Clear

  # yaml-language-server: $schema=../../../../../schemas/csr_schema.json

  $schema: csr_schema.json#
  kind: csr
  name: qc.mwpendaddr<%= num %>
  long_name: Watchpoint end address for region <%= num %>
  address: 0x<%= (0x7d4 + num).to_s(16) %>
  length: 32
  priv_mode: M
  definedBy:
    allOf:
      - xlen: 32
      - extension:
          name: Xqciint
          version: ">=0.4"
  writable: true
  description: |
    Watchpoint end address for region <%= num %>
  fields:
    ADDR:
      type: RW
      reset_value: 0
      location: 31-0
      description: Watchpoint end address
YAML

root = File.dirname(__FILE__)

erb = ERB.new(pend_template, trim_mode: "-")
8.times do |num|
  File.write("#{root}/qc.mclicip#{num}.yaml", erb.result(binding))
end

erb = ERB.new(en_template, trim_mode: "-")
8.times do |num|
  File.write("#{root}/qc.mclicie#{num}.yaml", erb.result(binding))
end

erb = ERB.new(level_template, trim_mode: "-")
32.times do |num|
  File.write("#{root}/qc.mclicilvl#{num.to_s.rjust(2, "0")}.yaml", erb.result(binding))
end

erb = ERB.new(wp_start_template, trim_mode: "-")
4.times do |num|
  File.write("#{root}/qc.mwpstartaddr#{num}.yaml", erb.result(binding))
end

erb = ERB.new(wp_end_template, trim_mode: "-")
4.times do |num|
  File.write("#{root}/qc.mwpendaddr#{num}.yaml", erb.result(binding))
end
