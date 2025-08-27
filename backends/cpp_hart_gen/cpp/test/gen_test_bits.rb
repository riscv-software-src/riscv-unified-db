#/usr/bin/env ruby

# frozen_string_literal: true

require "fileutils"
require "optparse"

$seed = 1234
NOUTPUTS = 6
$output = Array(NOUTPUTS).map { $stdout }

OptionParser.new do |opts|
  opts.banner = "Usage: gen_test_bits.rb [options]"

  opts.on("-o", "--output-dir DIRECTORY", "Write results to DIRECTORY, or concatenate them all to stdout if '-'. Default is '-'") do |o|
    if o == "-"
      $output = Array(NOUTPUTS).map { $stdout }
    else
      FileUtils.mkdir_p (o)
      NOUTPUTS.times do |i|
        $output[i] = File.open("#{o}/test_bits_random_#{i}.cpp", 'w')
      end
    end
  end

  opts.on("-s", "--seed", "Set random seed (default: #{$seed})") do |s|
    $seed = s.to_i
  end
end.parse!


$prng = Random.new($seed)

class Bits
  attr_reader :width, :signed

  def initialize(value, width, signed: false)
    @width = width
    @value = value & mask()
    @signed = signed
  end

  def mask
    (1 << width) - 1
  end

  def value
    if @signed
      if (@value >> (@width - 1)).zero?
        @value
      else
        # two's compliment
        -((~@value + 1) & mask())
      end
    else
      @value
    end
  end

  def to_s
    "#{@width}'#{@signed ? 's' : ''}#{@value}"
  end

  BINARY_ARITH_OPS = [:+, :'`+', :-, :'`-', :*, :'`*', :/, :%, :>>, :'>>>', :<<, :'`<<']
  def binary_expr(op, rhs)
    case op
    when :+
      Bits.new(value + rhs.value, [@width, rhs.width].max, signed: @signed && rhs.signed)
    when :'`+'
      Bits.new(value + rhs.value, [@width, rhs.width].max + 1, signed: @signed && rhs.signed)
    when :-
      Bits.new(value - rhs.value, [@width, rhs.width].max, signed: @signed && rhs.signed)
    when :'`-'
      Bits.new(value - rhs.value, [@width, rhs.width].max + 1, signed: @signed && rhs.signed)
    when :*
      Bits.new(value * rhs.value, [@width, rhs.width].max, signed: @signed && rhs.signed)
    when :'`*'
      Bits.new(value * rhs.value, @width + rhs.width, signed: @signed && rhs.signed)
    when :/
      Bits.new(value / rhs.value, [@width, rhs.width].max, signed: @signed && rhs.signed)
    when :%
      Bits.new(value % rhs.value, [@width, rhs.width].max, signed: @signed && rhs.signed)
    when :>>
      if value < 0
        Bits.new(@value >> rhs.value, @width, signed: @signed)
      else
        Bits.new(value >> rhs.value, @width, signed: @signed)
      end
    when :'>>>'
      if value < 0
        Bits.new(value >> rhs.value, @width, signed: @signed)
      else
        if ((value >> (@width - 1)) & 1).zero?
          Bits.new(value >> rhs.value, @width, signed: @signed)
        else
          # convert to signed, shift, then convert back
          signed_value = Bits.new(value, @width, signed: true).value
          Bits.new((signed_value >> rhs.value), @width, signed: @signed)
        end
      end
    when :<<
      Bits.new(value << rhs.value, @width, signed: @signed)
    when :'`<<'
      Bits.new(value << rhs.value, @width + rhs.value, signed: @signed)
    else
      raise "bad op: #{op}"
    end
  end

  def self.binary_expr_cpp(op, lhs, rhs)
    case op
    when :+
      "#{lhs} + #{rhs}"
    when :'`+'
      "#{lhs}.widening_add(#{rhs})"
    when :-
      "#{lhs} - #{rhs}"
    when :'`-'
      "#{lhs}.widening_sub(#{rhs})"
    when :*
      "#{lhs} * #{rhs}"
    when :'`*'
      "#{lhs}.widening_mul(#{rhs})"
    when :/
      "#{lhs} / #{rhs}"
    when :%
      "#{lhs} % #{rhs}"
    when :>>
      "#{lhs} >> #{rhs}"
    when :'>>>'
      "#{lhs}.sra(#{rhs})"
    when :<<
      "#{lhs} << #{rhs}"
    when :'`<<'
      "#{lhs}.widening_sll(#{rhs})"
    else
      raise "bad op: #{op}"
    end
  end

  def self.next_id
    @next_id ||= 0
    @next_id += 1
    "bits_#{@next_id}"
  end
