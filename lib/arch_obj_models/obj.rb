# frozen_string_literal: true

# base for any object representation of the Architecture Definition
# does two things:
#
#  1. Makes the raw data for the object accessible via []
#     For example, given:
#        data = {
#          'name' => 'mstatus',
#          'address' => 0x320,
#          ...
#        }
#
#     obj = ArchDefObject.new(data)
#     obj['name']    # 'mstatus'
#     obj['address'] # 0x320
#
#  2. Provides accessor methods for the data properties
#     Given the same example above, the following works:
#
#     obj.name       # 'mstatus'
#     obj.address    # 0x320
#
# Subclasses may override the accessors when a more complex data structure
# is warranted, e.g., the CSR Field 'alias' returns a CsrFieldAlias object
# instead of a simple string
class ArchDefObject
  attr_reader :data, :name, :long_name, :description

  # @return [String] Source file that data for this object can be attributed to
  # @return [nil] if the source isn't known
  def __source
    @data["__source"]
  end

  # The raw content of definedBy in the data.
  # @note Generally, you should prefer to use {#defined_by?}, etc. from Ruby
  #
  # @return [String] An extension name
  # @return [Array(String, Number)] An extension name and versions
  # @return [Array<*>] A list of extension names or extension names and versions
  def definedBy
    @data["definedBy"]
  end

  # @param data [Hash<String,Object>] Hash with fields to be added
  def initialize(data)
    raise "Bad data" unless data.is_a?(Hash)

    @data = data
    @name = data["name"]
    @long_name = data["long_name"]
    @description = data["description"]

  end

  def inspect
    self.class.name
  end

  # make the underlying YAML description available with []
  extend Forwardable
  def_delegator :@data, :[]

  # @return [Array<String>] List of keys added by this ArchDefObject
  def keys = @data.keys
  
  # @param k (see Hash#key?)
  # @return (see Hash#key?)
  def key?(k) = @data.key?(k)

  # adds accessor functions for any properties in the data
  # def method_missing(method_name, *args, &block)
  #   if @data.key?(method_name.to_s)
  #     raise "Unexpected argument to '#{method_name}" unless args.empty?

  #     raise "Unexpected block given to '#{method_name}" if block_given?

  #     @data[method_name.to_s]
  #   else
  #     super
  #   end
  # end

  # def respond_to_missing?(method_name, include_private = false)
  #   @data.key?(method_name.to_s) || super
  # end

  # @overload defined_by?(ext_name, ext_version)
  #   @param ext_name [#to_s] An extension name
  #   @param ext_version [#to_s] A specific extension version
  #   @return [Boolean] Whether or not the instruction is defined by extesion `ext`, version `version`
  # @overload defined_by?(ext_version)
  #   @param ext_version [ExtensionVersion] An extension version
  #   @return [Boolean] Whether or not the instruction is defined by ext_version
  def defined_by?(*args)
    if args.size == 1
      raise ArgumentError, "Parameter must be an ExtensionVersion" unless args[0].is_a?(ExtensionVersion)

      defined_by.any? do |r|
        r.satisfied_by?(args[0])
      end
    elsif args.size == 2
      raise ArgumentError, "First parameter must be an extension name" unless args[0].respond_to?(:to_s)
      raise ArgumentError, "Second parameter must be an extension version" unless args[0].respond_to?(:to_s)

      defined_by.any? do |r|
        r.satisfied_by?(args[0].to_s, args[1].to_s)
      end
    end
  end

  def to_extension_requirement(obj)
    if obj.is_a?(String)
      ExtensionRequirement.new(obj, ">= 0")
    else
      ExtensionRequirement.new(*obj)
    end
  end
  private :to_extension_requirement

  def to_extension_requirement_list(obj)
    list = []
    if obj.is_a?(Array)
      # could be either a single extension with exclusion, or a list of exclusions
      if extension_exclusion?(obj[0])
        list << to_extension_requirement(obj[0])
      else
        # this is a list
        obj.each do |r|
          list << to_extension_exclusion(r)
        end
      end
    else
      list << to_extension_requirement(obj)
    end
    list
  end

  def extension_requirement?(obj)
    obj.is_a?(String) && obj =~ /^([A-WY])|([SXZ][a-z]+)$/ ||
      obj.is_a?(Array) && obj[0] =~ /^([A-WY])|([SXZ][a-z]+)$/
  end
  private :extension_requirement?

  # @return [Array<ExtensionRequirement>] Extension(s) that define the instruction. If *any* requirement is met, the instruction is defined.
  def defined_by
    return @defined_by unless @defined_by.nil?

    @defined_by = []
    # definedBy can be:
    #
    #  * [String] Extension name
    #  * [Array] Extension name, version
    #  * [Array] Array of one of the two above
    if @data["definedBy"].is_a?(Array)
      if @data["definedBy"].size == 2
        if @data["definedBy"][1].is_a?(String) && @data["definedBy"][1] =~ /^<>=~$/
          @defined_by << to_extension_requirement(@data["definedBy"])
        elsif @data["definedBy"][1].is_a?(String)
          # this is an array of extension names
          @defined_by << to_extension_requirement(@data["definedBy"][0])
          @defined_by << to_extension_requirement(@data["definedBy"][1])
        else
          # this is a list of extension requirements
          @data["definedBy"].each do |r|
            @defined_by << to_extension_requirement(r)
          end
        end
      else
        # this is a list of extension requirements
        @data["definedBy"].each do |r|
          @defined_by << to_extension_requirement(r)
        end
      end
    else
      raise "unexpected" unless @data["definedBy"].is_a?(String)
      @defined_by << to_extension_requirement(@data["definedBy"])
    end

    raise "empty requirements" if @defined_by.empty?

    @defined_by
  end

  # @return [Integer] THe source line number of +path+ in the YAML file
  # @param path [Array<String>] Path to the scalar you want.
  # @example
  #   yaml = <<~YAML
  #     misa:
  #       sw_read(): ...
  #       fields:
  #         A:
  #           type(): ...
  #   YAML
  #   misa_csr.source_line("sw_read()")  #=> 2
  #   mis_csr.source_line("fields", "A", "type()") #=> 5
  def source_line(*path)

    # find the line number of this operation() in the *original* file
    yaml_filename = @data["__source"]
    raise "No __source for #{name}" if yaml_filename.nil?
    line = nil
    path_idx = 0
    Psych.parse_stream(File.read(yaml_filename), filename: yaml_filename) do |doc|
      mapping = doc.children[0]
      data = mapping.children[1]
      while path_idx < path.size
        idx = 0
        while idx < data.children.size
          if data.children[idx].value == path[path_idx]
            if path_idx == path.size - 1
              line = data.children[idx + 1].start_line
              if data.children[idx + 1].style == Psych::Nodes::Scalar::LITERAL
                line += 1 # the string actually begins on the next line
              end
              return line
            else
              data = data.children[idx + 1]
              path_idx += 1
              break
            end
          end
          idx += 2
        end
      end
    end
    raise "Didn't find key '#{path}' in #{@data['__source']}"
  end
