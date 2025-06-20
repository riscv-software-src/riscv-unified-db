# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "sorbet-runtime"

module Udb

# Represents an RVI version specifier
#
# Version specs have the form:
#   MAJOR[.MINOR[.PATCH[-pre]]]
# Where MAJOR, MINOR, and PATCH are integers and "pre" is an optional string
#
# Notably, these DO NOT represent a Semantic Version (https://semver.og).
#
# Rather, versions are treated as follows:
#
#  * Versions are assumed to be backward compatible by default.
#     For example,
#        - 2.0 is compatible with 1.0
#        - 1.1 is compatible with 1.0
#        - 0.9 is *not* compatible with 1.0
#  * A version can be explicitly marked as "breaking" in the architecture definition
#      Breaking versions are not backward compatible with any smaller versions
#      For example, if version 2.2 is Breaking,
#        - 3.0 is compatible with 2.2
#        - 2.3 is compatible with 2.2
#        - 3.0 is *not* compatible with 2.0
#        - 2.2 is *not* compatible with 2.0
#        - 2.1 is compatible with 2.0
#
class VersionSpec
  extend T::Sig

  include Comparable

  # MAJOR[.MINOR[.PATCH[-pre]]]
  VERSION_REGEX = /([0-9]+)(?:\.([0-9]+)(?:\.([0-9]+)(?:-(pre))?)?)?/

  # @return [Integer] Major version number
  attr_reader :major

  # @return [Integer] Minor version number
  attr_reader :minor

  # @return [Integer] Patch version number
  attr_reader :patch

  # @return [Boolean] Whether or not this is a pre-release
  attr_reader :pre

  sig { params(version_str: String).void }
  def initialize(version_str)
    if version_str =~ /^\s*#{VERSION_REGEX}\s*$/
      m = T.must(::Regexp.last_match)
      @major = m[1].to_i
      @minor_given = !m[2].nil?
      @minor = @minor_given ? m[2].to_i : 0
      @patch_given = !m[3].nil?
      @patch = @patch_given ? m[3].to_i : 0
      @pre = !m[4].nil?
    else
      raise ArgumentError, "#{version_str} is not a valid Version spec"
    end
    @version_str = version_str
  end

  sig { returns(String) }
  def inspect
    "VersionSpec[str: #{@version_str}; major: #{@major}, minor: #{@minor}, patch: #{@patch}, pre: #{@pre}]"
  end

  # @return [String] The version, in canonical form
  sig { returns(String) }
  def canonical
    "#{@major}.#{@minor}.#{@patch}#{@pre ? '-pre' : ''}"
  end

  # @return [String] The version formatted like RVI docs
  #
  # @example
  #   VersionSpec.new("2.2").to_rvi_s #=> "2p2"
  sig { returns(String) }
  def to_rvi_s
    s = @major.to_s
    s += "p#{@minor}" if @minor_given
    s += "p#{@patch}" if @patch_given
    s += "-pre" if @pre
    s
  end

  # @return [String] The exact string used during construction
  sig { returns(String) }
  def to_s = @version_str

  sig { params(other: T.any(String, VersionSpec)).returns(T.nilable(Integer)) }
  def <=>(other)
    if other.is_a?(String)
      VersionSpec.new(other) <=> self
    elsif other.is_a?(VersionSpec)
      if @major != other.major
        @major <=> other.major
      elsif @minor != other.minor
        @minor <=> other.minor
      elsif @patch != other.patch
        @patch <=> other.patch
      elsif @pre != other.pre
        @pre ? 1 : -1
      else
        0
      end
    else
      T.absurd(other)
    end
  end

  # @param other [VersionSpec] Comparison
  # @return [Boolean] Whether or not +other+ is an VersionSpec with the same canonical version
  sig { params(other: T.any(String, VersionSpec)).returns(T::Boolean) }
  def eql?(other)
    if other.is_a?(String)
      eql?(VersionSpec.new(other))
    elsif other.is_a?(VersionSpec)
      other.major == @major && \
        other.minor == @minor && \
        other.patch == @patch && \
        other.pre == @pre
    else
      T.absurd(other)
    end
  end
end

