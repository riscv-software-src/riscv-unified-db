# Copyright (c) Debanjan Maji
# SPDX-License-Identifier: BSD-3-Clause-Clear
# typed: false

# frozen_string_literal: true

require_relative "test_helper"

require "udb/cfg_arch"
require "udb/resolver"

class TestInstruction < Minitest::Test
  include Udb

  private def operation_text(inst)
    inst.instance_variable_get(:@data)["operation()"]
  end

  private def idl_references_pc?(operation)
    operation.include?("$pc")
  end

  private def idl_changes_pc?(operation)
    operation.match?(/(?:jump(?:_halfword)?\(|^\s*\$pc\s*=)/)
  end

  def setup
    @resolver = Udb::Resolver.new(Udb.repo_root)
    @cfg_arch = @resolver.cfg_arch_for("_")
  end

  def test_decode_variable_sext_with_size
    # Load the database to get access to instructions
    db = @cfg_arch

    # Find an instruction with a signed immediate (sign_extend: true)
    # BNE is a good example - it has imm with sign_extend: true
    bne_inst = db.instructions.find { |i| i.name == "bne" }
    refute_nil bne_inst, "BNE instruction should be found"

    # Get the decode variable for imm (using base 32)
    imm_var = bne_inst.decode_variables(32).find { |v| v.name == "imm" }
    refute_nil imm_var, "imm decode variable should exist"

    # Verify it has sign_extend property
    assert imm_var.sext?, "imm should have sign_extend set to true"

    # Extract the variable and verify it includes the size parameter
    extracted = imm_var.extract
    assert_match(/sext\(.+,\s*\d+\)/, extracted, "sext call should include size parameter")

    # For BNE, the imm is 13 bits (12 bits + 1 bit left shift = 13 bits total)
    assert_match(/sext\(.+,\s*13\)/, extracted, "sext call for BNE imm should have size 13")
  end

  def test_decode_variable_without_sext
    # Load the database
    db = @cfg_arch

    # Find an instruction without signed immediate
    # ADD has rs1, rs2, rd but no signed immediates
    add_inst = db.instructions.find { |i| i.name == "add" }
    refute_nil add_inst, "ADD instruction should be found"

    # Get a decode variable (e.g., rs1) using base 32
    rs1_var = add_inst.decode_variables(32).find { |v| v.name == "xs1" }
    refute_nil rs1_var, "xs1 decode variable should exist"

    # Verify it does NOT have sign_extend
    refute rs1_var.sext?, "xs1 should not have sign_extend"

    # Extract and verify no sext call
    extracted = rs1_var.extract
    refute_match(/sext/, extracted, "non-signed decode variable should not use sext")
  end

  def test_explicit_pc_metadata
    db = @cfg_arch

    auipc_inst = db.instructions.find { |i| i.name == "auipc" }
    refute_nil auipc_inst, "AUIPC instruction should be found"
    assert auipc_inst.pc_references?, "AUIPC should explicitly reference the PC"
    refute auipc_inst.pc_changes?, "AUIPC should not explicitly change the PC"

    jalr_inst = db.instructions.find { |i| i.name == "jalr" }
    refute_nil jalr_inst, "JALR instruction should be found"
    assert jalr_inst.pc_references?, "JALR should explicitly reference the PC"
    assert jalr_inst.pc_changes?, "JALR should explicitly change the PC"

    mret_inst = db.instructions.find { |i| i.name == "mret" }
    refute_nil mret_inst, "MRET instruction should be found"
    refute mret_inst.pc_references?, "MRET should not explicitly reference the current PC"
    assert mret_inst.pc_changes?, "MRET should explicitly change the PC"

    add_inst = db.instructions.find { |i| i.name == "add" }
    refute_nil add_inst, "ADD instruction should be found"
    refute add_inst.pc_references?, "Instructions without pc metadata should default to not referencing the PC"
    refute add_inst.pc_changes?, "Instructions without pc metadata should default to not changing the PC"
  end

  def test_explicit_pc_metadata_agrees_with_idl
    @cfg_arch.instructions.each do |inst|
      next unless inst.pc_references? || inst.pc_changes?

      operation = operation_text(inst)
      refute_nil operation, "#{inst.name} should define operation() when explicit pc metadata is present"

      if inst.pc_references?
        assert idl_references_pc?(operation), "#{inst.name} pc.references should agree with operation()"
      end

      if inst.pc_changes?
        assert idl_changes_pc?(operation), "#{inst.name} pc.changes should agree with operation()"
      end
    end
  end
end
