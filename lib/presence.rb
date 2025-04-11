# frozen_string_literal: true

require_relative "version"

# Is the extension mandatory, optional, various kinds of optional, etc.
# Accepts two kinds of YAML schemas:
#   String
#     Example => presence: mandatory
#   Hash
#     Must have the key "optional" with a String value
#     Example => presence:
#                  optional: development
class Presence
  attr_reader :presence
  attr_reader :optional_type

  # @param data [Hash, String] The presence data from the architecture spec
  def initialize(data)
    if data.is_a?(String)
      raise "Unknown extension presence of #{data}" unless ["mandatory","optional"].include?(data)

      @presence = data
      @optional_type = nil
    elsif data.is_a?(Hash)
      data.each do |key, value|
        if key == "optional"
          raise ArgumentError, "Extension presence hash #{data} missing type of optional" if value.nil?
          raise ArgumentError, "Unknown extension presence optional #{value} for type of optional" unless
            ["localized", "development", "expansion", "transitory"].include?(value)

          @presence = key
          @optional_type = value
        else
          raise ArgumentError, "Extension presence hash #{data} has unsupported key of #{key}"
        end
      end
    else
      raise ArgumentError, "Extension presence is a #{data.class} but only String or Hash are supported"
    end
  end

  def mandatory? = (@presence == "mandatory")
  def optional? = (@presence == "optional")

  # Class methods
  def self.mandatory = "mandatory"
  def self.optional = "optional"
  def self.optional_type_localized = "localized"
  def self.optional_type_development = "development"
  def self.optional_type_expansion = "expansion"
  def self.optional_type_transitory = "transitory"

  def self.presence_types = [mandatory, optional]
  def self.optional_types = [
        optional_type_localized,
        optional_type_development,
        optional_type_expansion,
        optional_type_transitory]

  def self.presence_types_obj
    return @presence_types_obj unless @presence_types_obj.nil?

    @presence_types_obj = []

    presence_types.each do |presence_type|
      @presence_types_obj << Presence.new(presence_type)
    end

    @presence_types_obj
  end

  def self.optional_types_obj
    return @optional_types_obj unless @optional_types_obj.nil?

    @optional_types_obj = []

    optional_types.each do |optional_type|
      @optional_types_obj << Presence.new({ self.optional => optional_type })
    end

    @optional_types_obj
  end

  def to_s
    @optional_type.nil? ? "#{presence}" : "#{presence} (#{optional_type})"
  end

  def to_s_concise
    "#{presence}"
  end

  # @overload ==(other)
  #   @param other [String] A presence string
  #   @return [Boolean] whether or not this Presence has the same presence (ignores optional_type)
  # @overload ==(other)
  #   @param other [Presence] An extension presence object
  #   @return [Boolean] whether or not this Presence has the exact same presence and optional_type as other
  #                     Ignores optional_type if either self or other have it as nil.
  def ==(other)
    case other
    when String
      @presence == other
    when Presence
      @presence == other.presence && (@optional_type.nil? || other.optional_type.nil? || @optional_type == other.optional_type)
    else
      raise "Unexpected comparison"
    end
  end

  ######################################################
  # Following comparison operators follow these rules:
  #   - "mandatory" is greater than "optional"
  #   - optional_types all have same rank
  #   - equals compares presence and then optional_type
  ######################################################

  # @overload >(other)
  #   @param other [Presence] An extension presence object
  #   @return [Boolean] Whether or not this Presence is greater-than the other
  def >(other)
    raise ArgumentError, "Presence is only comparable to other Presence classes" unless other.is_a?(Presence)
    (self.mandatory? && other.optional?)
  end

  # @overload >=(other)
  #   @param other [Presence] An extension presence object
  #   @return [Boolean] Whether or not this Presence is greater-than or equal to the other
  def >=(other)
    raise ArgumentError, "Presence is only comparable to other Presence classes" unless other.is_a?(Presence)
    (self > other) || (self == other)
  end

  # @overload <(other)
  #   @param other [Presence] An extension presence object
  #   @return [Boolean] Whether or not this Presence is less-than the other
  def <(other)
    raise ArgumentError, "Presence is only comparable to other Presence classes" unless other.is_a?(Presence)
    (self.optional? && other.mandatory?)
  end

  # @overload <=(other)
  #   @param other [Presence] An extension presence object
  #   @return [Boolean] Whether or not this Presence is less-than or equal to the other
  def <=(other)
    raise ArgumentError, "Presence is only comparable to other Presence classes" unless other.is_a?(Presence)
    (self < other) || (self == other)
  end
end
