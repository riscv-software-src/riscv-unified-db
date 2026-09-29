#!/usr/bin/env ruby
# frozen_string_literal: true
# typed: false
#
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#
# FPgen-inspired floating-point stimulus generator scaffold.
#
# This utility is intentionally narrow in scope:
# - RISC-V single-precision focused
# - top-level fp.idl-style operations only
# - uses the existing UDB Z3 integration
#
# The first implementation provides:
# - a task model for f32-oriented directed generation
# - "all types" stimulus generation using Z3 over IEEE-754 bit patterns
# - deterministic JSON output suitable for checked-in corpora
#
# It does not yet model full arithmetic semantics in SMT.
# Those constraints are expected to be checked/refined by the C++/SoftFloat
# comparison harness and future generator passes.

require "json"
require "optparse"
require "pathname"
require "set"

$LOAD_PATH.unshift(File.expand_path("../ruby-gems/udb/lib", __dir__))

require "udb/z3"

module Udb
  module FpGen
    F32_WIDTH = 32
    F32_EXP_BITS = 8
    F32_FRAC_BITS = 23

    ROUNDING_MODES = %w[RNE RTZ RDN RUP RMM].freeze
    F32_BINARY_OPS = %w[f32_add f32_sub f32_mul f32_div].freeze
    F32_UNARY_OPS = %w[f32_sqrt f32_to_i32 f32_to_ui32 f32_to_i64 f32_to_ui64].freeze
    F32_FROM_INT_OPS = %w[i32_to_f32 ui32_to_f32 i64_to_f32 ui64_to_f32].freeze
    F32_TERNARY_OPS = %w[f32_muladd].freeze
    F32_MULADD_OPS = %w[
      Softfloat_mulAdd_addC
      Softfloat_mulAdd_subC
      Softfloat_mulAdd_subProd
    ].freeze

    ALL_TYPES = %w[
      pos_zero
      neg_zero
      pos_subnormal
      neg_subnormal
      pos_normal
      neg_normal
      pos_inf
      neg_inf
      qnan
      snan
    ].freeze

    DIRECTED_F32_SPECIALS = {
      pos_zero: 0x00000000,
      neg_zero: 0x80000000,
      min_subnormal: 0x00000001,
      max_subnormal: 0x007f_ffff,
      neg_min_subnormal: 0x80000001,
      neg_max_subnormal: 0x807f_ffff,
      min_normal: 0x0080_0000,
      neg_min_normal: 0x8080_0000,
      one: 0x3f80_0000,
      neg_one: 0xbf80_0000,
      two: 0x4000_0000,
      three: 0x4040_0000,
      half: 0x3f00_0000,
      largest_finite: 0x7f7f_ffff,
      neg_largest_finite: 0xff7f_ffff,
      pos_inf: 0x7f80_0000,
      neg_inf: 0xff80_0000,
      canonical_qnan: 0x7fc0_0000,
      neg_qnan: 0xffc0_0000,
      snan: 0x7f80_0001,
      neg_snan: 0xff80_0001,
      ui32_overflow_edge: 0x4f80_0000,
      i32_overflow_edge: 0x4f00_0000,
      neg_i32_overflow_edge: 0xcf80_0000,
      i32_min_exact: 0xcf00_0000,
      neg_i64_overflow_edge: 0xdf80_0000,
      i64_min_exact: 0xdf00_0000,
      tiny_normal: 0x0080_0001,
      tiny_subnormal: 0x0000_0040,
      just_below_one: 0x3f7f_ffff,
      just_above_one: 0x3f80_0001,
      just_below_half: 0x3eff_ffff,
      just_above_half: 0x3f00_0001,
      just_below_two: 0x3fff_ffff,
      just_above_two: 0x4000_0001,
      largest_less_than_one: 0x3f7f_ffff,
      neg_just_above_neg_one: 0xbf80_0001,
      neg_just_below_neg_one: 0xbf7f_ffff,
      quarter: 0x3e80_0000,
      neg_half: 0xbf00_0000,
      neg_two: 0xc000_0000,
      neg_three: 0xc040_0000
    }.freeze

    class << self
      def directed_vectors
        s = DIRECTED_F32_SPECIALS

        [
          # Rounding-mode-sensitive arithmetic
          {"source"=>"fpgen_directed","kind"=>"rounding","op"=>"f32_add","rm"=>"RTZ","a"=>hex32(s[:just_below_one]),"b"=>hex32(s[:tiny_subnormal])},
          {"source"=>"fpgen_directed","kind"=>"rounding","op"=>"f32_add","rm"=>"RUP","a"=>hex32(s[:just_below_one]),"b"=>hex32(s[:tiny_subnormal])},
          {"source"=>"fpgen_directed","kind"=>"rounding","op"=>"f32_sub","rm"=>"RDN","a"=>hex32(s[:one]),"b"=>hex32(s[:tiny_subnormal])},
          {"source"=>"fpgen_directed","kind"=>"rounding","op"=>"f32_mul","rm"=>"RTZ","a"=>hex32(s[:largest_finite]),"b"=>hex32(s[:two])},
          {"source"=>"fpgen_directed","kind"=>"rounding","op"=>"f32_div","rm"=>"RMM","a"=>hex32(s[:one]),"b"=>hex32(s[:three])},
          {"source"=>"fpgen_directed","kind"=>"rounding","op"=>"f32_sqrt","rm"=>"RUP","a"=>hex32(s[:two])},

          # Signed zero behavior
          {"source"=>"fpgen_directed","kind"=>"signed_zero","op"=>"f32_add","rm"=>"RNE","a"=>hex32(s[:pos_zero]),"b"=>hex32(s[:neg_zero])},
          {"source"=>"fpgen_directed","kind"=>"signed_zero","op"=>"f32_mul","rm"=>"RNE","a"=>hex32(s[:neg_zero]),"b"=>hex32(s[:two])},
          {"source"=>"fpgen_directed","kind"=>"signed_zero","op"=>"f32_div","rm"=>"RNE","a"=>hex32(s[:neg_zero]),"b"=>hex32(s[:two])},

          # Subnormal / underflow focused
          {"source"=>"fpgen_directed","kind"=>"subnormal","op"=>"f32_add","rm"=>"RNE","a"=>hex32(s[:min_subnormal]),"b"=>hex32(s[:min_subnormal])},
          {"source"=>"fpgen_directed","kind"=>"subnormal","op"=>"f32_sub","rm"=>"RNE","a"=>hex32(s[:min_normal]),"b"=>hex32(s[:max_subnormal])},
          {"source"=>"fpgen_directed","kind"=>"subnormal","op"=>"f32_mul","rm"=>"RNE","a"=>hex32(s[:min_subnormal]),"b"=>hex32(s[:half])},
          {"source"=>"fpgen_directed","kind"=>"subnormal","op"=>"f32_mul","rm"=>"RNE","a"=>hex32(s[:max_subnormal]),"b"=>hex32(s[:half])},
          {"source"=>"fpgen_directed","kind"=>"subnormal","op"=>"f32_div","rm"=>"RNE","a"=>hex32(s[:min_subnormal]),"b"=>hex32(s[:two])},
          {"source"=>"fpgen_directed","kind"=>"subnormal","op"=>"f32_sqrt","rm"=>"RNE","a"=>hex32(s[:min_subnormal])},

          # NaN / sNaN propagation
          {"source"=>"fpgen_directed","kind"=>"nan","op"=>"f32_add","rm"=>"RNE","a"=>hex32(s[:snan]),"b"=>hex32(s[:one])},
          {"source"=>"fpgen_directed","kind"=>"nan","op"=>"f32_sub","rm"=>"RNE","a"=>hex32(s[:one]),"b"=>hex32(s[:snan])},
          {"source"=>"fpgen_directed","kind"=>"nan","op"=>"f32_mul","rm"=>"RNE","a"=>hex32(s[:neg_snan]),"b"=>hex32(s[:two])},
          {"source"=>"fpgen_directed","kind"=>"nan","op"=>"f32_div","rm"=>"RNE","a"=>hex32(s[:canonical_qnan]),"b"=>hex32(s[:snan])},
          {"source"=>"fpgen_directed","kind"=>"nan","op"=>"f32_sqrt","rm"=>"RNE","a"=>hex32(s[:snan])},

          # FMA corner cases
          {"source"=>"fpgen_directed","kind"=>"muladd","op"=>"f32_muladd","muladd_op"=>"Softfloat_mulAdd_addC","rm"=>"RNE","a"=>hex32(s[:one]),"b"=>hex32(s[:neg_one]),"c"=>hex32(s[:one])},
          {"source"=>"fpgen_directed","kind"=>"muladd","op"=>"f32_muladd","muladd_op"=>"Softfloat_mulAdd_addC","rm"=>"RNE","a"=>hex32(s[:max_subnormal]),"b"=>hex32(s[:half]),"c"=>hex32(s[:min_subnormal])},
          {"source"=>"fpgen_directed","kind"=>"muladd","op"=>"f32_muladd","muladd_op"=>"Softfloat_mulAdd_subC","rm"=>"RNE","a"=>hex32(s[:snan]),"b"=>hex32(s[:one]),"c"=>hex32(s[:two])},

          # Conversion boundaries
          {"source"=>"fpgen_directed","kind"=>"convert","op"=>"f32_to_i32","rm"=>"RUP","a"=>hex32(s[:i32_overflow_edge])},
          {"source"=>"fpgen_directed","kind"=>"convert","op"=>"f32_to_ui32","rm"=>"RNE","a"=>hex32(s[:neg_min_subnormal])},
          {"source"=>"fpgen_directed","kind"=>"convert","op"=>"f32_to_ui32","rm"=>"RNE","a"=>hex32(s[:ui32_overflow_edge])},
          {"source"=>"fpgen_directed","kind"=>"convert","op"=>"f32_to_ui32","rm"=>"RNE","a"=>hex32(s[:canonical_qnan])},
          {"source"=>"fpgen_directed","kind"=>"convert","op"=>"f32_to_i64","rm"=>"RNE","a"=>hex32(s[:neg_qnan])},
          {"source"=>"fpgen_directed","kind"=>"convert","op"=>"f32_to_ui64","rm"=>"RNE","a"=>hex32(s[:neg_one])},
          {"source"=>"fpgen_directed","kind"=>"convert","op"=>"f32_to_ui64","rm"=>"RNE","a"=>hex32(s[:canonical_qnan])},

          # Int-to-float boundaries
          {"source"=>"fpgen_directed","kind"=>"int_to_float","op"=>"i32_to_f32","rm"=>"RNE","a"=>"0x7fffffff"},
          {"source"=>"fpgen_directed","kind"=>"int_to_float","op"=>"ui32_to_f32","rm"=>"RNE","a"=>"0x80000000"},
          {"source"=>"fpgen_directed","kind"=>"int_to_float","op"=>"i64_to_f32","rm"=>"RNE","a"=>"0x7fffffffffffffff"},
          {"source"=>"fpgen_directed","kind"=>"int_to_float","op"=>"ui64_to_f32","rm"=>"RNE","a"=>"0x8000000000000000"},

          # Exception-focused vectors
          {"source"=>"fpgen_directed","kind"=>"invalid","op"=>"f32_add","rm"=>"RNE","a"=>hex32(s[:pos_inf]),"b"=>hex32(s[:neg_inf])},
          {"source"=>"fpgen_directed","kind"=>"invalid","op"=>"f32_mul","rm"=>"RNE","a"=>hex32(s[:pos_inf]),"b"=>hex32(s[:pos_zero])},
          {"source"=>"fpgen_directed","kind"=>"invalid","op"=>"f32_div","rm"=>"RNE","a"=>hex32(s[:pos_zero]),"b"=>hex32(s[:pos_zero])},
          {"source"=>"fpgen_directed","kind"=>"divbyzero","op"=>"f32_div","rm"=>"RNE","a"=>hex32(s[:one]),"b"=>hex32(s[:pos_zero])},
          {"source"=>"fpgen_directed","kind"=>"overflow","op"=>"f32_mul","rm"=>"RNE","a"=>hex32(s[:largest_finite]),"b"=>hex32(s[:largest_finite])},
          {"source"=>"fpgen_directed","kind"=>"overflow","op"=>"f32_add","rm"=>"RNE","a"=>hex32(s[:largest_finite]),"b"=>hex32(s[:largest_finite])},
          {"source"=>"fpgen_directed","kind"=>"underflow","op"=>"f32_mul","rm"=>"RNE","a"=>hex32(s[:min_subnormal]),"b"=>hex32(s[:half])},
          {"source"=>"fpgen_directed","kind"=>"underflow","op"=>"f32_div","rm"=>"RNE","a"=>hex32(s[:min_subnormal]),"b"=>hex32(s[:largest_finite])},
          {"source"=>"fpgen_directed","kind"=>"inexact","op"=>"f32_div","rm"=>"RNE","a"=>hex32(s[:one]),"b"=>hex32(s[:three])},
          {"source"=>"fpgen_directed","kind"=>"inexact","op"=>"f32_sqrt","rm"=>"RNE","a"=>hex32(s[:two])},

          # Rounding boundary matrices
          {"source"=>"fpgen_directed","kind"=>"rounding_boundary","op"=>"f32_to_i32","rm"=>"RNE","a"=>hex32(s[:just_below_one])},
          {"source"=>"fpgen_directed","kind"=>"rounding_boundary","op"=>"f32_to_i32","rm"=>"RTZ","a"=>hex32(s[:just_below_one])},
          {"source"=>"fpgen_directed","kind"=>"rounding_boundary","op"=>"f32_to_i32","rm"=>"RUP","a"=>hex32(s[:just_below_one])},
          {"source"=>"fpgen_directed","kind"=>"rounding_boundary","op"=>"f32_to_ui32","rm"=>"RTZ","a"=>hex32(s[:just_above_half])},
          {"source"=>"fpgen_directed","kind"=>"rounding_boundary","op"=>"f32_to_ui32","rm"=>"RUP","a"=>hex32(s[:just_above_half])},
          {"source"=>"fpgen_directed","kind"=>"rounding_boundary","op"=>"f32_add","rm"=>"RNE","a"=>hex32(s[:one]),"b"=>hex32(s[:tiny_subnormal])},
          {"source"=>"fpgen_directed","kind"=>"rounding_boundary","op"=>"f32_add","rm"=>"RTZ","a"=>hex32(s[:one]),"b"=>hex32(s[:tiny_subnormal])},
          {"source"=>"fpgen_directed","kind"=>"rounding_boundary","op"=>"f32_add","rm"=>"RUP","a"=>hex32(s[:one]),"b"=>hex32(s[:tiny_subnormal])},

          # Representative class-matrix coverage
          {"source"=>"fpgen_directed","kind"=>"class_matrix","op"=>"f32_add","rm"=>"RNE","a"=>hex32(s[:pos_inf]),"b"=>hex32(s[:canonical_qnan])},
          {"source"=>"fpgen_directed","kind"=>"class_matrix","op"=>"f32_add","rm"=>"RNE","a"=>hex32(s[:max_subnormal]),"b"=>hex32(s[:min_normal])},
          {"source"=>"fpgen_directed","kind"=>"class_matrix","op"=>"f32_sub","rm"=>"RNE","a"=>hex32(s[:neg_inf]),"b"=>hex32(s[:largest_finite])},
          {"source"=>"fpgen_directed","kind"=>"class_matrix","op"=>"f32_mul","rm"=>"RNE","a"=>hex32(s[:neg_max_subnormal]),"b"=>hex32(s[:neg_min_normal])},
          {"source"=>"fpgen_directed","kind"=>"class_matrix","op"=>"f32_div","rm"=>"RNE","a"=>hex32(s[:min_normal]),"b"=>hex32(s[:max_subnormal])},
          {"source"=>"fpgen_directed","kind"=>"class_matrix","op"=>"f32_sqrt","rm"=>"RNE","a"=>hex32(s[:largest_finite])},
          {"source"=>"fpgen_directed","kind"=>"class_matrix","op"=>"f32_muladd","muladd_op"=>"Softfloat_mulAdd_addC","rm"=>"RNE","a"=>hex32(s[:neg_zero]),"b"=>hex32(s[:neg_min_normal]),"c"=>hex32(s[:neg_max_subnormal])},
          {"source"=>"fpgen_directed","kind"=>"class_matrix","op"=>"f32_muladd","muladd_op"=>"Softfloat_mulAdd_subProd","rm"=>"RNE","a"=>hex32(s[:largest_finite]),"b"=>hex32(s[:half]),"c"=>hex32(s[:neg_largest_finite])},

          # More FMA sign/cancellation coverage
          {"source"=>"fpgen_directed","kind"=>"muladd","op"=>"f32_muladd","muladd_op"=>"Softfloat_mulAdd_addC","rm"=>"RNE","a"=>hex32(s[:one]),"b"=>hex32(s[:one]),"c"=>hex32(s[:neg_one])},
          {"source"=>"fpgen_directed","kind"=>"muladd","op"=>"f32_muladd","muladd_op"=>"Softfloat_mulAdd_subProd","rm"=>"RNE","a"=>hex32(s[:one]),"b"=>hex32(s[:one]),"c"=>hex32(s[:one])},
          {"source"=>"fpgen_directed","kind"=>"muladd","op"=>"f32_muladd","muladd_op"=>"Softfloat_mulAdd_addC","rm"=>"RNE","a"=>hex32(s[:largest_finite]),"b"=>hex32(s[:two]),"c"=>hex32(s[:neg_largest_finite])},
          {"source"=>"fpgen_directed","kind"=>"muladd","op"=>"f32_muladd","muladd_op"=>"Softfloat_mulAdd_subC","rm"=>"RNE","a"=>hex32(s[:one]),"b"=>hex32(s[:one]),"c"=>hex32(s[:one])},

          # Expanded int-to-float rounding boundaries
          {"source"=>"fpgen_directed","kind"=>"int_to_float","op"=>"i32_to_f32","rm"=>"RNE","a"=>"0x01000001"},
          {"source"=>"fpgen_directed","kind"=>"int_to_float","op"=>"i32_to_f32","rm"=>"RNE","a"=>"0x00ffffff"},
          {"source"=>"fpgen_directed","kind"=>"int_to_float","op"=>"ui32_to_f32","rm"=>"RNE","a"=>"0x01000001"},
          {"source"=>"fpgen_directed","kind"=>"int_to_float","op"=>"i64_to_f32","rm"=>"RNE","a"=>"0x0000000100000001"},
          {"source"=>"fpgen_directed","kind"=>"int_to_float","op"=>"ui64_to_f32","rm"=>"RNE","a"=>"0x0000000100000001"},

          # Negative overflow in signed int conversion — distinguishes INT_MIN from INT_MAX
          {"source"=>"fpgen_directed","kind"=>"convert_neg_overflow","op"=>"f32_to_i32","rm"=>"RNE","a"=>hex32(s[:neg_inf])},
          {"source"=>"fpgen_directed","kind"=>"convert_neg_overflow","op"=>"f32_to_i32","rm"=>"RNE","a"=>hex32(s[:neg_i32_overflow_edge])},
          {"source"=>"fpgen_directed","kind"=>"convert_neg_overflow","op"=>"f32_to_i64","rm"=>"RNE","a"=>hex32(s[:neg_inf])},
          {"source"=>"fpgen_directed","kind"=>"convert_neg_overflow","op"=>"f32_to_i64","rm"=>"RNE","a"=>hex32(s[:neg_i64_overflow_edge])},

          # Exact boundary conversion at INT64_MIN
          {"source"=>"fpgen_directed","kind"=>"convert","op"=>"f32_to_i64","rm"=>"RNE","a"=>hex32(s[:i64_min_exact])},

          # Additional signed-zero, invalid, and NaN cases
          {"source"=>"fpgen_directed","kind"=>"signed_zero","op"=>"f32_sub","rm"=>"RNE","a"=>hex32(s[:neg_zero]),"b"=>hex32(s[:pos_zero])},
          {"source"=>"fpgen_directed","kind"=>"invalid","op"=>"f32_sub","rm"=>"RNE","a"=>hex32(s[:pos_inf]),"b"=>hex32(s[:pos_inf])},
          {"source"=>"fpgen_directed","kind"=>"invalid","op"=>"f32_div","rm"=>"RNE","a"=>hex32(s[:pos_inf]),"b"=>hex32(s[:pos_inf])},
          {"source"=>"fpgen_directed","kind"=>"signed_zero","op"=>"f32_sqrt","rm"=>"RNE","a"=>hex32(s[:neg_zero])},
          {"source"=>"fpgen_directed","kind"=>"invalid","op"=>"f32_sqrt","rm"=>"RNE","a"=>hex32(s[:neg_one])},
          {"source"=>"fpgen_directed","kind"=>"nan","op"=>"f32_sqrt","rm"=>"RNE","a"=>hex32(s[:canonical_qnan])}
        ]
      end

      def hex32(value)
        format("0x%08x", unsigned32(value))
      end

      def unsigned32(value)
        value & 0xffff_ffff
      end

      def bit(expr, idx)
        expr.extract(idx, idx)
      end

      def bits(expr, msb, lsb)
        expr.extract(msb, lsb)
      end

      def sign(expr)
        bit(expr, 31)
      end

      def exponent(expr)
        bits(expr, 30, 23)
      end

      def fraction(expr)
        bits(expr, 22, 0)
      end

      def exp_all_zeros?(expr)
        exponent(expr) == 0
      end

      def exp_all_ones?(expr)
        exponent(expr) == 0xff
      end

      def frac_zero?(expr)
        fraction(expr) == 0
      end

      def is_zero(expr)
        exp_all_zeros?(expr) & frac_zero?(expr)
      end

      def is_subnormal(expr)
        exp_all_zeros?(expr) & (fraction(expr) != 0)
      end

      def is_inf(expr)
        exp_all_ones?(expr) & frac_zero?(expr)
      end

      def is_nan(expr)
        exp_all_ones?(expr) & (fraction(expr) != 0)
      end

      def is_qnan(expr)
        is_nan(expr) & (bit(expr, 22) == 1)
      end

      def is_snan(expr)
        exp_all_ones?(expr) & (bit(expr, 22) == 0) & (bits(expr, 21, 0) != 0)
      end

      def is_normal(expr)
        (exponent(expr) != 0) & (exponent(expr) != 0xff)
      end

      def positive(expr)
        sign(expr) == 0
      end

      def negative(expr)
        sign(expr) == 1
      end

      def classify(expr, klass)
        case klass
        when "pos_zero"      then positive(expr) & is_zero(expr)
        when "neg_zero"      then negative(expr) & is_zero(expr)
        when "pos_subnormal" then positive(expr) & is_subnormal(expr)
        when "neg_subnormal" then negative(expr) & is_subnormal(expr)
        when "pos_normal"    then positive(expr) & is_normal(expr)
        when "neg_normal"    then negative(expr) & is_normal(expr)
        when "pos_inf"       then positive(expr) & is_inf(expr)
        when "neg_inf"       then negative(expr) & is_inf(expr)
        when "qnan"          then is_qnan(expr)
        when "snan"          then is_snan(expr)
        else
          raise ArgumentError, "unknown FP class: #{klass}"
        end
      end

      def all_types_tasks
        tasks = []

        F32_BINARY_OPS.each do |op|
          ALL_TYPES.each do |a_type|
            ALL_TYPES.each do |b_type|
              ROUNDING_MODES.each do |rm|
                tasks << {
                  "source" => "fpgen_like",
                  "kind" => "all_types",
                  "op" => op,
                  "rm" => rm,
                  "a_class" => a_type,
                  "b_class" => b_type,
                }
              end
            end
          end
        end

        F32_TERNARY_OPS.each do |op|
          ALL_TYPES.each do |a_type|
            ALL_TYPES.each do |b_type|
              ALL_TYPES.each do |c_type|
                ROUNDING_MODES.each do |rm|
                  F32_MULADD_OPS.each do |muladd_op|
                    tasks << {
                      "source" => "fpgen_like",
                      "kind" => "all_types",
                      "op" => op,
                      "rm" => rm,
                      "muladd_op" => muladd_op,
                      "a_class" => a_type,
                      "b_class" => b_type,
                      "c_class" => c_type,
                    }
                  end
                end
              end
            end
          end
        end

        F32_UNARY_OPS.each do |op|
          ALL_TYPES.each do |a_type|
            ROUNDING_MODES.each do |rm|
              tasks << {
                "source" => "fpgen_like",
                "kind" => "all_types",
                "op" => op,
                "rm" => rm,
                "a_class" => a_type,
              }
            end
          end
        end

        F32_FROM_INT_OPS.each do |op|
          ROUNDING_MODES.each do |rm|
            tasks << {
              "source" => "fpgen_like",
              "kind" => "int_to_f32_smoke",
              "op" => op,
              "rm" => rm,
            }
          end
        end

        tasks
      end
    end

    class Generator
      def initialize(samples_per_task:, seed:)
        @samples_per_task = samples_per_task
        @rng = Random.new(seed)
      end

      def emit_all_types(io)
        Udb::Z3Solver.configure_parallelization(false)
        all_types = Udb::FpGen.all_types_tasks
        seen = Set.new

        all_types.each do |task|
          emit_task(io, task, seen)
        end
      end

      private

      def emit_task(io, task, seen)
        case task.fetch("op")
        when *F32_BINARY_OPS
          emit_binary_task(io, task, seen)
        when *F32_TERNARY_OPS
          emit_ternary_task(io, task, seen)
        when *F32_UNARY_OPS
          emit_unary_task(io, task, seen)
        when *F32_FROM_INT_OPS
          emit_int_to_f32_smoke_task(io, task, seen)
        else
          raise ArgumentError, "unsupported task op #{task.fetch("op")}"
        end
      end

      def emit_binary_task(io, task, seen)
        solver = Udb::Z3Solver.new
        a = Z3.Bitvec("a_#{@rng.rand(1 << 30)}", F32_WIDTH)
        b = Z3.Bitvec("b_#{@rng.rand(1 << 30)}", F32_WIDTH)

        solver.assert(Udb::FpGen.classify(a, task.fetch("a_class")))
        solver.assert(Udb::FpGen.classify(b, task.fetch("b_class")))

        sample_models(solver, count: @samples_per_task) do |model|
          vector = task.merge(
            "a" => format_hex(model[a]),
            "b" => format_hex(model[b]),
          )
          write_unique(io, seen, vector)
        end
      end

      def emit_ternary_task(io, task, seen)
        solver = Udb::Z3Solver.new
        a = Z3.Bitvec("a_#{@rng.rand(1 << 30)}", F32_WIDTH)
        b = Z3.Bitvec("b_#{@rng.rand(1 << 30)}", F32_WIDTH)
        c = Z3.Bitvec("c_#{@rng.rand(1 << 30)}", F32_WIDTH)

        solver.assert(Udb::FpGen.classify(a, task.fetch("a_class")))
        solver.assert(Udb::FpGen.classify(b, task.fetch("b_class")))
        solver.assert(Udb::FpGen.classify(c, task.fetch("c_class")))

        sample_models(solver, count: @samples_per_task) do |model|
          vector = task.merge(
            "a" => format_hex(model[a]),
            "b" => format_hex(model[b]),
            "c" => format_hex(model[c]),
          )
          write_unique(io, seen, vector)
        end
      end

      def emit_unary_task(io, task, seen)
        solver = Udb::Z3Solver.new
        a = Z3.Bitvec("a_#{@rng.rand(1 << 30)}", F32_WIDTH)

        solver.assert(Udb::FpGen.classify(a, task.fetch("a_class")))

        sample_models(solver, count: @samples_per_task) do |model|
          vector = task.merge(
            "a" => format_hex(model[a]),
          )
          write_unique(io, seen, vector)
        end
      end

      def emit_int_to_f32_smoke_task(io, task, seen)
        values =
          case task.fetch("op")
          when "i32_to_f32"
            [0, 1, -1, -(2**31), 2**31 - 1]
          when "ui32_to_f32"
            [0, 1, 2**31, 2**32 - 1]
          when "i64_to_f32"
            [0, 1, -1, -(2**63), 2**63 - 1]
          when "ui64_to_f32"
            [0, 1, 2**63, 2**64 - 1]
          else
            raise ArgumentError, "unsupported int_to_f32 op"
          end

        values.each do |value|
          vector = task.merge("a" => format_int(task.fetch("op"), value))
          write_unique(io, seen, vector)
        end
      end

      def sample_models(solver, count:)
        generated = 0
        while generated < count && solver.satisfiable?
          model = solver.model
          yield model

          assignments =
            model.to_h.map do |decl, value|
              decl == value
            end
          solver.assert(~Z3.And(*assignments))
          generated += 1
        end
      end

      def write_unique(io, seen, vector)
        key = JSON.generate(vector)
        return if seen.include?(key)

        seen << key
        io.puts(key)
      end

      def format_hex(z3_value)
        value =
          case z3_value
          when Integer
            z3_value
          else
            value_text = z3_value.to_s

            case value_text
            when /\A#x([0-9a-fA-F]+)\z/
              Regexp.last_match(1).to_i(16)
            when /\A#b([01]+)\z/
              Regexp.last_match(1).to_i(2)
            when /\A\d+\z/
              value_text.to_i(10)
            when /\ABitvec\(\d+\)<(\d+)>\z/
              Regexp.last_match(1).to_i(10)
            when /\ABits<((?:0x)?[0-9a-fA-F]+)>\z/
              Regexp.last_match(1).to_i(16)
            else
              raise ArgumentError, "unsupported Z3 bitvector literal format: #{value_text.inspect}"
            end
          end
        format("0x%08x", Udb::FpGen.unsigned32(value))
      end

      def format_int(op, value)
        case op
        when "i32_to_f32", "ui32_to_f32"
          format("0x%08x", value & 0xffff_ffff)
        when "i64_to_f32", "ui64_to_f32"
          format("0x%016x", value & 0xffff_ffff_ffff_ffff)
        else
          raise ArgumentError, "unsupported integer formatting op #{op}"
        end
      end
    end
  end
end

options = {
  output: nil,
  samples_per_task: 1,
  seed: 1234,
  emit_all_types: false,
}

parser = OptionParser.new do |opts|
  opts.banner = "Usage: fpgen_generate.rb --output PATH [--samples-per-task N] [--seed N]"

  opts.on("--output PATH", "Output JSONL file") { |v| options[:output] = v }
  opts.on("--samples-per-task N", Integer, "Number of satisfying models per task") do |v|
    options[:samples_per_task] = v
  end
  opts.on("--seed N", Integer, "Deterministic RNG seed") { |v| options[:seed] = v }
  opts.on("--all-types", "Also emit Z3-generated all-types vectors") { options[:emit_all_types] = true }
end

parser.parse!

if options[:output].nil?
  warn parser.to_s
  exit 1
end

output_path = Pathname(options[:output])
output_path.dirname.mkpath

File.open(output_path, "w") do |io|
  Udb::FpGen.directed_vectors.each do |vector|
    io.puts(JSON.generate(vector))
  end

  if options[:emit_all_types]
    generator = Udb::FpGen::Generator.new(
      samples_per_task: options[:samples_per_task],
      seed: options[:seed],
    )
    generator.emit_all_types(io)
  end
end
