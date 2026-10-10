# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "ffi"
require "fileutils"
require "net/http"
require "uri"
require "rbconfig"
require "tmpdir"
require "sorbet-runtime"
require "zip"

require_relative "log"
require_relative "dep_versions"

module FFI
  class DynamicLibrary
    class << self
      alias_method :orig_load_library, :load_library
    end
    def self.load_library(name, flags)
      names =
        if name.is_a?(::Array)
          name
        else
          [name]
        end
      names.map! do |name|
        if name =~ /z3/
          unless Pathname.new(name).absolute?
            # when we load z3, make sure we get our installed version
            File.join(Udb::Z3Loader.z3_lib_dir, Udb::Z3Loader.library_name)
          else
            name
          end
        else
          name
        end
      end
      orig_load_library(names, flags)
    end
  end
end

module Udb
  # Manages automatic download and installation of the Z3 library
  module Z3Loader
    extend T::Sig

    class Z3LoadError < StandardError; end

    class << self
      extend T::Sig

      # Main entry point - ensures Z3 is available before requiring the z3 gem
      sig { void }
      def ensure_z3_loaded
        require "z3"
      end

      sig { returns(String) }
      def z3_lib_dir
        cpu =
          case RbConfig::CONFIG["host_cpu"]
          when /arm64|aarch64/
            "arm64"
          when /x86_64|x64/
            "x64"
          else
            raise Z3LoadError, "Unsupported host cpu: #{RbConfig::CONFIG["host_cpu"]}"
          end
        xdg_cache = ENV.fetch("XDG_CACHE_HOME", File.join(Dir.home, ".cache"))
        File.join(xdg_cache, "udb", "z3", Udb::Z3_VERSION, cpu)
      end

      # Returns the platform-specific library name
      sig { returns(String) }
      def library_name
        case RbConfig::CONFIG["host_os"]
        when /darwin|mac os/
          "libz3.dylib"
        when /linux/
          "libz3.so"
        when /mswin|mingw|cygwin/
          "libz3.dll"
        else
          "libz3.so" # fallback
        end
      end

      private

    end
  end
end
