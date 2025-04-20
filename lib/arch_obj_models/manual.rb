# frozen_string_literal: true

require "asciidoctor"

require_relative "database_obj"

class Manual < DatabaseObject
  def versions
    return @versions unless @versions.nil?

    @versions = @arch.manual_versions.select { |mv| mv.manual == self }
  end

  def version(name)
    versions.find { |v| v.name == name }
  end

  # @return [String] The title of the manual, as used by marketing
  def marketing_name = @data["marketing_name"]

  # for manuals that reference an external repo, set the url to that repo data (file path)
  def repo_path=(path)
    @repo_path = Pathname.new(path)
    versions.each { |v| v.repo_path = @repo_path }
  end
end

class ManualChapter
  def initialize(volume, path)
    @volume = volume
    @version = volume.version

    @path = Pathname.new path
  end

  def name
    @path.basename(".adoc").to_s
  end

  def title
    return @title unless @title.nil?

    @title = (Asciidoctor.load File.read(fullpath).scrub).doctitle.encode("US-ASCII")
  end

  def fullpath
    raise "Must call repo_path= first" if @repo_path.nil?

    @repo_path / @path
  end

  def repo_path=(path)
    @repo_path = path
  end

  # @return [Pathname] The relative path to the chapter
  attr_reader :path
end

class ManualVolume
  # @return [ManualVersion] The version this volume belongs to
  attr_reader :version

  def cfg_arch = version.cfg_arch

  def initialize(data, version)
    @data = data
    @version = version
  end

  def chapters
    return @chapters unless @chapters.nil?

    @chapters = []
    return @chapters if @data["chapters"].nil?

    @data["chapters"].each do |chapter_path|
      @chapters << ManualChapter.new(self, chapter_path)
    end

    @chapters
  end

  def chapter(name) = chapters.find { |c| c.name == name }

  def title = @data["title"]

  # @return [Array<ExtensionVersion>] Array of extension versions in this volume
  def extensions
    return @extensions unless @extensions.nil?

    @extensions = []
    return @extensions if @data["extensions"].nil?

    @data["extensions"].each do |ext_hsh|
      ext_obj = cfg_arch.extension(ext_hsh["name"])
      if ext_obj.nil?
        warn "Extension '#{ext_hsh['name']}' is not in the database"
        next
      end

      ext_ver = ExtensionVersion.new(ext_hsh["name"], ext_hsh["version"], cfg_arch)
      unless ext_obj.versions.any? { |known_ver| known_ver == ext_ver }
        warn "Extension '#{ext_hsh['name']}', version '#{ext_hsh['version']}' is not defined in the database"
        next
      end

      @extensions << ext_ver
    end
    @extensions
  end

  def repo_path=(path)
    @repo_path = path
    chapters.each { |c| c.repo_path = path }
  end
end

class ManualVersion < DatabaseObject
  # @return [Manual] The manual this version belongs to
  def manual
    return @manual unless @manual.nil?

    @manual = @arch.ref(@data["manual"]["$ref"])
    raise "Error: manual #{@data['manual']['$ref']} is not found" if @manual.nil?

    @manual
  end

  # @return [String] Semantic version number
  def version = @data["version"]

  # @return [String] Version name used by marketing
  def marketing_version = @data["marketing_version"]

  # @return [String] Path to the directory containing contents.yaml file for this version
  def path
    File.dirname(@data["$source"])
  end

  # @return [Boolean] Whether or not this version is using riscv-isa-manual as a source
  def uses_isa_manual? = @data["uses_isa_manual"] == true

  # @return [String] The git tree-ish of riscv-isa-manual used by this version
  def isa_manual_tree = @data["isa_manual_tree"]

  # @return [Array<ManualVolume>] All volumes defined in this manual version
  def volumes
    return @volumes unless @volumes.nil?

    @volumes = []
    @data["volumes"].each do |volume|
      @volumes << ManualVolume.new(volume, self)
    end

    @volumes
  end

  def state = @data["state"]

  # @return [Array<ExtensionVersion>] Array of extension versions in this manual version
  def extensions
    return @extensions unless @extensions.nil?

    @extensions = volumes.map(&:extensions).flatten.uniq
  end

  # @return [Array<Instruction>] All instructions defined in this version
  def instructions
    return @instructions unless @instructions.nil?

    @instructions = []
    extensions.each do |ext|
      ext_obj = @cfg_arch.extension(ext.name)
      ext_obj.instructions.each do |inst|
        @instructions << inst
      end
    end
    @instructions = @instructions.uniq(&:name)
  end

  # @return [Array<Csr>] All csrs defined in this version
  def csrs
    return @csrs unless @csrs.nil?

    @csrs = []
    extensions.each do |ext|
      ext_obj = @cfg_arch.extension(ext.name)
      ext_obj.csrs.each do |csr|
        @csrs << csr
      end
    end
    @csrs = @csrs.uniq(&:name)
  end

  def repo_path=(path)
    @repo_path = path
    volumes.each { |v| v.repo_path = path }
  end
end
