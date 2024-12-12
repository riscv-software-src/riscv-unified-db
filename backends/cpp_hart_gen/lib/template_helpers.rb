
module CppHartGen
  module TemplateHelpers

    # get the name of a c++ class
    #
    # e.g.:
    #
    # name_of(:hart, cfg_arch)
    # name_of(:params, "rv64")
    def name_of(kind, cfg_arch_or_config_name, *extras)
      config_name = cfg_arch_or_config_name.is_a?(ConfiguredArchitecture) ? cfg_arch.name : cfg_arch_or_config_name
      case kind
      when :hart
        "#{config_name.camelize}_Hart"
      when :params
        "#{config_name.camelize}_Params"
      when :csr
        raise "Missing csr name" unless extras.size == 1

        "#{config_name.camelize}_#{extras[0].capitalize}_Csr"
      when :csr_field
        raise "Missing csr name" unless extras.size == 2

        "#{config_name.camelize}_#{extras[0].capitalize}_#{extras[1].capitalize}_Field"
      when :csr_container
        "#{config_name.camelize}_CsrContainer"
      when :csr_view
        raise "Missing csr name" unless extras.size == 1

        "#{config_name.camelize}_#{extras[0].capitalize}_CsrView"
      else
        raise "TODO: #{kind}"
      end
    end
  end

  class TemplateEnv
    attr_reader :cfg_arch
    def initialize(cfg_arch)
      @cfg_arch = cfg_arch
    end

    include TemplateHelpers

    def get_binding
      binding
    end
  end
end
