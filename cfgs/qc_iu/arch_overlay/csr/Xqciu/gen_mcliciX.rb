
require 'erb'

pend_template = <<~YAML
  # yaml-language-server: $schema=../../../../../schemas/csr_schema.json

  qc.mclicip<%= num %>:
    long_name: IRQ Pending <%= num %>
    address: 0x<%= (0x7f0 + num).to_s(16) %>
    length: 32
    priv_mode: M
    definedBy: Xqciu
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
  # yaml-language-server: $schema=../../../../../schemas/csr_schema.json

  qc.mclicie<%= num %>:
    long_name: IRQ Enable <%= num %>
    address: 0x<%= (0x7f0 + num).to_s(16) %>
    length: 32
    priv_mode: M
    definedBy: Xqciu
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

root = File.dirname(__FILE__)

erb = ERB.new(pend_template, trim_mode: '-')
8.times do |num|
  File.write("#{root}/qc.mclicip#{num}.yaml", erb.result(binding))
end

erb = ERB.new(en_template, trim_mode: '-')
8.times do |num|
  File.write("#{root}/qc.mclicie#{num}.yaml", erb.result(binding))
end
