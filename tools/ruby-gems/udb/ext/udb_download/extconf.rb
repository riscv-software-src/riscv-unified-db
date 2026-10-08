# typed: false
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

# This extconf.rb runs at `gem install` time to download binaries and libraries
# (espresso, eqntott, must, Z3) from the GitHub releases for the current platform.
# It requires no external tools — only Ruby's built-in Net::HTTP.

require "digest"
require "fileutils"
require "net/http"
require "rbconfig"
require "uri"

# Check that required build tools are present
def find_executable(name)
  ENV.fetch("PATH", "").split(File::PATH_SEPARATOR).any? do |dir|
    File.executable?(File.join(dir, name))
  end
end

abort "ERROR: 'make' is not installed or not on PATH. Please install make before continuing." \
  unless find_executable("make")

# Load version constants from sibling lib files without requiring the full gem
load File.expand_path("../../lib/udb/dep_versions.rb", __dir__)

GITHUB_REPO = "riscv/riscv-unified-db"

cpu =
  case RbConfig::CONFIG["host_cpu"]
  when /arm64|aarch64/
    "arm64"
  when /x86_64|x64/
    "x64"
  else
    raise "Unsupported host cpu: #{RbConfig::CONFIG["host_cpu"]}. " \
          "Only x64 and arm64 are supported."
  end

xdg_cache = ENV.fetch("XDG_CACHE_HOME", File.join(Dir.home, ".cache"))

# Follow redirects (GitHub releases use a CDN redirect)
def download_with_redirects(url_str, limit: 10, hint: nil)
  raise "Too many HTTP redirects" if limit.zero?

  uri = URI.parse(url_str)
  http = Net::HTTP.new(uri.host, uri.port)
  http.use_ssl = (uri.scheme == "https")
  http.open_timeout = 30
  http.read_timeout = 120

  request = Net::HTTP::Get.new(uri.request_uri)
  request["User-Agent"] = "udb-gem/installer"

  response = http.request(request)

  case response
  when Net::HTTPSuccess
    response.body
  when Net::HTTPRedirection
    download_with_redirects(response["location"], limit: limit - 1, hint: hint)
  else
    msg = "Failed to download #{url_str}\nHTTP #{response.code} #{response.message}"
    msg += "\n#{hint}" if hint
    raise msg
  end
end

# ---------------------------------------------------------------------------
# espresso
# ---------------------------------------------------------------------------
espresso_version = Udb::ESPRESSO_VERSION
espresso_dir  = File.join(xdg_cache, "udb", "espresso", espresso_version, cpu)
espresso_file = File.join(espresso_dir, "espresso")

unless File.exist?(espresso_file)
  FileUtils.mkdir_p(espresso_dir)
  url_str = "https://github.com/#{GITHUB_REPO}/releases/download/#{espresso_version}/espresso-#{cpu}"
  $stderr.puts "Downloading espresso (#{espresso_version}, #{cpu}) from GitHub releases..."
  $stderr.puts "  URL: #{url_str}"
  File.binwrite(espresso_file, download_with_redirects(url_str))
  File.chmod(0o755, espresso_file)
  $stderr.puts "  Saved to #{espresso_file}"

  # Download and verify checksum
  checksum_url_str =
    "https://github.com/#{GITHUB_REPO}/releases/download/#{espresso_version}/espresso-#{cpu}.checksum"
  checksum_file = File.join(espresso_dir, "espresso.checksum")
  $stderr.puts "  Downloading checksum..."
  checksum_body = download_with_redirects(checksum_url_str)
  File.write(checksum_file, checksum_body)

  $stderr.puts "  Verifying checksum..."
  expected = checksum_body.strip.split(":")[1]
  actual   = Digest::SHA256.file(espresso_file).hexdigest

  if expected != actual
    $stderr.puts "ERROR: Checksum verification failed for espresso!"
    $stderr.puts "  Expected: #{expected}"
    $stderr.puts "  Got:      #{actual}"
    $stderr.puts "  The downloaded file may be corrupted or tampered with."
    abort "Checksum verification failed"
  end

  $stderr.puts "  Checksum verified successfully."
end

# ---------------------------------------------------------------------------
# eqntott
# ---------------------------------------------------------------------------
eqntott_version = Udb::EQNTOTT_VERSION
eqntott_dir  = File.join(xdg_cache, "udb", "eqntott", eqntott_version, cpu)
eqntott_file = File.join(eqntott_dir, "eqntott")

