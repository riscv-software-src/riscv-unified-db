# frozen_string_literal: true

# represents an RVI version specifier
class VersionSpec
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

  def initialize(version_str)
    if version_str =~ /^\s*#{VERSION_REGEX}\s*$/
      m = ::Regexp.last_match
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

  def inspect
    "VersionSpec[str: #{@version_str}; major: #{@major}, minor: #{@minor}, patch: #{@patch}, pre: #{@pre}]"
  end

  # @return [String] The version, in canonical form
  def canonical
    "#{@major}.#{@minor}.#{@patch}#{@pre ? '-pre' : ''}"
  end

  # @return [String] The version formatted like RVI docs
  #
  # @example
  #   VersionSpec.new("2.2").to_rvi_s #=> "2p2"
  def to_rvi_s
    s = @major.to_s
    s += "p#{@minor}" if @minor_given
    s += "p#{@patch}" if @patch_given
    s += "-pre" if @pre
    s
  end

  # @return [String] The exact string used during construction
  def to_s = @version_str

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
      raise ArgumentError, "Cannot compare VersionSpec with #{other.class.name}"
    end
  end

  # @param other [VersionSpec] Comparison
  # @return [Boolean] Whether or not +other+ is an VersionSpec with the same canonical version
  def eql?(other)
    if other.is_a?(String)
      eql?(ExtensionVersion.new(other))
    elsif other.is_a?(VersionSpec)
      other.major == @major && \
        other.minor == @minor && \
        other.patch == @patch && \
        other.pre == @pre
    else
      raise ArgumentError, "Cannot compare VersionSpec with #{other.class.name}"
    end
  end
end

# A requirement
class RequirementSpec
  REQUIREMENT_OP_REGEX = /((?:>=)|(?:>)|(?:~>)|(?:<)|(?:<=)|(?:!=)|(?:=))/
  REQUIREMENT_REGEX = /#{REQUIREMENT_OP_REGEX}\s*(#{VersionSpec::VERSION_REGEX})/

  # @param requirement [String] A requirement string
  def initialize(requirement)
    unless requirement.is_a?(String)
      raise ArgumentError, "requirement must be a string (is a #{requirement.class.name})"
    end

    if requirement =~ /^\s*#{REQUIREMENT_REGEX}\s*$/
      m = ::Regexp.last_match
      @op = m[1]
      @version_str = m[2]
      @version_spec = VersionSpec.new(@version_str)
    else
      raise ArgumentError, "Bad requirement string '#{requirement}'"
    end
  end

  def to_s
    "#{@op} #{@version_str}"
  end

  # @param version [String] A version string
  # @param version [VersionSpec] A version spec
  # @param ext [Extension] An extension, needed to evaluate the compatible (~>) operator
  # @return [Boolean] if the version satisfies the requirement
  def satisfied_by?(version, ext)
    v_spec =
      case version
      when String
        VersionSpec.new(version)
      when VersionSpec
        version
      else
        raise ArgumentError, "satisfied_by? expects a String or VersionSpec (got #{version.class.name})"
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
      matching_ver = ext.versions.find { |v| v.version_spec == v_spec }
      raise "Can't find version?" if matching_ver.nil?

      matching_ver.compatible?(ExtensionVersion.new(ext.name, v_spec.to_s, ext.arch_def))
    end
  end
end