# Represents a version requirement
#
# A requirement is either a logical comparison (>, >=, <, <=, =, !=)
# or a compatible operator (~>).
#
# @example Logical requirement
#   # When the requirement is a logical comparison, the extension parameter is not needed
#   RequirementSpec.new(">= 0.5").satisfied_by?(VersionSpec.new("1.0"), nil) #=> true
#   RequirementSpec.new(">= 0.5").satisfied_by?(VersionSpec.new("0.4"), nil) #=> false
#
# @example Compatible requirement
#   s_ext = Extension.new(...) # S extension, which is breaking between 1.11 -> 1.12
#   RequirementSpec.new("~> 1.11").satisfied_by?(VersionSpec.new("1.10"), s_ext) #=> true
#   RequirementSpec.new("~> 1.11").satisfied_by?(VersionSpec.new("1.11"), s_ext) #=> true
#   RequirementSpec.new("~> 1.11").satisfied_by?(VersionSpec.new("1.12"), s_ext) #=> false
class RequirementSpec
  extend T::Sig
  REQUIREMENT_OP_REGEX = /((?:>=)|(?:>)|(?:~>)|(?:<)|(?:<=)|(?:!=)|(?:=))/
  REQUIREMENT_REGEX = /#{REQUIREMENT_OP_REGEX}\s*(#{VersionSpec::VERSION_REGEX})/

  # @param requirement [String] A requirement string
  sig { params(requirement: String).void }
  def initialize(requirement)
    if requirement =~ /^\s*#{REQUIREMENT_REGEX}\s*$/
      m = T.must(::Regexp.last_match)
      @op = T.must(m[1])
      @version_str = T.must(m[2])
      @version_spec = VersionSpec.new(@version_str)
    else
      raise ArgumentError, "Bad requirement string '#{requirement}' #{REQUIREMENT_REGEX}"
    end
  end

  sig { returns(String) }
  def to_s
    "#{@op} #{@version_str}"
  end

  # invert the requirement
  sig { void }
  def invert!
    case @op
    when ">="
      @op = "<"
    when ">"
      @op = "<="
    when "<="
      @op = ">"
    when "<"
      @op = ">="
    when "="
      @op = "!="
    when "!="
      @op = "="
    when "~>"
      @op = "!~>"
    end
    self
  end

  # @param version [String] A version string
  # @param version [VersionSpec] A version spec
  # @param ext [Extension] An extension, needed to evaluate the compatible (~>) operator
  # @param ext [Hash] Raw extension spec (from YAML)
  # @return [Boolean] if the version satisfies the requirement
  sig { params(version: T.any(String, VersionSpec), ext: T.any(Extension, T::Hash[String, T.untyped])).returns(T::Boolean) }
  def satisfied_by?(version, ext)
    v_spec =
      case version
      when String
        VersionSpec.new(version)
      when VersionSpec
        version
      else
        T.absurd(version)
      end

    case @op
    when ">="
      v_spec >= @version_spec
    when ">"
      v_spec > @version_spec
    when "<="
      v_spec <= @version_spec
    when "<"
      v_spec < @version_spec
    when "="
      v_spec == @version_spec
    when "!="
      v_spec != @version_spec
    when "~>"
      if ext.is_a?(Extension)
        matching_ver = ext.versions.find { |v| v.version_spec == v_spec }
        raise "Can't find version?" if matching_ver.nil?

        matching_ver.compatible?(ExtensionVersion.new(ext.name, v_spec.to_s, ext.arch))
      else
        versions = ext.fetch("versions")
        compatible_versions = []
        versions.each do |vinfo|
          vspec = VersionSpec.new(vinfo.fetch("version"))
          compatible_versions << vspec if vspec >= v_spec
          break if compatible_versions.size.positive? && vinfo.key?("breaking")
        end

        compatible_versions.include?(v_spec)
      end
    when "!~>" # not a legal spec, but used for inversion
      if ext.is_a?(Extension)
        matching_ver = ext.versions.find { |v| v.version_spec == v_spec }
        raise "Can't find version?" if matching_ver.nil?

        !matching_ver.compatible?(ExtensionVersion.new(ext.name, v_spec.to_s, ext.arch))
      else
        versions = ext.fetch("versions")
        compatible_versions = []
        versions.each do |vinfo|
          vspec = VersionSpec.new(vinfo.fetch("version"))
          compatible_versions << vspec if vspec >= v_spec
          break if compatible_versions.size.positive? && vinfo.key?("breaking")
        end

        !compatible_versions.include?(v_spec)
      end
    end
  end
end

end
