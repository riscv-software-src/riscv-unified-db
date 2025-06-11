# frozen_string_literal: true

ruby "3.2.3"

# local gems in UDB
gem "idlc", path: "tools/gems/idlc"
gem "idl_highlighter", path: "tools/gems/idl_highlighter"
gem "udb_helpers", path: "tools/gems/udb_helpers"
gem "udb", path: "tools/gems/udb"

source "https://rubygems.org"

# gem "activesupport"
gem "asciidoctor-diagram", "~> 2.2"
gem "asciidoctor-pdf"
gem "base64"
gem "bigdecimal"
gem "concurrent-ruby", require: "concurrent"
gem "concurrent-ruby-ext"
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
  gem "awesome_print"
  gem "debug"
  gem "rdbg"
  gem "rubocop-minitest"
  gem "rubocop-sorbet"
  gem "ruby-prof"
  gem "ruby-prof-flamegraph", git: "https://github.com/oozou/ruby-prof-flamegraph.git", ref: "fc3c437", require: false
  gem "solargraph"
  gem "sorbet"
  gem "spoom"
  gem "tapioca", require: false
end

group :development, :test do
  gem "minitest"
  gem "simplecov"
end
