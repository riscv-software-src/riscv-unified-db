# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

# Contains Ruby methods included in Ruby class definition for any database object that can have coverage points
# defined in the database object's YAML definition.

require_relative "../coverage_point"

module Udb
module CanDefineCoveragePoints
  # @return [Array<CoveragePoint>]
  def coverage_points
    return @coverage_points unless @coverage_points.nil?

    @coverage_points = []
    @data["coverage_points"]&.each do |cp_data|
      cp = CoveragePoint.new(cp_data, self)
      arch.add_coverage_point(cp)
      @coverage_points << cp
    end
    @coverage_points
  end

  # @return [Hash<String, CoveragePoint>] Hash of all coverage points defined by database object
  def coverage_point_hash
    return @coverage_point_hash unless @coverage_point_hash.nil?

    @coverage_point_hash = {}
    coverage_points.each do |cp|
      @coverage_point_hash[cp.name] = cp
    end
    @coverage_point_hash
  end

  # @param cp_name [String] Unique name for coverage point
  # @return [CoveragePoint]
  # @return [nil] if there is no coverage point with name +cp_name+
  def coverage_point(cp_name) = coverage_point_hash[cp_name]
end # module
end
