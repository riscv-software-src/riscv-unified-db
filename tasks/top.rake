# frozen_string_literal: true

$root = Pathname.new(__FILE__).dirname.dirname.realpath
$lib = $root / "lib"

require "yard"

require_relative $root / "lib" / "validate"

directory "#{$root}/.stamps"

load "#{$root}/tasks/arch_gen.rake"
load "#{$root}/tasks/adoc_gen.rake"
load "#{$root}/tasks/html_gen.rake"

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
      sh "bundle exec yard doc"
    end
  end
end

namespace :serve do
  desc <<~DESC
    Start an HTML server to view the generated HTML documentation for the tool

    The default port is 8000, though it can be overridden with an argument
  DESC
  task :ruby_doc, [:port] => "gen:tool_doc" do |_t, args|
    args.with_defaults(port: 8000)

    puts <<~MSG
      Server will come up on http://#{`hostname`.strip}:#{args[:port]}.
      It will regenerate the documentation on every access

    MSG
    sh "yard server -p #{args[:port]} --reload"
  end
end
