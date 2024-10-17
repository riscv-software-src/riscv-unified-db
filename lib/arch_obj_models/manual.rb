# frozen_string_literal: true

require "asciidoctor"

require_relative "obj"

class Manual < ArchDefObject
  def initialize(data, arch_def)
    super(data)
    @arch_def = arch_def
  end

  def versions
    return @versions unless @versions.nil?

    @versions = []
    @data["versions"].each do |version|
      @versions << ManualVersion.new(version, self, @arch_def)
    end

    @versions
  end

  def version(name)
    versions.find { |v| v.name == name }
  end

  # @return [String] The title of the manual, as used by marketing
  def marketing_name = @data["marketing_name"]
end

class ManualChapter
  def initialize(volume, path)
    @volume = volume
    @version = volume.version

    fullpath = "#{@version.path}/#{path}"
    raise "Path '#{fullpath}' does not exist" unless File.exist?(fullpath)

    @path = fullpath
  end

  def name
    File.basename(@path, ".adoc")
  end

  def title
    return @title unless @title.nil?

    @title = (Asciidoctor.load File.read(path).scrub).doctitle.encode("US-ASCII")
  end

  # @return [String] The absolute path to the chapter
  attr_reader :path
end

class ManualVolume
  # @return [ManualVersion] The version this volume belongs to
  attr_reader :version

  # @return [ArchDef] The architecture definition
  def arch_def = version.arch_def

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

    @data["extensions"].each do |ext|
      ext_obj = arch_def.extension(ext[0])
      if ext_obj.nil?
        warn "Extension '#{ext[0]}' is not in the database"
        next
      end

      unless ext_obj.versions.any? { |v| v["version"] == ext[1] }
        warn "Extension '#{ext[0]}', version '#{ext[1]}' is not defined in the database"
        next
      end

      @extensions << ExtensionVersion.new(ext[0], ext[1])
    end
    @extensions
  end
end

class ManualVersion < ArchDefObject
  # @return [Manual] The manual this version belongs to
  attr_reader :manual

  # @return [ArchDef] The architecture definition
  attr_reader :arch_def

  def initialize(data, manual, arch_def)
    super(data)
    @manual = manual
    @arch_def = arch_def
  end

  # @return [String] Semantic version number
  def version = @data["version"]

  # @return [String] Version name used by marketing
  def marketing_version = @data["marketing_version"]

  # @return [String] Path to the directory containing contents.yaml file for this version
  def path
    File.dirname(@data["__source"])
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
      ext_obj = @arch_def.extension(ext.name)
      ext_obj.instructions.each do |inst|
        @instructions << inst
      end
    end
    @instructions
  end

  # @return [Array<Csr>] All csrs defined in this version
  def csrs
    return @csrs unless @csrs.nil?

    @csrs = []
    extensions.each do |ext|
      ext_obj = @arch_def.extension(ext.name)
      ext_obj.csrs.each do |csr|
        @csrs << csr
      end
    end
    @csrs
  end
end
