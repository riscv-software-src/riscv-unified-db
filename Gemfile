# frozen_string_literal: true

ruby "~> 3.2"

# local gems in UDB
gem "idlc", path: "tools/ruby-gems/idlc"
gem "idl_highlighter", path: "tools/ruby-gems/idl_highlighter"
gem "udb", path: "tools/ruby-gems/udb"
gem "udb_helpers", path: "tools/ruby-gems/udb_helpers"

source "https://rubygems.org"

# gem "activesupport"
gem "asciidoctor-diagram", "~> 2.2"
gem "asciidoctor-pdf"
gem "base64"
gem "bigdecimal"
gem "concurrent-ruby", require: "concurrent"
gem "concurrent-ruby-ext"
gem "json_schemer", "~> 1.0"
gem "rake", "~> 13.0"
gem "ruby-progressbar", "~> 1.13"
gem "sorbet-runtime"
gem "ttfunk", "1.7" # needed to avoid having asciidoctor-pdf dependencies pulling in a buggy version of ttunk (1.8)
gem "webrick"
gem "write_xlsx"
gem "yard"

group :development do
  gem "awesome_print"
  gem "debug"
  gem "rdbg"
  gem "rubocop-github"
  gem "rubocop-minitest"
  gem "rubocop-performance"
  gem "rubocop-sorbet"
  gem "ruby-prof"
  gem "solargraph"
  gem "sorbet"
  gem "spoom"
  gem "tapioca", require: false
end

group :development, :test do
  gem "minitest"
  gem "simplecov"
  gem "simplecov-cobertura"
end
