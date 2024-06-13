# frozen_string_literal: true

$root = Pathname.new(__FILE__).dirname.dirname.realpath
$lib = $root / "lib"

require "yard"

require_relative $root / "lib" / "validate"

load "#{$root}/tasks/arch_gen.rake"

namespace :gen do
  task :html
end

desc "Validate the arch docs"
task :validate do
  validator = Validator.new
  Dir.glob("#{$root}/arch/**/*.yaml") do |f|
    validator.validate(f)
  end
end

directory "#{$root}/.stamps"

file "#{$root}/.stamps/dev_gems" => "#{$root}/.stamps" do
  Dir.chdir($root) do
    sh "bundle config set --local with development"
    sh "bundle install"
    FileUtils.touch "#{$root}/.stamps/dev_gems"
  end
end

namespace :gen do
  desc "Generate documentation for the generator tool"
  task tool_doc: "#{$root}/.stamps/dev_gems" do
    Dir.chdir($root) do
      sh "bundle exec yard doc -o docs/ruby 'lib/*.rb'"
    end
  end
end
