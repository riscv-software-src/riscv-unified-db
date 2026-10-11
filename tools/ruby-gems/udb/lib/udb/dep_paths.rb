# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "digest"
require "rbconfig"
require "fileutils"
require "net/http"
require "uri"
require_relative "dep_versions"

module Udb
  # Shared HTTP download helper for binary dependencies (espresso, eqntott, must).
  module DepDownloader
    GITHUB_REPO = "riscv/riscv-unified-db"

    class << self
      def host_cpu
        case RbConfig::CONFIG["host_cpu"]
        when /arm64|aarch64/ then "arm64"
        when /x86_64|x64/    then "x64"
        else raise "Unsupported host cpu: #{RbConfig::CONFIG["host_cpu"]}"
        end
      end

      def bin_dir(name, version)
        xdg_cache = ENV.fetch("XDG_CACHE_HOME", File.join(Dir.home, ".cache"))
        File.join(xdg_cache, "udb", name, version, host_cpu)
      end

      def binary(name, version)
        path = File.join(bin_dir(name, version), name)
        unless File.exist?(path)
          begin
            download_binary(name, version, path)
          rescue => e
            raise "#{name} binary not found at #{path} and download failed: #{e.message}"
          end
        end
        path
      end

      private

      def download_binary(name, version, dest_file)
        cpu = host_cpu
        FileUtils.mkdir_p(File.dirname(dest_file))

        asset_name = "#{name}-#{cpu}"
        url_str = "https://github.com/#{GITHUB_REPO}/releases/download/#{version}/#{asset_name}"

        $stderr.puts "Downloading #{name} (#{version}, #{cpu}) from GitHub releases..."
        $stderr.puts "  URL: #{url_str}"

        body = download_with_redirects(url_str)

        # Verify against the published .checksum asset before the file is made
        # executable. extconf.rb publishes and checks these for the same
        # artifacts; this path previously skipped verification entirely.
        checksum_url_str = "#{url_str}.checksum"
        $stderr.puts "  Verifying checksum..."
        expected = download_with_redirects(checksum_url_str).strip.split(":")[1]
        actual = Digest::SHA256.hexdigest(body)

        raise "Could not parse checksum for #{name} from #{checksum_url_str}" if expected.nil? || expected.empty?

        unless expected == actual
          raise "Checksum verification failed for #{name}!\n" \
                "  Expected: #{expected}\n" \
                "  Got:      #{actual}\n" \
                "  The downloaded file may be corrupted or tampered with."
        end

        File.binwrite(dest_file, body)
        File.chmod(0o755, dest_file)
        $stderr.puts "  Saved to #{dest_file}"
      end

      def download_with_redirects(url_str, limit = 10)
        raise "Too many HTTP redirects" if limit.zero?

        uri = URI.parse(url_str)
        raise "Refusing to download over a non-HTTPS URL: #{url_str}" unless uri.scheme == "https"

        http = Net::HTTP.new(uri.host, uri.port)
        http.use_ssl = true
        http.open_timeout = 30
        http.read_timeout = 120

        request = Net::HTTP::Get.new(T.cast(uri, T.any(URI::HTTP, URI::HTTPS)).request_uri)
        request["User-Agent"] = "udb-gem/installer"

        response = http.request(request)

        case response
        when Net::HTTPSuccess
          response.body
        when Net::HTTPRedirection
          download_with_redirects(response["location"], limit - 1)
        else
          raise "Failed to download #{url_str}\n" \
                "HTTP #{response.code} #{response.message}"
        end
      end
    end
  end

  # Returns the path to the managed espresso binary downloaded at gem install time.
  module EspressoPath
    def self.binary  = DepDownloader.binary("espresso", ESPRESSO_VERSION)

    def self.bin_dir = DepDownloader.bin_dir("espresso", ESPRESSO_VERSION)
  end

  # Returns the path to the managed eqntott binary downloaded at gem install time.
  module EqntottPath
    def self.binary  = DepDownloader.binary("eqntott", EQNTOTT_VERSION)

    def self.bin_dir = DepDownloader.bin_dir("eqntott", EQNTOTT_VERSION)
  end

  # Returns the path to the managed must binary downloaded at gem install time.
  module MustPath
    def self.binary  = DepDownloader.binary("must", MUST_VERSION)

    def self.bin_dir = DepDownloader.bin_dir("must", MUST_VERSION)
  end
end
