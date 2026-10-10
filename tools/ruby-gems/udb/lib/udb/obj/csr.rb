# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "idlc/ast"
require "idlc/interfaces"
require "idlc/passes/reachable_functions"

require_relative "database_obj"
require_relative "has_fields"

module Udb

# CSR definition
  class Csr < TopLevelDatabaseObject
    # Frozen constant Type/Var objects reused across all fill_symtab calls
    BITS6_TYPE = Idl::Type.new(:bits, width: 6).freeze
    BITS6_CONST_TYPE = Idl::Type.new(:bits, width: 6, qualifiers: [:const]).freeze
    BITS128_TYPE = Idl::Type.new(:bits, width: 128).freeze
    ENCODING_SIZE_VAR = Idl::Var.new("__instruction_encoding_size", BITS6_TYPE, 32).freeze
    # Privilege mode => IDL expression naming the field that selects the effective
    # XLEN in that mode. Debug mode executes at MXLEN, so it shares M-mode's field.
    MODE_TO_XLEN_FIELD = {
      "M" => "CSR[misa].MXL",
      "D" => "CSR[misa].MXL",
      "S" => "CSR[mstatus].SXL",
      "U" => "CSR[mstatus].UXL",
      "VS" => "CSR[hstatus].VSXL",
      "VU" => "CSR[vsstatus].UXL"
    }.freeze
    XLEN_TO_ENCODING = { 32 => 0, 64 => 1 }.freeze
    # Add all methods in this module to this type of database object.
    include HasFields

    include Idl::Csr

    class MemoizedState < T::Struct
      prop :reachable_functions, T::Hash[T.any(Symbol, Integer), T::Array[Idl::FunctionDefAst]]
    end

    sig { params(data: T::Hash[String, T.untyped], data_path: T.any(String, Pathname), arch: ConfiguredArchitecture).void }
    def initialize(data, data_path, arch)
      super(data, data_path, arch)

      @memo = MemoizedState.new(reachable_functions: {})
    end

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

      fields.reduce(0) { |val, f| val | (T.cast(f.reset_value, Integer) << f.location.begin) }
    end
    alias reset_value value

    # @return [Integer] 32 or 64, the XLEN this CSR is exclusively defined in
    # @return [nil] if this CSR is defined in all bases
    sig { returns(T.nilable(Integer)) }
    def base
      return @base if defined?(@base)

      @base =
        if defined_by_condition.rv32_only?
          32
        elsif defined_by_condition.rv64_only?
          64
        else
          nil
        end
    end

    # @return [Boolean] true if this CSR is defined when XLEN is 32
    def defined_in_base32? = base != 64

    # @return [Boolean] true if this CSR is defined when XLEN is 64
    def defined_in_base64? = base != 32

    # @return [Boolean] true if this CSR is defined regardless of the effective XLEN
    def defined_in_all_bases? = base.nil?

    # @return [Boolean] true if this CSR is defined when XLEN is xlen
    # @param xlen [32,64] base
    def defined_in_base?(xlen) = xlen == 32 ? defined_in_base32? : defined_in_base64?

    # @return [Boolean] Whether or not the format of this CSR changes when the effective XLEN changes in some mode
    def format_changes_with_xlen?
      dynamic_length? || \
        (defined_in_all_bases? && (possible_fields_for(32) != possible_fields_for(64))) || \
        possible_fields.any?(&:dynamic_location?)
    end

    # @param effective_xlen [Integer or nil] 32 or 64 for fixed xlen, nil for dynamic
    # @return [Array<Idl::FunctionDefAst>] List of functions reachable from this CSR's sw_read or a field's sw_write function
    sig {
      params(
        effective_xlen: T.nilable(Integer),
        cache: T::Hash[Integer, Idl::AstNode::ReachableFunctionCacheType]
      )
      .returns(T::Array[Idl::FunctionDefAst])
    }
    def reachable_functions(effective_xlen = nil, cache = T.let({}, T::Hash[Integer, Idl::AstNode::ReachableFunctionCacheType]))
      cache_key = effective_xlen
      return @memo.reachable_functions[cache_key] unless @memo.reachable_functions[cache_key].nil?

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
          fns.concat(ast.reachable_functions(symtab, cache.fetch(xlen)))
        end
      end

      if cfg_arch.multi_xlen?
        possible_fields_for(32).each do |field|
          fns.concat(field.reachable_functions(32, cache.fetch(32)))
        end
        possible_fields_for(64).each do |field|
          fns.concat(field.reachable_functions(64, cache.fetch(64)))
        end
      else
        possible_fields_for(cfg_arch.mxlen).each do |field|
          fns.concat(field.reachable_functions(cfg_arch.mxlen, cache.fetch(T.must(cfg_arch.mxlen))))
        end
      end

      @memo.reachable_functions[cache_key] = fns.uniq
    end

    # @return [Boolean] Whether or not the length of the CSR depends on a runtime value
    #                   (e.g., mstatus.SXL)
    def dynamic_length?
      return false if @data["length"].is_a?(Integer)

      # when a CSR is only defined in one base, its length can't change
      return false unless base.nil?

      case @data["length"]
      when "MXLEN"
        # mxlen can never change at runtime, so if we have it in the config, the length is not dynamic
        # if we don't have it in the config, we don't know what the length is
        cfg_arch.mxlen.nil?
      when "SXLEN"
        # dynamic if either we don't know SXLEN or SXLEN is explicitly mutable
        cfg_arch.param_values["SXLEN"].nil? || cfg_arch.param_values["SXLEN"].size > 1
      when "VSXLEN"
        # dynamic if either we don't know VSXLEN or VSXLEN is explicitly mutable
        !cfg_arch.param_values.key?("VSXLEN") || cfg_arch.param_values["VSXLEN"].size > 1
      when "XLEN"
        modes_with_dynamic_xlen.any?
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

        if !base.nil?
          base
        else
          # don't know MXLEN
          effective_xlen
        end
      when "SXLEN"
        if cfg_arch.param_values.key?("SXLEN")
          if cfg_arch.param_values["SXLEN"].size > 1
            effective_xlen
          else
            cfg_arch.param_values["SXLEN"][0]
          end
        elsif !base.nil?
          # if this CSR is only available in one base, then we know its length
          base
        else
          # don't know SXLEN
          effective_xlen
        end
      when "VSXLEN"
        if cfg_arch.param_values.key?("VSXLEN")
          if cfg_arch.param_values["VSXLEN"].size > 1
            effective_xlen
          else
            cfg_arch.param_values["VSXLEN"][0]
          end
        elsif !base.nil?
          # if this CSR is only available in one base, then we know its length
          base
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
      return T.must(base) unless base.nil?

      case @data["length"]
      when "MXLEN"
        cfg_arch.mxlen || 64
      when "SXLEN"
        if cfg_arch.param_values.key?("SXLEN")
          if cfg_arch.param_values["SXLEN"].size > 1
            cfg_arch.param_values["SXLEN"].max
          else
            cfg_arch.param_values.fetch("SXLEN").fetch(0)
          end
        else
          64
        end
      when "VSXLEN"
        if cfg_arch.param_values.key?("VSXLEN")
          if cfg_arch.param_values["VSXLEN"].size > 1
            cfg_arch.param_values["VSXLEN"].max
          else
            cfg_arch.param_values["VSXLEN"][0]
          end
        else
          64
        end
      when "XLEN"
        if cfg_arch.possible_extensions.map(&:name).include?("Sm")
          cfg_arch.mxlen || 64
        elsif cfg_arch.possible_extensions.map(&:name).include?("S")
          if cfg_arch.param_values.key?("SXLEN")
            if cfg_arch.param_values.fetch("SXLEN").size > 1
              cfg_arch.param_values.fetch("SXLEN").max
            else
              cfg_arch.param_values.fetch("SXLEN").fetch(0)
            end
          else
            # SXLEN can never be greater than MXLEN
            cfg_arch.mxlen || 64
          end
        elsif cfg_arch.possible_extensions.map(&:name).include?("H")
          if cfg_arch.param_values.key?("VSXLEN")
            if cfg_arch.param_values["VSXLEN"].size > 1
              cfg_arch.param_values["VSXLEN"].max
            else
              cfg_arch.param_values["VSXLEN"][0]
            end
          else
            # VSXLEN can never be greater than MXLEN or SXLEN
            if cfg_arch.param_values.key?("SXLEN")
              if cfg_arch.param_values.fetch("SXLEN").size > 1
                cfg_arch.param_values.fetch("SXLEN").max
              else
                cfg_arch.param_values.fetch("SXLEN").fetch(0)
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

    # @return [Array<String>] Modes with access to this CSR whose effective XLEN can
    #                          vary in this configuration
    def modes_with_dynamic_xlen
      modes_with_access.select { |mode| cfg_arch.multi_xlen_in_mode?(mode) }
    end

    # @param xlen [Integer] 32 or 64
    # @return [String] IDL condition of when the effective xlen is +xlen+
    def length_cond(xlen)
      encoding = XLEN_TO_ENCODING.fetch(xlen)
      case @data["length"]
      when "MXLEN"
        "#{MODE_TO_XLEN_FIELD['M']} == #{encoding}"
      when "SXLEN"
        "#{MODE_TO_XLEN_FIELD['S']} == #{encoding}"
      when "VSXLEN"
        "#{MODE_TO_XLEN_FIELD['VS']} == #{encoding}"
      when "XLEN"
        modes = modes_with_dynamic_xlen
        raise "No mode with access to #{name} has a dynamic XLEN" if modes.empty?

        modes.map { |mode|
          "(priv_mode() == PrivilegeMode::#{mode} && #{MODE_TO_XLEN_FIELD.fetch(mode)} == #{encoding})"
        }.join(" || ")
      else
        raise "Unexpected length #{@data['length']} for #{name}"
      end
    end

    # @return [String] IDL condition of when the effective xlen is 32
    def length_cond32 = length_cond(32)

    # @return [String] IDL condition of when the effective xlen is 64
    def length_cond64 = length_cond(64)

    # @param effective_xlen [Integer or nil] 32 or 64 for fixed xlen, nil for dynamic
    # @return [String] Pretty-printed length string
    def length_pretty(effective_xlen = nil)
      raise ArgumentError, "effective_xlen is non-nil and is a #{effective_xlen.class} but must be an Integer" unless effective_xlen.nil? || effective_xlen.is_a?(Integer)
      if dynamic_length?
        if effective_xlen.nil?
          [
            "* #{length(32)} when #{length_cond(32)}",
            "* #{length(64)} when #{length_cond(64)}"
          ].join("\n")
        else
          "#{length(effective_xlen)}-bit"
        end
      else
        "#{length}-bit"
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

    # return list of extension requirements that must be implemented for this Csr to be defined
    #
    # will not include any extension requirements that are conditionally required
    # e.g., definedBy = Zblah if XLEN == 32; defining_extension_requirements will not include Zblah
    sig { returns(T::Array[ExtensionRequirement]) }
    def defining_extension_requirements
      @defining_extension_requirements ||=
        begin
          pb =
            Udb.create_progressbar(
              "Determining defining extensions for CSR #{name} [:bar] :current/:total",
              total: @cfg_arch.csrs.size,
              clear: true
            )
          @cfg_arch.extensions.map do |ext|
            pb.advance
            vers = ext.versions.select do |ext_ver|
              if defined_by_condition.mentions?(ext_ver)
                (-defined_by_condition & ext_ver.to_condition).unsatisfiable?
              end
            end
            unless vers.empty?
              ExtensionRequirement.create_from_ext_vers(vers)
            end
          end.compact
        end
    end

    # Sorbet override to satisfy Idl::Csr abstract method.
    # HasFields#fields returns CsrField instances but Sorbet can't see through
    # the untyped module, so we cast explicitly.
    sig { override.returns(T::Array[CsrField]) }
    def fields = T.unsafe(super)

    # @param effective_xlen [Integer or nil] 32 or 64 for fixed xlen, nil for dynamic
    # @return [Idl::BitfieldType] A bitfield type that can represent all fields of the CSR
    def bitfield_type(cfg_arch, effective_xlen = nil)
      @bitfield_type_cache ||= {}
      @bitfield_type_cache[effective_xlen] ||= Idl::BitfieldType.new(
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
    sig { params(effective_xlen: T.nilable(Integer)).returns(Idl::FunctionBodyAst) }
    def type_checked_sw_read_ast(effective_xlen)
      @type_checked_sw_read_asts ||= {}
      ast = @type_checked_sw_read_asts[effective_xlen.nil? ? :none : effective_xlen]
      return ast unless ast.nil?

      symtab = cfg_arch.symtab.global_clone
      symtab.push(ast)
      # all CSR instructions are 32-bit
      unless effective_xlen.nil?
        @xlen_var_cache ||= {}
        @xlen_var_cache[effective_xlen] ||= Idl::Var.new("__effective_xlen", BITS6_TYPE, effective_xlen).freeze
        symtab.add("__effective_xlen", @xlen_var_cache[effective_xlen])
      end
      symtab.add("__instruction_encoding_size", ENCODING_SIZE_VAR)
      symtab.add(
        "__expected_return_type",
        BITS128_TYPE
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

      return @sw_read_ast if instance_variable_defined?(:@sw_read_ast)
      return (@sw_read_ast = nil) if @data["sw_read()"].nil?

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

      @sw_read_ast
    end

    # @param ast [Idl::AstNode] An abstract syntax tree that will be evaluated with the returned symbol table
    # @return [IdL::SymbolTable] A symbol table populated with globals and syms specific to this CSR
    def fill_symtab(ast, effective_xlen)
      symtab = @cfg_arch.symtab.global_clone
      symtab.push(ast)
      # all CSR instructions are 32-bit
      if effective_xlen
        @xlen_var_cache ||= {}
        @xlen_var_cache[effective_xlen] ||= Idl::Var.new("__effective_xlen", BITS6_TYPE, effective_xlen).freeze
        symtab.add("__effective_xlen", @xlen_var_cache[effective_xlen])
      end
      symtab.add("__instruction_encoding_size", ENCODING_SIZE_VAR)
      symtab.add("__expected_return_type", BITS128_TYPE)
      if symtab.get("MXLEN").value.nil?
        # Cache per-xlen MXLEN var; use :nil_xlen sentinel so nil key doesn't collide with unset
        mxlen_key = effective_xlen.nil? ? :nil_xlen : effective_xlen
        @mxlen_var_cache ||= {}
        @mxlen_var_cache[mxlen_key] ||= Idl::Var.new(
          "MXLEN",
          BITS6_CONST_TYPE,
          effective_xlen,
          param: true
        ).freeze
        symtab.add("MXLEN", @mxlen_var_cache[mxlen_key])
      end
      symtab
    end

    # @param effective_xlen [Integer or nil] 32 or 64 for fixed xlen, nil for dynamic
    # @return [FunctionBodyAst] Pruned (but not re-type-checked) AST for sw_read()
    def pruned_sw_read_ast(effective_xlen)
      raise ArgumentError, "effective_xlen is non-nil and is a #{effective_xlen.class} but must be an Integer" unless effective_xlen.nil? || effective_xlen.is_a?(Integer)
      @pruned_sw_read_ast ||= {}
      return @pruned_sw_read_ast[effective_xlen] unless @pruned_sw_read_ast[effective_xlen].nil?

      ast = type_checked_sw_read_ast(effective_xlen)

      symtab = fill_symtab(ast, effective_xlen)

      ast = ast.prune(symtab)
      ast.freeze_tree(@cfg_arch.symtab)

      symtab.pop
      symtab.release

      @pruned_sw_read_ast[effective_xlen] = ast
    end

    # @param effective_xlen [Integer or nil] 32 or 64 for fixed xlen, nil for dynamic
    # @return [FunctionBodyAst] Pruned and re-type-checked AST for sw_read()
    #   Use this when you need the AST to be fully type-checked (e.g., for the type_check pass).
    #   For reachable_functions, use pruned_sw_read_ast directly.
    def type_checked_pruned_sw_read_ast(effective_xlen)
      raise ArgumentError, "effective_xlen is non-nil and is a #{effective_xlen.class} but must be an Integer" unless effective_xlen.nil? || effective_xlen.is_a?(Integer)
      @type_checked_pruned_sw_read_ast ||= {}
      return @type_checked_pruned_sw_read_ast[effective_xlen] if @type_checked_pruned_sw_read_ast.key?(effective_xlen)

      ast = pruned_sw_read_ast(effective_xlen)

      symtab = fill_symtab(type_checked_sw_read_ast(effective_xlen), effective_xlen)

      @cfg_arch.idl_compiler.type_check(
        ast,
        symtab,
        "CSR[#{name}].sw_read()"
      )

      symtab.pop
      symtab.release

      @type_checked_pruned_sw_read_ast[effective_xlen] = ast
    end

    # @param cfg_arch [ConfiguredArchitecture] Architecture def
    # @return [Boolean] whether or not the CSR is possibly implemented given the supplied config options
    sig { params(cfg_arch: ConfiguredArchitecture).returns(T::Boolean) }
    def exists_in_cfg?(cfg_arch)
      @exists_in_cfg ||= defined_by_condition.could_be_satisfied_by_cfg_arch?(cfg_arch)
    end
  end

end
