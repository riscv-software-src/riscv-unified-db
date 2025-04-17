# frozen_string_literal: true

class CertTestProcedure
  # @param data [Hash<String, Object>] Data from YAML file
  # @param db_obj [DatabaseObject] Database object that defines test procedure (Extension, Instruction, CSR, or CSR field)
  def initialize(data, db_obj)
    raise ArgumentError, "Need Hash but was passed a #{data.class}" unless data.is_a?(Hash)
    raise ArgumentError, "Need DatabaseObject but was passed a #{db_obj.class}" unless db_obj.is_a?(DatabaseObject)

    @data = data
    @db_obj = db_obj

    raise ArgumentError, "Missing certification test procedure ID for #{db_obj.name} of kind #{db_obj.kind}" if id.nil?
    warn "Warning: Missing test_file_name for certification test procedure description for #{db_obj.name} of kind #{db_obj.kind}" if test_file_name.nil?
    raise ArgumentError, "Missing certification test procedure description for #{db_obj.name} of kind #{db_obj.kind}" if description.nil?
  end

  # @return [String] Unique ID of the test procedure
  def id = @data["id"]

  # @return [String] Name of test file that implements this test procedure. Could be nil.
  def test_file_name = @data["test_file_name"]

  # @return [String] Description of test procedure (could be multiple lines)
  def description = @data["description"]

  # @return [Array<CertNormativeRule>]
  def cert_normative_rules
    return @cert_normative_rules unless @cert_normative_rules.nil?

    @cert_normative_rules = []
    @data["normative_rules"]&.each do |id|
      cp = @db_obj.cert_coverage_point(id)
      raise ArgumentError, "Can't find certification test procedure with ID '#{id}' for '#{@db_obj.name}' of kind #{@db_obj.kind}" if cp.nil?
      @cert_normative_rules << cp
    end
    @cert_normative_rules
  end

  # @return [String] String (likely multiline) of certification test procedure steps using Asciidoc lists
  def cert_steps = @data["steps"]
end
