

class Array
  def to_cxx
    "{#{map(&:to_cxx).join(', ')}}"
  end
end

class Instruction
  def assembly_fmt(xlen)
    fmt = assembly.dup
    dvs = encoding(xlen).decode_variables
    dvs.each do |dv|
      fmt.gsub!(dv.name, "{}")
    end
    fmt
  end

  def assembly_fmt_args(xlen)
    args = []
    dvs = encoding(xlen).decode_variables
    dvs.each do |dv|
      if dv.name[0] == "x" || dv.name[0] == "r"
        args << "Reg(#{dv.name}()).to_string()"
      elsif dv.name[0] == "f"
        args << "Reg(#{dv.name}(), true).to_string()"
      else
        args << "#{dv.name}()"
      end
    end
    if args.empty?
      ""
    else
      ", #{args.reverse.join(', ')}"
    end
  end
end

class ExtensionRequirementExpression
  class LogicNode
    def to_cxx(&block)
      if type == :term
        yield @children[0].name, @children[0].requirement_specs_to_s
      elsif type == :not
        "!(#{@children[0].to_cxx(&block)})"
      elsif type == :and
        "(#{@children[0].to_cxx(&block)} && #{@children[1].to_cxx(&block)})"
      elsif type == :or
        "(#{@children[0].to_cxx(&block)} || #{@children[1].to_cxx(&block)})"
      end
    end
  end

  def to_cxx(&block)
    raise ArgumentError, "Missing block" unless block_given?
    raise ArgumentError, "Blcok expects two arguments" unless block.arity == 2

    to_logic_tree(expand: false).to_cxx(&block)
  end
end

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
      config_name = config_name.gsub("-", "_")
      case kind
      when :cfg
        config_name.camelize
      when :hart
        "#{config_name.camelize}_Hart"
      when :params
        "#{config_name.camelize}_Params"
      when :csr
        raise "Missing csr name" unless extras.size == 1

        "#{config_name.camelize}_#{extras[0].gsub(".", "_").capitalize}_Csr"
      when :csr_field
        raise "Missing csr name" unless extras.size == 2

        "#{config_name.camelize}_#{extras[0].gsub(".", "_").capitalize}_#{extras[1].capitalize}_Field"
      when :csr_container
        "#{config_name.camelize}_CsrContainer"
      when :csr_view
        raise "Missing csr name" unless extras.size == 1

        "#{config_name.camelize}_#{extras[0].gsub(".", "_").capitalize}_CsrView"
      when :inst
        raise "Missing Instruction name" unless extras.size == 1

        "#{config_name.camelize}_#{extras[0].gsub(".", "_").capitalize}_Inst"
      when :struct
        raise "Missing struct name" unless extras.size == 1

        "#{config_name.camelize}_#{extras[0]}_Struct"
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
