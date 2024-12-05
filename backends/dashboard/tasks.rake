# frozen_string_literal: true

require "pathname"

namespace :gen do
  desc "Generate status dashboard"
  task dash: ["#{$root}/.stamps/arch-gen-_64.stamp"] do
    template_path = Pathname.new("#{$root}/backends/dashboard/templates/index.html.erb")
    erb = ERB.new template_path.read, trim_mode: "-"
    erb.filename = template_path.to_s

    arch_def = arch_def_for("_64")

    result_path = Pathname.new("#{$root}/gen/dashboard/index.html")
    FileUtils.mkdir_p result_path.dirname
    File.write result_path, erb.result(binding)
  end
end
