# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "idlc/interfaces"

require_relative "database_obj"
require_relative "certifiable_obj"

module Udb

# CSR definition
class Csr < TopLevelDatabaseObject
  # Add all methods in this module to this type of database object.
  include CertifiableObject

  include Idl::Csr

  sig { override.returns(String) }
  attr_reader :name

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

  # @return [Boolean] Whether or not the CSR can be accessed by indirect address
  def indirect?
    @data.key?("indirect_address")
  end

  # @return [Integer] The indirect address
  def indirect_address
    @data["indirect_address"]
  end

  # @return [Integer] The indirect window slot
  def indirect_slot
    @data["indirect_slot"]
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

  sig { override.returns(T.nilable(Integer)) }
  def value
    return nil unless fields.all? { |f| f.type == "RO" }

    fields.reduce(0) { |val, f| val | (f.reset_value << f.location.begin) }
  end

  # can this CSR be implemented if +ext_name+ is not?
  sig { override.params(ext_name: String).returns(T::Boolean) }
  def implemented_without?(ext_name)
    raise "#{ext_name} is not an extension" if @cfg_arch.extension(ext_name).nil?

    defined_by_condition.satisfied_by? do |ext_req|
      if ext_req.name == ext_name
        false
      else
        @cfg_arch.possible_extension_versions.any? { |ext_ver| ext_req.satisfied_by?(ext_ver) }
      end
    end
  end

  def writable
    @data["writable"]
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

  # @return [Boolean] true if this CSR is defined when XLEN is xlen
  # @param xlen [32,64] base
  def defined_in_base?(xlen) = @data["base"].nil? || @data["base"] == xlen

  # @return [Boolean] Whether or not the format of this CSR changes when the effective XLEN changes in some mode
  def format_changes_with_xlen?
    dynamic_length? || \
      (defined_in_all_bases? && (possible_fields_for(32) != possible_fields_for(64))) || \
      possible_fields.any?(&:dynamic_location?)
  end

  # @param effective_xlen [Integer or nil] 32 or 64 for fixed xlen, nil for dynamic
  # @return [Array<Idl::FunctionDefAst>] List of functions reachable from this CSR's sw_read or a field's sw_write function
  def reachable_functions(effective_xlen = nil)
    raise ArgumentError, "effective_xlen is non-nil and is a #{effective_xlen.class} but must be an Integer" unless effective_xlen.nil? || effective_xlen.is_a?(Integer)
    return @reachable_functions unless @reachable_functions.nil?

    fns = []

    if has_custom_sw_read?
      xlens =
        if cfg_arch.multi_xlen?
          defined_in_all_bases? ? [32, 64] : [base]
        else
          [cfg_arch.possible_xlens[0]]
        end
      xlens.each do |xlen|
        ast = pruned_sw_read_ast(xlen)
        symtab = cfg_arch.symtab.deep_clone
        symtab.push(ast)
        fns.concat(ast.reachable_functions(symtab))
      end
    end

    if cfg_arch.multi_xlen?
      possible_fields_for(32).each do |field|
        fns.concat(field.reachable_functions(32))
      end
      possible_fields_for(64).each do |field|
        fns.concat(field.reachable_functions(64))
      end
    else
      possible_fields_for(cfg_arch.mxlen).each do |field|
        fns.concat(field.reachable_functions(cfg_arch.mxlen))
      end
    end

    @reachable_functions = fns.uniq
  end

  # @return [Boolean] Whether or not the length of the CSR depends on a runtime value
  #                   (e.g., mstatus.SXL)
  def dynamic_length?
    return false if @data["length"].is_a?(Integer)

    # when a CSR is only defined in one base, its length can't change
    return false unless @data["base"].nil?

    case @data["length"]
    when "MXLEN"
      # mxlen can never change at runtime, so if we have it in the config, the length is not dynamic
      # if we don't have it in the config, we don't know what the length is
      cfg_arch.mxlen.nil?
    when "SXLEN"
      # dynamic if either we don't know SXLEN or SXLEN is explicitly mutable
      [nil, 3264].include?(cfg_arch.param_values["SXLEN"])
    when "VSXLEN"
      # dynamic if either we don't know VSXLEN or VSXLEN is explicitly mutable
      [nil, 3264].include?(cfg_arch.param_values["VSXLEN"])
    when "XLEN"
      # must always have M-mode
      # SXLEN condition applies if S-mode is possible
      # VSXLEN condition applies if VS-mode is possible
      (cfg_arch.mxlen.nil?) || \
      (cfg_arch.possible_extensions.map(&:name).include?("S") && \
      [nil, 3264].include?(cfg_arch.param_values["SXLEN"])) || \
      (cfg_arch.possible_extensions.map(&:name).include?("H") && \
      [nil, 3264].include?(cfg_arch.param_values["VSXLEN"]))
    else
      raise "Unexpected length"
    end
  end

  # @param cfg_arch [ConfiguredArchitecture] Architecture definition
  # @return [Integer] Smallest length of the CSR in any mode
  def min_length
    case @data["length"]
    when "MXLEN", "SXLEN", "VSXLEN", "XLEN"
      @cfg_arch.possible_xlens.min
    when Integer
      @data["length"]
    else
      raise "Unexpected length"
    end
  end

  # @param effective_xlen [Integer or nil] 32 or 64 for fixed xlen, nil for dynamic
  sig { override.params(effective_xlen: T.nilable(Integer)).returns(T.nilable(Integer)) }
  def length(effective_xlen = nil)
    case @data["length"]
    when "MXLEN"
      return T.must(cfg_arch.mxlen) unless cfg_arch.mxlen.nil?

      if !@data["base"].nil?
        @data["base"]
      else
        # don't know MXLEN
        effective_xlen
      end
    when "SXLEN"
      if cfg_arch.param_values.key?("SXLEN")
        if cfg_arch.param_values["SXLEN"] == 3264
          effective_xlen
        else
          cfg_arch.param_values["SXLEN"]
        end
      elsif !@data["base"].nil?
        # if this CSR is only available in one base, then we know its length
        @data["base"]
      else
        # don't know SXLEN
        effective_xlen
      end
    when "VSXLEN"
      if cfg_arch.param_values.key?("VSXLEN")
        if cfg_arch.param_values["VSXLEN"] == 3264
          effective_xlen
        else
          cfg_arch.param_values["VSXLEN"]
        end
      elsif !@data["base"].nil?
        # if this CSR is only available in one base, then we know its length
        @data["base"]
      else
        # don't know VSXLEN
        effective_xlen
      end
    when "XLEN"
      effective_xlen
    when Integer
      @data["length"]
    else
      raise "Unexpected length field for #{name}"
    end
  end

  # @return [Integer] The largest length of this CSR in any valid mode/xlen for the config
  # sig { override.returns(Integer) }    dhower: sorbet doesn't think this is an override??
  sig { override.returns(Integer) }
  def max_length
    return @data["base"] unless @data["base"].nil?

    case @data["length"]
    when "MXLEN"
      cfg_arch.mxlen || 64
    when "SXLEN"
      if cfg_arch.param_values.key?("SXLEN")
        if cfg_arch.param_values["SXLEN"] == 3264
          64
        else
          cfg_arch.param_values["SXLEN"]
        end
      else
        64
      end
    when "VSXLEN"
      if cfg_arch.param_values.key?("VSXLEN")
        if cfg_arch.param_values["VSXLEN"] == 3264
          64
        else
          cfg_arch.param_values["VSXLEN"]
        end
      else
        64
      end
    when "XLEN"
      if cfg_arch.possible_extensions.map(&:name).include?("M")
        cfg_arch.mxlen || 64
      elsif cfg_arch.possible_extensions.map(&:name).include?("S")
        if cfg_arch.param_values.key?("SXLEN")
          if cfg_arch.param_values["SXLEN"] == 3264
            64
          else
            cfg_arch.param_values["SXLEN"]
          end
        else
          # SXLEN can never be greater than MXLEN
          cfg_arch.mxlen || 64
        end
      elsif cfg_arch.possible_extensions.map(&:name).include?("H")
        if cfg_arch.param_values.key?("VSXLEN")
          if cfg_arch.param_values["VSXLEN"] == 3264
            64
          else
            cfg_arch.param_values["VSXLEN"]
          end
        else
          # VSXLEN can never be greater than MXLEN or SXLEN
          if cfg_arch.param_values.key?("SXLEN")
            if cfg_arch.param_values["SXLEN"] == 3264
              64
            else
              cfg_arch.param_values["SXLEN"]
            end
          else
            cfg_arch.mxlen || 64
          end
        end
      else
        raise "Unexpected"
      end
    when Integer
      @data["length"]
    else
      raise "Unexpected length field for #{name}"
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
    when "XLEN"
      "(priv_mode() == PrivilegeMode::M && CSR[misa].MXL == 0) || (priv_mode() == PrivilegeMode::S && CSR[mstatus].SXL == 0) || (priv_mode() == PrivilegeMode::VS && CSR[hstatus].VSXL == 0)"
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
    when "XLEN"
      "(priv_mode() == PrivilegeMode::M && CSR[misa].MXL == 1) || (priv_mode() == PrivilegeMode::S && CSR[mstatus].SXL == 1) || (priv_mode() == PrivilegeMode::VS && CSR[hstatus].VSXL == 1)"
    else
      raise "Unexpected length"
    end
  end

  # @param effective_xlen [Integer or nil] 32 or 64 for fixed xlen, nil for dynamic
  # @return [String] Pretty-printed length string
  def length_pretty(effective_xlen=nil)
    raise ArgumentError, "effective_xlen is non-nil and is a #{effective_xlen.class} but must be an Integer" unless effective_xlen.nil? || effective_xlen.is_a?(Integer)
    if dynamic_length?
      cond =
        case @data["length"]
        when "MXLEN"
          "CSR[misa].MXL == %%"
        when "SXLEN"
          "CSR[mstatus].SXL == %%"
        when "VSXLEN"
          "CSR[hstatus].VSXL == %%"
        when "XLEN"
          "(priv_mode() == PrivilegeMode::M && CSR[misa].MXL == %%) || (priv_mode() == PrivilegeMode::S && CSR[mstatus].SXL == %%) || (priv_mode() == PrivilegeMode::VS && CSR[hstatus].VSXL == %%)"
        else
          raise "Unexpected length '#{@data['length']}'"
        end

      if effective_xlen.nil?
        [
          "* #{length(32)} when #{cond.sub('%%', '0')}",
          "* #{length(64)} when #{cond.sub('%%', '1')}"
        ].join("\n")
      else
        "#{length(effective_xlen)}-bit"
      end
    else
      "#{length()}-bit"
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
    when "D"
      ["M", "D"]
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

  # @param effective_xlen [Integer or nil] 32 or 64 for fixed xlen, nil for dynamic
  # @return [Array<CsrField>] All implemented fields for this CSR at the given effective XLEN, sorted by location (smallest location first)
  #                           Excluded any fields that are defined by unimplemented extensions or a base that is not effective_xlen
  def possible_fields_for(effective_xlen)

    raise ArgumentError, "effective_xlen is non-nil and is a #{effective_xlen.class} but must be an Integer" unless effective_xlen.nil? || effective_xlen.is_a?(Integer)

    @possible_fields_for ||= {}
    @possible_fields_for[effective_xlen] ||=
      possible_fields.select do |f|
        f.base.nil? || f.base == effective_xlen
      end
  end

  # @return [Array<CsrField>] All implemented fields for this CSR
  #                           Excluded any fields that are defined by unimplemented extensions
  sig {returns(T::Array[CsrField])}
  def possible_fields
    @possible_fields ||= fields.select do |f|
      f.exists_in_cfg?(cfg_arch)
    end
  end

  # @return [Array<CsrField>] All known fields of this CSR
  sig { override.returns(T::Array[CsrField]) }
  def fields
    return @fields unless @fields.nil?

    @fields = @data["fields"].map { |field_name, field_data| CsrField.new(self, field_name, field_data) }
  end

  # @param effective_xlen [Integer or nil] 32 or 64 for fixed xlen, nil for dynamic
  # @return [Array<CsrField>] All known fields of this CSR when XLEN == +effective_xlen+
  # equivalent to {#fields} if +effective_xlen+ is nil
  sig {params(effective_xlen: T.nilable(Integer)).returns(T::Array[CsrField])}
  def fields_for(effective_xlen)
    fields.select { |f| effective_xlen.nil? || f.base.nil? || f.base == effective_xlen }
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

  # @param effective_xlen [Integer or nil] 32 or 64 for fixed xlen, nil for dynamic
  # @return [Idl::BitfieldType] A bitfield type that can represent all fields of the CSR
  def bitfield_type(cfg_arch, effective_xlen = nil)
    Idl::BitfieldType.new(
      "Csr#{name.capitalize}Bitfield",
      length(effective_xlen),
      fields_for(effective_xlen).map(&:name),
      fields_for(effective_xlen).map { |f| f.location(effective_xlen) }
    )
  end

  # @return [Boolean] true if the CSR has a custom sw_read function
  def has_custom_sw_read?
    @data.key?("sw_read()") && !@data["sw_read()"].empty?
  end

  # @param effective_xlen [Integer or nil] 32 or 64 for fixed xlen, nil for dynamic
  def type_checked_sw_read_ast(effective_xlen)
    raise ArgumentError, "effective_xlen is non-nil and is a #{effective_xlen.class} but must be an Integer" unless effective_xlen.nil? || effective_xlen.is_a?(Integer)
    @type_checked_sw_read_asts ||= {}
    ast = @type_checked_sw_read_asts[effective_xlen.nil? ? :none : effective_xlen]
    return ast unless ast.nil?

    symtab = cfg_arch.symtab.global_clone
    symtab.push(ast)
    # all CSR instructions are 32-bit
    unless effective_xlen.nil?
      symtab.add(
        "__effective_xlen",
        Idl::Var.new("__effective_xlen", Idl::Type.new(:bits, width: 6), effective_xlen)
      )
    end
    symtab.add(
      "__instruction_encoding_size",
      Idl::Var.new("__instruction_encoding_size", Idl::Type.new(:bits, width: 6), 32)
    )
    symtab.add(
      "__expected_return_type",
      Idl::Type.new(:bits, width: 128)
     )

    ast = sw_read_ast(symtab)
    @cfg_arch.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{name}].sw_read()"
    )
    symtab.pop
    symtab.release
    @type_checked_sw_read_asts[effective_xlen.nil? ? :none : effective_xlen] = ast
  end

  # @return [FunctionBodyAst] The abstract syntax tree of the sw_read() function
  # @param cfg_arch [ConfiguredArchitecture] A configuration
  def sw_read_ast(symtab)
    raise ArgumentError, "Argument should be a symtab" unless symtab.is_a?(Idl::SymbolTable)

    return @sw_read_ast unless @sw_read_ast.nil?
    return nil if @data["sw_read()"].nil?

    # now, parse the function
    @sw_read_ast = @cfg_arch.idl_compiler.compile_func_body(
      @data["sw_read()"],
      return_type: Idl::Type.new(:bits, width: 128), # big int to hold special return values
      name: "CSR[#{name}].sw_read()",
      input_file: __source,
      input_line: source_line(["sw_read()"]),
      symtab:,
      type_check: false
    )

    raise "unexpected #{@sw_read_ast.class}" unless @sw_read_ast.is_a?(Idl::FunctionBodyAst)

    @sw_read_ast.set_input_file_unless_already_set(T.must(__source), source_line(["sw_read()"]))

    @sw_read_ast
  end

  # @param ast [Idl::AstNode] An abstract syntax tree that will be evaluated with the returned symbol table
  # @return [IdL::SymbolTable] A symbol table populated with globals and syms specific to this CSR
  def fill_symtab(ast, effective_xlen)
    symtab = @cfg_arch.symtab.global_clone
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
    if symtab.get("MXLEN").value.nil?
      symtab.add(
        "MXLEN",
        Idl::Var.new(
          "MXLEN",
          Idl::Type.new(:bits, width: 6, qualifiers: [:const]),
          effective_xlen,
          param: true
        )
      )
    end
    symtab
  end

  # @param effective_xlen [Integer or nil] 32 or 64 for fixed xlen, nil for dynamic
  def pruned_sw_read_ast(effective_xlen)
    raise ArgumentError, "effective_xlen is non-nil and is a #{effective_xlen.class} but must be an Integer" unless effective_xlen.nil? || effective_xlen.is_a?(Integer)
    @pruned_sw_read_ast ||= {}
    return @pruned_sw_read_ast[effective_xlen] unless @pruned_sw_read_ast[effective_xlen].nil?

    ast = type_checked_sw_read_ast(effective_xlen)

    symtab = fill_symtab(ast, effective_xlen)

    ast = ast.prune(symtab)
    ast.freeze_tree(@cfg_arch.symtab)

    @cfg_arch.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{name}].sw_read()"
    )

    symtab.pop
    symtab.release

    @pruned_sw_read_ast[effective_xlen] = ast
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
  # @param cfg_arch [ConfiguredArchitecture] A configuration
  # @param effective_xlen [Integer,nil] Effective XLEN to use when CSR length is dynamic
  # @param exclude_unimplemented [Boolean] If true, do not create include unimplemented fields in the figure
  # @param optional_type [Integer] Wavedrom type (Fill color) for fields that are optional (not mandatory) in a partially-specified cfg_arch
  # @return [Hash] A representation of the WaveDrom drawing for the CSR (should be turned into JSON for wavedrom)
  def wavedrom_desc(cfg_arch, effective_xlen, exclude_unimplemented: false, optional_type: 2)
    unless cfg_arch.is_a?(ConfiguredArchitecture)
      raise ArgumentError, "cfg_arch is a class #{cfg_arch.class} but must be a ConfiguredArchitecture"
    end
    raise ArgumentError, "effective_xlen is non-nil and is a #{effective_xlen.class} but must be an Integer" unless effective_xlen.nil? || effective_xlen.is_a?(Integer)

    desc = {
      "reg" => []
    }
    last_idx = -1

    field_list =
      if exclude_unimplemented
        possible_fields_for(effective_xlen)
      else
        fields_for(effective_xlen)
      end

    field_list.sort! { |a, b| a.location(effective_xlen).min <=> b.location(effective_xlen).min }
    field_list.each do |field|

      if field.location(effective_xlen).min != last_idx + 1
        # have some reserved space
        n = field.location(effective_xlen).min - last_idx - 1
        raise "negative reserved space? #{n} #{name} #{field.location(effective_xlen).min} #{last_idx + 1}" if n <= 0

        desc["reg"] << { "bits" => n, type: 1 }
      end
      if cfg_arch.partially_configured? && field.optional_in_cfg?(cfg_arch)
        desc["reg"] << { "bits" => field.location(effective_xlen).size, "name" => field.name, type: optional_type }
      else
        desc["reg"] << { "bits" => field.location(effective_xlen).size, "name" => field.name, type: 3 }
      end
      last_idx = T.cast(field.location(effective_xlen).max, Integer)
    end
    if !field_list.empty? && (field_list.last.location(effective_xlen).max != (T.must(length(effective_xlen)) - 1))
      # reserved space at the end
      desc["reg"] << { "bits" => (T.must(length(effective_xlen)) - 1 - last_idx), type: 1 }
      # desc['reg'] << { 'bits' => 1, type: 1 }
    end
    desc["config"] = { "bits" => length(effective_xlen) }
    desc["config"]["lanes"] = T.must(length(effective_xlen)) / 16
    desc
  end

  # @param cfg_arch [ConfiguredArchitecture] Architecture def
  # @return [Boolean] whether or not the CSR is possibly implemented given the supplied config options
  def exists_in_cfg?(cfg_arch)
    raise ArgumentError, "cfg_arch is a class #{cfg_arch.class} but must be a ConfiguredArchitecture" unless cfg_arch.is_a?(ConfiguredArchitecture)

    @exists_in_cfg ||=
      cfg_arch.possible_csrs.include?(self)
  end

  # @param cfg_arch [ConfiguredArchitecture] Architecture def
  # @return [Boolean] whether or not the CSR is optional in the config
  def optional_in_cfg?(cfg_arch)
    unless cfg_arch.is_a?(ConfiguredArchitecture)
      raise ArgumentError, "cfg_arch is a class #{cfg_arch.class} but must be a ConfiguredArchitecture"
    end
    raise "optional_in_cfg? should only be used by a partially-specified arch def" unless cfg_arch.partially_configured?

    # exists in config and isn't satisfied by some combo of mandatory extensions
    @optional_in_cfg ||=
      exists_in_cfg?(cfg_arch) &&
      !defined_by_condition.satisfied_by? do |defining_ext_req|
        cfg_arch.mandatory_extension_reqs.any? do |mand_ext_req|
          mand_ext_req.satisfying_versions.any? do |mand_ext_ver|
            defining_ext_req.satisfied_by?(mand_ext_ver)
          end
        end
      end
  end

  # @return [Boolean] Whether or not the presence of ext_ver affects this CSR definition
  def affected_by?(ext_ver)
    defined_by_condition.possibly_satisfied_by?(ext_ver) || fields.any? { |field| field.affected_by?(ext_ver) }
  end
end

end