end

raise unless Bits.new(-5, 8, signed: true).value == -5
raise unless Bits.new(-5, 8, signed: false).value == 0xfb

def width_to_suffix(width)
  if width <= 32
    "u"
  elsif width <= 64
    "llu"
  elsif width <= 128
    "_u128"
  else
    "_mpz"
  end
end

def relation(lhs, rhs)
  valid_relations = []
  valid_relations << "==" if lhs.value == rhs.value
  valid_relations << "!=" if lhs.value != rhs.value
  valid_relations << "<="  if lhs.value <= rhs.value
  valid_relations << ">="  if lhs.value >= rhs.value
  valid_relations << "<"  if lhs.value < rhs.value
  valid_relations << ">"  if lhs.value > rhs.value

  valid_relations[$prng.rand(valid_relations.size)]
end

def gen_binary_expr_testcase(op, lhs, rhs)
  expected = lhs.binary_expr(op, rhs)
  <<~TEST
    TEST_CASE("#{Bits.next_id}")
    {
      // #{lhs} #{op} #{rhs} = #{expected}
      {
        _Bits<#{lhs.width}, #{lhs.signed}> lhs{#{lhs.value}#{width_to_suffix(lhs.width)}};
        _Bits<#{rhs.width}, #{rhs.signed}> rhs{#{rhs.value}#{width_to_suffix(rhs.width)}};
        auto result = #{Bits.binary_expr_cpp(op, 'lhs', 'rhs')};
        auto expected = _Bits<#{expected.width}, #{expected.signed}>{#{expected.value}#{width_to_suffix(expected.width)}};
        REQUIRE(result == expected);
        REQUIRE(result.width() == expected.width());
        REQUIRE(lhs #{relation(lhs, rhs)} rhs);
        REQUIRE(rhs #{relation(rhs, lhs)} lhs);
        REQUIRE(lhs #{relation(lhs, expected)} result);
        REQUIRE(result #{relation(expected, lhs)} lhs);
        REQUIRE(rhs #{relation(rhs, expected)} result);
        REQUIRE(result #{relation(expected, rhs)} rhs);
      }
      {
        _RuntimeBits<#{lhs.width}, #{lhs.signed}> lhs{Bits<#{lhs.width}>{#{lhs.value}#{width_to_suffix(lhs.width)}}, Bits<32>{#{lhs.width}}};
        _RuntimeBits<#{rhs.width}, #{rhs.signed}> rhs{Bits<#{lhs.width}>{#{rhs.value}#{width_to_suffix(rhs.width)}}, Bits<32>{#{rhs.width}}};
        auto result = #{Bits.binary_expr_cpp(op, 'lhs', 'rhs')};
        auto expected = _Bits<#{expected.width}, #{expected.signed}>{#{expected.value}#{width_to_suffix(expected.width)}};
        REQUIRE(result == expected);
        REQUIRE(result.width() == expected.width());
        REQUIRE(lhs #{relation(lhs, rhs)} rhs);
        REQUIRE(rhs #{relation(rhs, lhs)} lhs);
        REQUIRE(lhs #{relation(lhs, expected)} result);
        REQUIRE(result #{relation(expected, lhs)} lhs);
        REQUIRE(rhs #{relation(rhs, expected)} result);
        REQUIRE(result #{relation(expected, rhs)} rhs);
      }
      {
        _PossiblyUnknownBits<#{lhs.width}, #{lhs.signed}> lhs{0x#{lhs.value.to_s(16)}_b};
        _PossiblyUnknownBits<#{rhs.width}, #{rhs.signed}> rhs{0x#{rhs.value.to_s(16)}_b};
        auto result = #{Bits.binary_expr_cpp(op, 'lhs', 'rhs')};
        auto expected = _Bits<#{expected.width}, #{expected.signed}>{#{expected.value}#{width_to_suffix(expected.width)}};
        REQUIRE(result == expected);
        REQUIRE(result.width() == expected.width());
        REQUIRE(lhs #{relation(lhs, rhs)} rhs);
        REQUIRE(rhs #{relation(rhs, lhs)} lhs);
        REQUIRE(lhs #{relation(lhs, expected)} result);
        REQUIRE(result #{relation(expected, lhs)} lhs);
        REQUIRE(rhs #{relation(rhs, expected)} result);
        REQUIRE(result #{relation(expected, rhs)} rhs);
      }
      {
        _PossiblyUnknownRuntimeBits<#{lhs.width}, #{lhs.signed}> lhs{0x#{lhs.value.to_s(16)}_b, Bits<32>{#{lhs.width}}};
        _PossiblyUnknownRuntimeBits<#{rhs.width}, #{rhs.signed}> rhs{0x#{rhs.value.to_s(16)}_b, Bits<32>{#{rhs.width}}};
        auto result = #{Bits.binary_expr_cpp(op, 'lhs', 'rhs')};
        auto expected = _Bits<#{expected.width}, #{expected.signed}>{#{expected.value}#{width_to_suffix(expected.width)}};
        REQUIRE(result == expected);
        REQUIRE(result.width() == expected.width());
        REQUIRE(lhs #{relation(lhs, rhs)} rhs);
        REQUIRE(rhs #{relation(rhs, lhs)} lhs);
        REQUIRE(lhs #{relation(lhs, expected)} result);
        REQUIRE(result #{relation(expected, lhs)} lhs);
        REQUIRE(rhs #{relation(rhs, expected)} result);
        REQUIRE(result #{relation(expected, rhs)} rhs);
      }
    }
  TEST
end




header = <<~HEADER
#include <fmt/core.h>

#include <catch2/catch_test_macros.hpp>
#include <catch2/generators/catch_generators.hpp>
#include <catch2/generators/catch_generators_adapters.hpp>
#include <catch2/generators/catch_generators_random.hpp>
#include <catch2/matchers/catch_matchers_string.hpp>
#include <iostream>
#include <udb/bits.hpp>
#include <udb/defines.hpp>

using Catch::Matchers::Equals;

consteval __uint128_t operator""_u128(const char *x) {
  __uint128_t y = 0;
  auto len = strlen(x);

  if (x[0] == '0' && (x[1] == 'x' || x[1] == 'X')) {
    for (int i = 2; x[i] != '\\0'; ++i) {
      if (x[i] == '\\'') {
        continue;
      }
      y *= 16ull;
      if ('0' <= x[i] && x[i] <= '9')
        y += x[i] - '0';
      else if ('A' <= x[i] && x[i] <= 'F')
        y += x[i] - 'A' + 10;
      else if ('a' <= x[i] && x[i] <= 'f')
        y += x[i] - 'a' + 10;
    }
  } else if (x[0] == '0' && (x[1] == 'o' || x[1] == 'O')) {
    for (int i = 2; x[i] != '\\0'; ++i) {
      if (x[i] == '\\'') {
        continue;
      }
      y *= 8ull;
      if ('0' <= x[i] && x[i] <= '7') y += x[i] - '0';
    }
  } else if (x[0] == '0' && (x[1] == 'b' || x[1] == 'B')) {
    for (int i = 2; x[i] != '\\0'; ++i) {
      if (x[i] == '\\'') {
        continue;
      }
      y *= 2ull;
      if ('0' <= x[i] && x[i] <= '1') y += x[i] - '0';
    }
  } else {
    __uint128_t pow = 1;
    for (int i = len - 1; i >= '\\0'; i--) {
      if (x[i] == '\\'') {
        continue;
      }
      if ('0' <= x[i] && x[i] <= '9') y += ((unsigned __int128)(x[i] - '0')) * pow;
      else throw std::runtime_error("bad literal");
      pow *= 10;
    }
  }
  return y;
}

std::ostream &operator<<(std::ostream &stream, const __uint128_t &val) {
  stream << fmt::format("0x{:x}", val);
  return stream;
}

std::ostream &operator<<(std::ostream &stream, const __int128_t &val) {
  stream << fmt::format("0x{:x}", val);
  return stream;
}

using namespace udb;
HEADER


[1, 8, 16, 32, 64, 128].each_with_index do |n, idx|
  puts idx
  $output[idx].puts header
   # binary ops
   Bits::BINARY_ARITH_OPS.each do |op|
    [10, 2**n].min.times do |i|
      lhs = Bits.new($prng.rand(2**n), n)
      if [:>>, :'>>>', :<<, :'`<<'].include?(op)
        rhs = Bits.new($prng.rand(2*n), n)
      else
        rhs = Bits.new($prng.rand(2**n), n)
      end

      if [:>>, :'>>>', :<<, :'`<<'].include?(op)
        raise if rhs.value > (2*n)
      end

      next if [:/, :%].include?(op) && rhs.value == 0

      $output[idx].puts gen_binary_expr_testcase(op, lhs, rhs)
    end
   end
end
