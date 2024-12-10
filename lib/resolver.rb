# given an architecture folder, resolves inheritance and expands some fields

require "pathname"

class Resolver
  def initialize(arch_folder)
    @dir = Pathname.new(arch_folder).realpath
  end

  def resolve_all(output_folder)
    Dir.glob(@dir / "**" / "*.yaml") do |f|
      resolve(f, "#{output_folder}/#{f.gsub("#{@dir.to_s}/", "")}")
    end
  end

  def resolve(input_file, output_file)
    obj = YamlLoader.load(input_file, permitted_classes: [Date])
    File.write(output_file, YAML::dump(obj))
  end
end