end

# A company description
class Company < ArchDefObject
  # @return [String] Company name
  def name = @data["name"]

  # @return [String] Company website
  def url = @data["url"]
end

# License information
class License < ArchDefObject
  # @return [String] License name
  def name = @data["name"]

  # @return [String] License website
  # @return [nil] if there is no website for the license
  def url = @data["url"]

  # @return [String] Text of the license
  def text
    if !@data["text_url"].nil?
      Net::HTTP.get(URI(@data["text_url"]))
    else
      @data["text"]
    end
  end
end

# Personal information about a contributor
class Person < ArchDefObject
  # @return [String] Person's name
  def name = @data["name"]

  # @return [String] Email address
  # @return [nil] if email address is not known
  def email = @data["email"]

  # @return [String] Company the person works for
  # @return [nil] if the company is not known, or if the person is an individual contributor
  def company = @data["company"]

  def <=>(other)
    name <=> other.name
  end
end

# represents a JSON Schema compoisition, e.g.:
#
# anyOf:
#   - oneOf:
#     - A
#     - B
#   - C
#
class SchemaCondition
  # @param composition_hash [Hash] A possibly recursive hash of "allOf", "anyOf", "oneOf"
  def initialize(composition_hash)
    raise ArgumentError, "Expecting a JSON schema composition" unless is_a_condition?(composition_hash)

    @hsh = composition_hash
  end

  def is_a_condition?(hsh)
    return false unless hsh.is_a?(Hash) && hsh.keys.size == 1 && hsh[hsh.keys[0]].is_a?(Array)

    return false unless ["allOf", "anyOf", "oneOf"].include?(hsh.keys[0])

    hsh[hsh.keys[0]].each do |element|
      if element.is_a?(Hash)
        return false unless is_a_condition?(element)
      end
    end

    return true
  end
  private :is_a_condition?

  def to_rb_helper(hsh)
    if hsh.is_a?(Hash)
      key = hsh.keys[0]

      case key
      when "allOf"
        rb_str = hsh[key].map { |element| to_rb_helper(element) }.join(' && ')
        "(#{rb_str})"
      when "anyOf"
        rb_str = hsh[key].map { |element| to_rb_helper(element) }.join(' || ')
        "(#{rb_str})"
      when "oneOf"
        rb_str = hsh[key].map { |element| to_rb_helper(element) }.join(', ')
        "([#{rb_str}].count(true) == 1)"
      else
        "(yield #{hsh})"
      end
    else
      "(yield #{hsh})"
    end
  end

  # Given the name of a ruby array +ary_name+ containing the available objects to test,
  # return a string that can be eval'd to determine if the objects in +ary_name+
  # meet the Condition
  #
  # @param ary_name [String] Name of a ruby string in the eval binding
  # @return [Boolean] If the condition is met
  def to_rb
    to_rb_helper(@hsh)
  end

  # @example See if a string satisfies
  #   cond = { "anyOf" => ["A", "B", "C"] }
  #   string = "A"
  #   cond.satisfied_by? { |endpoint| endpoint == string } #=> true
  #   string = "D"
  #   cond.satisfied_by? { |endpoint| endpoint == string } #=> false
  #
  # @example See if an array satisfies
  #   cond = { "allOf" => ["A", "B", "C"] }
  #   ary = ["A", "B", "C", "D"]
  #   cond.satisfied_by? { |endpoint| ary.include?(endpoint) } #=> true
  #   ary = ["A", "B"]
  #   cond.satisfied_by? { |endpoint| ary.include?(endpoint) } #=> false
  #
  # @yieldparam obj [Object] An endpoint in the condition
  # @yieldreturn [Boolean] Whether or not +obj+ is what you are looking for
  # @return [Boolean] Whether or not the entire condition is satisfied
  def satisfied_by?(&block)
    raise ArgumentError, "Missing required block" unless block_given?

    raise ArgumentError, "Expecting one argument to block" unless block.arity == 1

    eval to_rb
  end
end

class AlwaysTrueSchemaCondition
  def to_rb = "true"
  
  def satisfied_by? = true
end
