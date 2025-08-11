# frozen_string_literal: true

ruby "~> 3.2"

# local gems in UDB
gem "idlc", path: "tools/ruby-gems/idlc"
gem "idl_highlighter", path: "tools/ruby-gems/idl_highlighter"
gem "udb", path: "tools/ruby-gems/udb", require: false
gem "udb_helpers", path: "tools/ruby-gems/udb_helpers"

source "https://rubygems.org"

# gem "activesupport"
gem "asciidoctor-diagram", "~> 2.2"
gem "asciidoctor-pdf"
gem "base64"
gem "bigdecimal"
# gem "concurrent-ruby", require: "concurrent"
# gem "concurrent-ruby-ext"
gem "json_schemer", "~> 1.0"
# gem "pygments.rb"
gem "rake", "~> 13.0"
#gem "rouge"
gem "ruby-progressbar", "~> 1.13"
gem "sorbet-runtime"
#gem "treetop", "1.6.12"
gem "ttfunk", "1.7" # needed to avoid having asciidoctor-pdf dependencies pulling in a buggy version of ttunk (1.8)
gem "webrick"
gem "write_xlsx"
gem "yard"

group :development do
  gem "awesome_print", require: false
  gem "bumbler", require: false
  gem "debug", require: false
  gem "rdbg", require: false
  gem "rubocop-github", require: false
  gem "rubocop-minitest", require: false
  gem "rubocop-performance", require: false
  gem "rubocop-sorbet", require: false
  gem "ruby-prof", require: false
  gem "solargraph", require: false
  gem "sorbet", require: false
  gem "spoom", require: false
  gem "tapioca", require: false
end

group :development, :test do
  gem "minitest", require: false
  gem "simplecov", require: false
  gem "simplecov-cobertura", require: false
end