unless File.exist?(eqntott_file)
  FileUtils.mkdir_p(eqntott_dir)
  url_str = "https://github.com/#{GITHUB_REPO}/releases/download/#{eqntott_version}/eqntott-#{cpu}"
  $stderr.puts "Downloading eqntott (#{eqntott_version}, #{cpu}) from GitHub releases..."
  $stderr.puts "  URL: #{url_str}"
  File.binwrite(eqntott_file, download_with_redirects(url_str))
  File.chmod(0o755, eqntott_file)
  $stderr.puts "  Saved to #{eqntott_file}"

  # Download and verify checksum
  checksum_url_str =
    "https://github.com/#{GITHUB_REPO}/releases/download/#{eqntott_version}/eqntott-#{cpu}.checksum"
  checksum_file = File.join(eqntott_dir, "eqntott.checksum")
  $stderr.puts "  Downloading checksum..."
  checksum_body = download_with_redirects(checksum_url_str)
  File.write(checksum_file, checksum_body)

  $stderr.puts "  Verifying checksum..."
  expected = checksum_body.strip.split(":")[1]
  actual   = Digest::SHA256.file(eqntott_file).hexdigest

  if expected != actual
    $stderr.puts "ERROR: Checksum verification failed for eqntott!"
    $stderr.puts "  Expected: #{expected}"
    $stderr.puts "  Got:      #{actual}"
    $stderr.puts "  The downloaded file may be corrupted or tampered with."
    abort "Checksum verification failed"
  end

  $stderr.puts "  Checksum verified successfully."
end

# ---------------------------------------------------------------------------
# must
# ---------------------------------------------------------------------------
must_version = Udb::MUST_VERSION
must_dir  = File.join(xdg_cache, "udb", "must", must_version, cpu)
must_file = File.join(must_dir, "must")

unless File.exist?(must_file)
  FileUtils.mkdir_p(must_dir)
  url_str = "https://github.com/#{GITHUB_REPO}/releases/download/#{must_version}/must-#{cpu}"
  $stderr.puts "Downloading must (#{must_version}, #{cpu}) from GitHub releases..."
  $stderr.puts "  URL: #{url_str}"
  File.binwrite(must_file, download_with_redirects(url_str))
  File.chmod(0o755, must_file)
  $stderr.puts "  Saved to #{must_file}"

  # Download and verify checksum
  checksum_url_str =
    "https://github.com/#{GITHUB_REPO}/releases/download/#{must_version}/must-#{cpu}.checksum"
  checksum_file = File.join(must_dir, "must.checksum")
  $stderr.puts "  Downloading checksum..."
  checksum_body = download_with_redirects(checksum_url_str)
  File.write(checksum_file, checksum_body)

  $stderr.puts "  Verifying checksum..."
  expected = checksum_body.strip.split(":")[1]
  actual   = Digest::SHA256.file(must_file).hexdigest

  if expected != actual
    $stderr.puts "ERROR: Checksum verification failed for must!"
    $stderr.puts "  Expected: #{expected}"
    $stderr.puts "  Got:      #{actual}"
    $stderr.puts "  The downloaded file may be corrupted or tampered with."
    abort "Checksum verification failed"
  end

  $stderr.puts "  Checksum verified successfully."
end

# ---------------------------------------------------------------------------
# Z3
# ---------------------------------------------------------------------------
z3_version = Udb::Z3_VERSION
z3_dir  = File.join(xdg_cache, "udb", "z3", z3_version, cpu)
z3_file = File.join(z3_dir, "libz3.so")

if RbConfig::CONFIG["host_os"] =~ /darwin|mac os/
  abort <<~ERROR
    ERROR: Prebuilt Z3 binaries are not yet available for macOS.
    The published GitHub release assets contain Linux libz3.so binaries, which cannot be loaded on macOS.
    If you previously ran bin/setup on macOS, remove the cached Z3 directory:

      #{z3_dir}
    See https://github.com/riscv/riscv-unified-db/issues/1996
  ERROR
end

unless File.exist?(z3_file)
  FileUtils.mkdir_p(z3_dir)
  url_str = "https://github.com/#{GITHUB_REPO}/releases/download/#{z3_version}/libz3-#{cpu}.so"
  $stderr.puts "Downloading Z3 (#{z3_version}, #{cpu}) from GitHub releases..."
  $stderr.puts "  URL: #{url_str}"
  File.binwrite(
    z3_file,
    download_with_redirects(url_str, hint: "If you are a maintainer, run: bin/chore update z3")
  )
  $stderr.puts "  Saved to #{z3_file}"

  # Download and verify checksum
  checksum_url_str =
    "https://github.com/#{GITHUB_REPO}/releases/download/#{z3_version}/libz3-#{cpu}.checksum"
  checksum_file = File.join(z3_dir, "libz3.checksum")
  $stderr.puts "  Downloading checksum..."
  checksum_body = download_with_redirects(checksum_url_str)
  File.write(checksum_file, checksum_body)

  $stderr.puts "  Verifying checksum..."
  expected = checksum_body.strip.split(":")[1]
  actual   = Digest::SHA256.file(z3_file).hexdigest

  if expected != actual
    $stderr.puts "ERROR: Checksum verification failed for libz3!"
    $stderr.puts "  Expected: #{expected}"
    $stderr.puts "  Got:      #{actual}"
    $stderr.puts "  The downloaded file may be corrupted or tampered with."
    abort "Checksum verification failed"
  end

  $stderr.puts "  Checksum verified successfully."
end

# Write a no-op Makefile — we have no C extension to compile
File.write("Makefile", <<~MAKEFILE)
  all:
  \t@true
  install:
  \t@true
  clean:
  \t@true
MAKEFILE
