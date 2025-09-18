# Copyright (c) Synopsys Inc.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require_relative "database_obj"

module Udb

##
# Represents a Programmer's Reference Manual specification
class Prm < TopLevelDatabaseObject

  # Store the resolver for processor config loading
  attr_accessor :resolver

  ##
  # @return [String] Brief description of this PRM
  def description
    @data["description"]
  end

  ##
  # @return [ConfiguredArchitecture] The processor configuration this PRM documents
  def processor_config
    return @processor_config unless @processor_config.nil?

    config_ref = @data["processor_config"]["$ref"]
    # Remove the trailing # if present
    config_path = config_ref.sub(/#\z/, '')

    # Resolve relative path from PRM file location to config file
    prm_dir = File.dirname(@data["$source"])
    config_full_path = File.expand_path(config_path, prm_dir)

    # Extract config name from the filename
    config_name = File.basename(config_full_path, '.yaml')

    @processor_config = @resolver.cfg_arch_for(config_name)
    @processor_config
  end


  ##
  # @return [Array<Hash>] Array of chapter definitions in their natural order
  def chapters
    @data["chapters"] || []
  end

end

end
