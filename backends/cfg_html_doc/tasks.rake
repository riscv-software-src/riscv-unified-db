# frozen_string_literal: true

require_relative "#{$lib}/arch_def"

CFG_HTML_DOC_DIR = Pathname.new(__FILE__).dirname

load "#{CFG_HTML_DOC_DIR}/adoc_gen.rake"
load "#{CFG_HTML_DOC_DIR}/html_gen.rake"
