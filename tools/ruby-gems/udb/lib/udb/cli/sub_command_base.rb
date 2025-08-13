#!/usr/bin/env ruby

# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

require "thor"

class SubCommandBase < Thor
  def self.banner(command, _namespace = nil, _subcommand = false)
    "#{basename} #{subcommand_prefix} #{command.usage}"
  end

  def self.subcommand_prefix
    T.must(name).gsub(/.*::/, "").gsub(/^[A-Z]/) { |match| T.must(match[0]).downcase }.gsub(/[A-Z]/) do |match|
      "-#{T.must(match[0]).downcase}"
    end
  end
end
