# frozen_string_literal: true

class CertNormativeRule
  # @param data [Hash<String, Object>] Data from YAML file
  # @param db_obj [DatabaseObject] Database object that defines normative rule (Extension, Instruction, CSR, or CSR field)
  def initialize(data, db_obj)
    raise ArgumentError, "Need Hash but was passed a #{data.class}" unless data.is_a?(Hash)
    raise ArgumentError, "Need DatabaseObject but was passed a #{db_obj.class}" unless db_obj.is_a?(DatabaseObject)

    @data = data
    @db_obj = db_obj

    raise ArgumentError, "Missing certification normative rule description for #{db_obj.name} of kind #{db_obj.kind}" if description.nil?
    raise ArgumentError, "Missing certification normative rule ID for #{db_obj.name} of kind #{db_obj.kind}" if id.nil?
  end

  # @return [String] Description of normative rule (could be multiple lines)
  def description = @data["description"]

  # @return [String] Unique ID of the normative rule
  def id = @data["id"]

  # @return [Array<DocLink>] List of certification point documentation links
  def doc_links
    return @doc_links unless @doc_links.nil?

    @doc_links = []
    @data["doc_links"]&.each do |dst|
      @doc_links << DocLink.new(dst, @db_obj)
    end

    raise "Missing doc_links for certification normative rule ID '#{id}' of kind #{@db_obj.kind}" if @doc_links.empty?

    @doc_links
  end
end
