# frozen_string_literal: true

ruby "3.2.3"

source "https://rubygems.org"

gem "activesupport"
gem "asciidoctor-diagram", "~> 2.2"
gem "asciidoctor-pdf"
gem "base64"
gem "bigdecimal"
gem "concurrent-ruby", require: "concurrent"
gem "concurrent-ruby-ext"
gem "json_schemer", "~> 1.0"
gem "pygments.rb"
gem "rake", "~> 13.0"
gem "rouge"
gem "ruby-progressbar", "~> 1.13"
gem "treetop", "1.6.12"
gem "ttfunk", "1.7" # needed to avoid having asciidoctor-pdf dependencies pulling in a buggy version of ttunk (1.8)
gem "webrick"
gem "write_xlsx"
gem "yard"

group :development do
  gem "awesome_print"
  gem "debug"
  gem "minitest"
  gem "rdbg"
  gem "rubocop-minitest"
  gem "ruby-prof"
  gem "ruby-prof-flamegraph", git: "https://github.com/oozou/ruby-prof-flamegraph.git", ref: "fc3c437", require: false
  gem "solargraph"
end

group :test do
  gem 'simplecov', require: false
end
