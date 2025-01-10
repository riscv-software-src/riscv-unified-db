# frozen_string_literal: true

require_relative "database_obj"

# CSR definition
class Csr < DatabaseObject
  def ==(other)
    if other.is_a?(Csr)
      name == other.name
    else
      raise ArgumentError, "Csr is not comparable to #{other.class.name}"
    end
  end

  # @return [Integer] CSR address (the value passed as an immediate to csrrw, etc.)
  # @return [nil] if the CSR is indirect-accesss-only
  def address
    @data["address"]
  end

  # @return [String] Least-privileged mode that can access this CSR. One of ['m', 's', 'u', 'vs', 'vu']
  def priv_mode
    @data["priv_mode"]
  end

  def long_name
    @data["long_name"]
  end

  # @return [Integer] CSR address in VS/VU mode, if different from other modes
  # @return [nil] If the CSR is not accessible in VS/VU mode, or if it's address does not change in those modes
  def virtual_address
    @data["virtual_address"]
  end

  # @return [Integer] 32 or 64, the XLEN this CSR is exclusively defined in
  # @return [nil] if this CSR is defined in all bases
  def base = @data["base"]

  # @return [Boolean] true if this CSR is defined when XLEN is 32
  def defined_in_base32? = @data["base"].nil? || @data["base"] == 32

  # @return [Boolean] true if this CSR is defined when XLEN is 64
  def defined_in_base64? = @data["base"].nil? || @data["base"] == 64

  # @return [Boolean] true if this CSR is defined regardless of the effective XLEN
  def defined_in_all_bases? = @data["base"].nil?

  # @param design [Design] The design
  # @return [Boolean] Whether or not the format of this CSR changes when the effective XLEN changes in some mode
  def format_changes_with_xlen?(design)
    dynamic_length?(design) ||
      implemented_fields(design).any? do |f|
        f.dynamic_location?(design)
      end
  end

  # @param design [Design] The design
  # @return [Array<Idl::FunctionDefAst>] List of functions reachable from this CSR's sw_read or a field's sw_write function
  def reachable_functions(design)
    return @reachable_functions unless @reachable_functions.nil?

    fns = []

    if has_custom_sw_read?
      ast = pruned_sw_read_ast(design)
      symtab = design.symtab.deep_clone
      symtab.push(ast)
      fns.concat(ast.reachable_functions(symtab))
    end

    if design.multi_xlen?
      implemented_fields_for(design, 32).each do |field|
        fns.concat(field.reachable_functions(design, 32))
      end
      implemented_fields_for(design, 64).each do |field|
        fns.concat(field.reachable_functions(design, 64))
      end
    else
      implemented_fields_for(design, design.mxlen).each do |field|
        fns.concat(field.reachable_functions(design, design.mxlen))
      end
    end

    @reachable_functions = fns.uniq
  end

  # @param design [Design]
  # @return [Array<Idl::FunctionDefAst>] List of functions reachable from this CSR's sw_read or a field's sw_wirte function, irrespective of context
  def reachable_functions_unevaluated(design)
    return @reachable_functions_unevaluated unless @reachable_functions_unevaluated.nil?

    fns = []

    if has_custom_sw_read?
      ast = sw_read_ast(design)
      fns.concat(ast.reachable_functions_unevaluated(design))
    end

    fields.each do |field|
      fns.concat(field.reachable_functions_unevaluated(design))
    end

    @reachable_functions_unevaluated = fns.uniq
  end

  # @param design [Design] The design
  # @return [Boolean] Whether or not the length of the CSR depends on a runtime value
  #                   (e.g., mstatus.SXL)
  def dynamic_length?(design)
    return false if @data["length"].is_a?(Integer)

    # when a CSR is only defined in one base, its length can't change
    return false unless @data["base"].nil?

    case @data["length"]
    when "MXLEN"
      # mxlen can never change at runtime, so if we have it in the config, the length is not dynamic
      # if we don't have it in the config, we don't know what the length is
      design.mxlen.nil?
    when "SXLEN"
      # dynamic if either we don't know SXLEN or SXLEN is explicitly mutable
      [nil, 3264].include?(design.param_values["SXLEN"])
    when "VSXLEN"
      # dynamic if either we don't know VSXLEN or VSXLEN is explicitly mutable
      [nil, 3264].include?(design.param_values["VSXLEN"])
    else
      raise "Unexpected length"
    end
  end

  # @param design [Design]
  # @return [Integer] Smallest length of the CSR in any mode
  def min_length(design)
    case @data["length"]
    when "MXLEN", "SXLEN", "VSXLEN"
      32
    when Integer
      @data["length"]
    else
      raise "Unexpected length"
    end
  end

  # @param design [Design] The design (can be nil if the length is not dependent on a config parameter)
  # @param effective_xlen [Integer] The effective xlen, needed since some fields change location with XLEN. If the field location is not determined by XLEN, then this parameter can be nil
  # @return [Integer] Length, in bits, of the CSR, given effective_xlen
  # @return [nil] if the length cannot be determined from the design (e.g., because SXLEN is unknown and +effective_xlen+ was not provided)
  def length(design, effective_xlen = nil)
    case @data["length"]
    when "MXLEN"
      return design.mxlen unless design.mxlen.nil?

      if !@data["base"].nil?
        @data["base"]
      else
        # don't know MXLEN
        effective_xlen
      end
    when "SXLEN"
      if design.param_values.key?("SXLEN")
        if design.param_values["SXLEN"] == 3264
          effective_xlen
        else
          design.param_values["SXLEN"]
        end
      elsif !@data["base"].nil?
        # if this CSR is only available in one base, then we know its length
        @data["base"]
      else
        # don't know SXLEN
        effective_xlen
      end
    when "VSXLEN"
      if design.param_values.key?("VSXLEN")
        if design.param_values["VSXLEN"] == 3264
          effective_xlen
        else
          design.param_values["VSXLEN"]
        end
      elsif !@data["base"].nil?
        # if this CSR is only available in one base, then we know its length
        @data["base"]
      else
        # don't know VSXLEN
        effective_xlen
      end
    when Integer
      @data["length"]
    else
      raise "Unexpected length field for #{csr.name}"
    end
  end

  # @return [Integer] The largest length of this CSR in any valid mode/xlen for the config
  def max_length(design)
    return @data["base"] unless @data["base"].nil?

    case @data["length"]
    when "MXLEN"
      design.mxlen || 64
    when "SXLEN"
      if design.param_values.key?("SXLEN")
        if design.param_values["SXLEN"] == 3264
          64
        else
          design.param_values["SXLEN"]
        end
      else
        64
      end
    when "VSXLEN"
      if design.param_values.key?("VSXLEN")
        if design.param_values["VSXLEN"] == 3264
          64
        else
          design.param_values["VSXLEN"]
        end
      else
        64
      end
    when Integer
      @data["length"]
    else
      raise "Unexpected length field for #{csr.name}"
    end
  end

  # @return [String] IDL condition of when the effective xlen is 32
  def length_cond32
    case @data["length"]
    when "MXLEN"
      "CSR[misa].MXL == 0"
    when "SXLEN"
      "CSR[mstatus].SXL == 0"
    when "VSXLEN"
      "CSR[hstatus].VSXL == 0"
    else
      raise "Unexpected length #{@data['length']} for #{name}"
    end
  end

  # @return [String] IDL condition of when the effective xlen is 64
  def length_cond64
    case @data["length"]
    when "MXLEN"
      "CSR[misa].MXL == 1"
    when "SXLEN"
      "CSR[mstatus].SXL == 1"
    when "VSXLEN"
      "CSR[hstatus].VSXL == 1"
    else
      raise "Unexpected length"
    end
  end

  # @param design [Design] The design
  # @return [String] Pretty-printed length string
  def length_pretty(design, effective_xlen=nil)
    if dynamic_length?(design)
      cond =
        case @data["length"]
        when "MXLEN"
          "CSR[misa].MXL == %%"
        when "SXLEN"
          "CSR[mstatus].SXL == %%"
        when "VSXLEN"
          "CSR[hstatus].VSXL == %%"
        else
          raise "Unexpected length '#{@data['length']}'"
        end

      if effective_xlen.nil?
        <<~LENGTH
          #{length(design, 32)} when #{cond.sub('%%', '0')}
          #{length(design, 64)} when #{cond.sub('%%', '1')}
        LENGTH
      else
        "#{length(design, effective_xlen)}-bit"
      end
    else
      "#{length(design)}-bit"
    end
  end

  # list of modes that can potentially access the field
  def modes_with_access
    case @data["priv_mode"]
    when "M"
      ["M"]
    when "S"
      ["M", "S", "VS"]
    when "U"
      ["M", "S", "U", "VS", "VU"]
    when "VS"
      ["M", "S", "VS"]
    else
      raise "unexpected priv mode"
    end
  end

  # parse description field with asciidoctor, and return the HTML result
  #
  # @return [String] Parsed description in HTML
  def description_html
    Asciidoctor.convert description
  end

  # @param design [Design] The design
  # @return [Array<CsrField>] All implemented fields for this CSR at the given effective XLEN, sorted by location (smallest location first)
  #                           Excluded any fields that are defined by unimplemented extensions or a base that is not effective_xlen
  def implemented_fields_for(design, effective_xlen)
    @implemented_fields_for ||= {}
    key = [design.name, effective_xlen].hash

    return @implemented_fields_for[key] if @implemented_fields_for.key?(key)

    @implemented_fields_for[key] =
      implemented_fields(design).select do |f|
        !f.key?("base") || f.base == effective_xlen
      end
  end

  # @param design [Design] The design
  # @return [Array<CsrField>] All implemented fields for this CSR
  #                           Excluded any fields that are defined by unimplemented extensions
  def implemented_fields(design)
    return @implemented_fields unless @implemented_fields.nil?

    implemented_bases =
      if design.param_values["SXLEN"] == 3264 ||
         design.param_values["UXLEN"] == 3264 ||
         design.param_values["VSXLEN"] == 3264 ||
         design.param_values["VUXLEN"] == 3264
        [32, 64]
      else
        [design.param_values["XLEN"]]
      end

    @implemented_fields = fields.select do |f|
      f.exists_in_design?(design)
    end
  end

  # @return [Array<CsrField>] All known fields of this CSR
  def fields
    return @fields unless @fields.nil?

    @fields = @data["fields"].map { |field_name, field_data| CsrField.new(self, field_name, field_data) }
  end

  # @return [Array<CsrField>] All known fields of this CSR when XLEN == +effective_xlen+
  # equivalent to {#fields} if +effective_xlen+ is nil
  def fields_for(effective_xlen)
    fields.select { |f| effective_xlen.nil? || !f.key?("base") || f.base == effective_xlen }
  end

  # @return [Hash<String,CsrField>] Hash of fields, indexed by field name
  def field_hash
    @field_hash unless @field_hash.nil?

    @field_hash = {}
    fields.each do |field|
      @field_hash[field.name] = field
    end

    @field_hash
  end

  # @return [Boolean] true if a field named 'field_name' is defined in the csr, and false otherwise
  def field?(field_name)
    field_hash.key?(field_name.to_s)
  end

  # returns [CsrField,nil] field named 'field_name' if it exists, and nil otherwise
  def field(field_name)
    field_hash[field_name.to_s]
  end

  # @param design [Design] The design
  # @param effective_xlen [Integer] The effective XLEN to apply, needed when field locations change with XLEN in some mode
  # @return [Idl::BitfieldType] A bitfield type that can represent all fields of the CSR
  def bitfield_type(design, effective_xlen = nil)
    Idl::BitfieldType.new(
      "Csr#{name.capitalize}Bitfield",
      length(design, effective_xlen),
      fields_for(effective_xlen).map(&:name),
      fields_for(effective_xlen).map { |f| f.location(design, effective_xlen) }
    )
  end

  # @return [Boolean] true if the CSR has a custom sw_read function
  def has_custom_sw_read?
    @data.key?("sw_read()") && !@data["sw_read()"].empty?
  end

  # @param symtab [Idl::SymbolTable] Symbol table with globals
  def type_checked_sw_read_ast(symtab)
    @type_checked_sw_read_asts ||= {}
    ast = @type_checked_sw_read_asts[symtab.hash]
    return ast unless ast.nil?

    symtab_hash = symtab.hash
    symtab = symtab.global_clone
    symtab.push(ast)
    # all CSR instructions are 32-bit
    symtab.add(
      "__instruction_encoding_size",
      Idl::Var.new("__instruction_encoding_size", Idl::Type.new(:bits, width: 6), 32)
    )
    symtab.add(
      "__expected_return_type",
      Idl::Type.new(:bits, width: 128)
     )

    ast = sw_read_ast(symtab)
    symtab.design.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{name}].sw_read()"
    )
    symtab.pop
    symtab.release
    @type_checked_sw_read_asts[symtab_hash] = ast
  end

  # @return [FunctionBodyAst] The abstract syntax tree of the sw_read() function
  # @param design [Design] The design
  def sw_read_ast(symtab)
    raise ArgumentError, "Argument should be a symtab" unless symtab.is_a?(Idl::SymbolTable)

    return @sw_read_ast unless @sw_read_ast.nil?
    return nil if @data["sw_read()"].nil?

    # now, parse the function
    @sw_read_ast = symtab.design.idl_compiler.compile_func_body(
      @data["sw_read()"],
      return_type: Idl::Type.new(:bits, width: 128), # big int to hold special return values
      name: "CSR[#{name}].sw_read()",
      input_file: __source,
      input_line: source_line("sw_read()"),
      symtab:,
      type_check: false
    )

    raise "unexpected #{@sw_read_ast.class}" unless @sw_read_ast.is_a?(Idl::FunctionBodyAst)

    @sw_read_ast.set_input_file_unless_already_set(__source, source_line("sw_read()"))

    @sw_read_ast
  end

  def pruned_sw_read_ast(design)
    @pruned_sw_read_asts ||= {}
    ast = @pruned_sw_read_asts[design.name]
    return ast unless ast.nil?

    ast = type_checked_sw_read_ast(design.symtab)

    symtab = design.symtab.global_clone
    symtab.push(ast)
    # all CSR instructions are 32-bit
    symtab.add(
      "__instruction_encoding_size",
      Idl::Var.new("__instruction_encoding_size", Idl::Type.new(:bits, width: 6), 32)
    )
    symtab.add(
      "__expected_return_type",
      Idl::Type.new(:bits, width: 128)
    )

    ast = ast.prune(symtab)
    ast.freeze_tree(design.symtab)

    design.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{name}].sw_read()"
    )

    symtab.pop
    symtab.release

    @pruned_sw_read_asts[design.name] = ast
  end

  # @example Result for an I-type instruction
  #   {reg: [
  #     {bits: 7,  name: 'OP-IMM',    attr: ['{op_major_name}'], type: 8},
  #     {bits: 5,  name: 'rd',        attr: [''], type: 2},
  #     {bits: 3,  name: {funct3},    attr: ['{mnemonic}'], type: 8},
  #     {bits: 5,  name: 'rs1',       attr: [''], type: 4},
  #     {bits: 12, name: 'imm12',     attr: [''], type: 6}
  #   ]}
  #
  # @param design [Design] The design
  # @param effective_xlen [Integer,nil] Effective XLEN to use when CSR length is dynamic
  # @param exclude_unimplemented [Boolean] If true, do not create include unimplemented fields in the figure
  # @param optional_type [Integer] Wavedrom type (Fill color) for fields that are optional (not mandatory) in a partially-specified design
  # @return [Hash] A representation of the WaveDrom drawing for the CSR (should be turned into JSON for wavedrom)
  def wavedrom_desc(design, effective_xlen, exclude_unimplemented: false, optional_type: 2)
    desc = {
      "reg" => []
    }
    last_idx = -1

    field_list =
      if exclude_unimplemented
        implemented_fields_for(design, effective_xlen)
      else
        fields_for(effective_xlen)
      end

    field_list.sort! { |a, b| a.location(design, effective_xlen).min <=> b.location(design, effective_xlen).min }
    field_list.each do |field|

      if field.location(design, effective_xlen).min != last_idx + 1
        # have some reserved space
        n = field.location(design, effective_xlen).min - last_idx - 1
        raise "negative reserved space? #{n} #{name} #{field.location(design, effective_xlen).min} #{last_idx + 1}" if n <= 0

        desc["reg"] << { "bits" => n, type: 1 }
      end
      if design.partially_configured? && field.optional_in_design?(design)
        desc["reg"] << { "bits" => field.location(design, effective_xlen).size, "name" => field.name, type: optional_type }
      else
        desc["reg"] << { "bits" => field.location(design, effective_xlen).size, "name" => field.name, type: 3 }
      end
      last_idx = field.location(design, effective_xlen).max
    end
    if !field_list.empty? && (field_list.last.location(design, effective_xlen).max != (length(design, effective_xlen) - 1))
      # reserved space at the end
      desc["reg"] << { "bits" => (length(design, effective_xlen) - 1 - last_idx), type: 1 }
      # desc['reg'] << { 'bits' => 1, type: 1 }
    end
    desc["config"] = { "bits" => length(design, effective_xlen) }
    desc["config"]["lanes"] = length(design, effective_xlen) / 16
    desc
  end

  # @param design [Design]
  # @return [Boolean] whether or not the CSR is possibly implemented given the supplies config options
  def exists_in_design?(design)
    if design.fully_configured?
      (@data["base"].nil? || (design.possible_xlens.include? @data["base"])) &&
        design.transitive_implemented_ext_vers.any? { |ext_ver| defined_by?(ext_ver) }
    else
      (@data["base"].nil? || (design.possible_xlens.include? @data["base"])) &&
        design.prohibited_ext_reqs.none? { |ext_req| ext_req.satisfying_versions.any? { |ext_ver| defined_by?(ext_ver) } }
    end
  end

  # @param design [Design]
  # @return [Boolean] whether or not the CSR is optional in the config
  def optional_in_design?(design)
    raise "optional_in_design? should only be used by a partially-specified arch def" unless design.partially_configured?

    exists_in_design?(design) &&
      design.mandatory_ext_reqs.all? { |ext_req| ext_req.satisfying_versions.none? { |ext_ver| defined_by?(ext_ver) } }
  end
end
