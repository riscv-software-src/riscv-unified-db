# Copyright (c) AINEKKO.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require_relative "csr_field"

module Udb

# Shared field-management methods for register-like objects (CSR, MMR).
#
# Includers must provide:
#   - length(effective_xlen)  — register width in bits
#   - max_length              — largest possible width
#   - cfg_arch                — ConfiguredArchitecture
#   - name                    — register name (String)
#   - defined_by_condition    — ExtensionRequirement condition
#   - exists_in_cfg?(cfg_arch)
module HasFields
  # @return [Array<CsrField>] All known fields of this register
  def fields
    return @fields unless @fields.nil?

    @fields =
      if @data["fields"].nil?
        []
      else
        @data["fields"].map { |field_name, field_data| CsrField.new(self, field_name, field_data) }
      end
  end

  # @param effective_xlen [Integer or nil] 32 or 64 for fixed xlen, nil for dynamic
  # @return [Array<CsrField>] All known fields when XLEN == +effective_xlen+
  def fields_for(effective_xlen)
    fields.select { |f| effective_xlen.nil? || f.base.nil? || f.base == effective_xlen }
  end

  # @return [Hash<String,CsrField>] Hash of fields, indexed by field name
  def field_hash
    return @field_hash unless @field_hash.nil?   # <-- CHANGED: added 'return'

    @field_hash = {}
    fields.each do |field|
      @field_hash[field.name] = field
    end

    @field_hash
  end

  # @return [Boolean] true if a field named 'field_name' is defined
  def field?(field_name)
    field_hash.key?(field_name.to_s)
  end

  # @return [CsrField,nil] field named 'field_name' if it exists, and nil otherwise
  def field(field_name)
    field_hash[field_name.to_s]
  end

  # @return [Array<CsrField>] All implemented fields, excluding fields defined by unimplemented extensions
  def possible_fields
    @possible_fields ||= fields.select do |f|
      f.exists_in_cfg?(cfg_arch)
    end
  end

  # @param effective_xlen [Integer or nil] 32 or 64 for fixed xlen, nil for dynamic
  # @return [Array<CsrField>] All implemented fields at the given effective XLEN
  def possible_fields_for(effective_xlen)
    raise ArgumentError, "effective_xlen is non-nil and is a #{effective_xlen.class} but must be an Integer" unless effective_xlen.nil? || effective_xlen.is_a?(Integer)

    @possible_fields_for ||= {}
    @possible_fields_for[effective_xlen] ||=
      possible_fields.select do |f|
        f.base.nil? || f.base == effective_xlen
      end
  end

  # @return [Boolean] Whether or not the register can be written by software
  def writable
    @data["writable"]
  end

  # @param cfg_arch [ConfiguredArchitecture] Architecture definition
  # @param effective_xlen [Integer,nil] Effective XLEN to use
  # @param exclude_unimplemented [Boolean] If true, do not include unimplemented fields
  # @param optional_type [Integer] Wavedrom type (fill color) for optional fields
  # @return [Hash] A representation of the WaveDrom drawing for the register
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
        # reserved space
        n = field.location(effective_xlen).min - last_idx - 1
        raise "negative reserved space? #{n} #{name} #{field.location(effective_xlen).min} #{last_idx + 1}" if n <= 0

        desc["reg"] << { "bits" => n, type: 1 }
      end
      if cfg_arch.partially_configured? && field.optional_in_cfg?(cfg_arch)
        desc["reg"] << { "bits" => field.location(effective_xlen).size, "name" => field.name, type: optional_type }
      else
        desc["reg"] << { "bits" => field.location(effective_xlen).size, "name" => field.name, type: 3 }
      end
      last_idx = field.location(effective_xlen).max
    end
    if !field_list.empty? && (field_list.last.location(effective_xlen).max != (length(effective_xlen) - 1))
      desc["reg"] << { "bits" => (length(effective_xlen) - 1 - last_idx), type: 1 }
    end
    desc["config"] = { "bits" => length(effective_xlen) }
    desc["config"]["lanes"] = length(effective_xlen) / 16
    desc
  end

  # @param cfg_arch [ConfiguredArchitecture] Architecture def
  # @return [Boolean] whether or not the register is optional in the config
  def optional_in_cfg?(cfg_arch)
    unless cfg_arch.is_a?(ConfiguredArchitecture)
      raise ArgumentError, "cfg_arch is a class #{cfg_arch.class} but must be a ConfiguredArchitecture"
    end
    raise "optional_in_cfg? should only be used by a partially-specified arch def" unless cfg_arch.partially_configured?

    @optional_in_cfg_cache ||= {}.compare_by_identity

    return @optional_in_cfg_cache[cfg_arch] if @optional_in_cfg_cache.key?(cfg_arch)

    @optional_in_cfg_cache[cfg_arch] =
      exists_in_cfg?(cfg_arch) &&
      (defined_by_condition.satisfied_by_cfg_arch?(cfg_arch) == SatisfiedResult::Maybe)
  end

  # @return [Boolean] Whether or not the presence of ext_ver affects this register definition
  def affected_by?(ext_ver)
    defined_by_condition.satisfiability_depends_on_ext_req?(ext_ver.to_ext_req) || \
      fields.any? { |field| field.affected_by?(ext_ver) }
  end
end

end
