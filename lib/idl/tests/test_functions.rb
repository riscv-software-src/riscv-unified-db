require "minitest/autorun"

$root ||= (Pathname.new(__FILE__) / ".." / ".." / ".." / "..").realpath

require_relative "../../idl"
require_relative "../passes/reachable_exceptions"
require_relative "helpers"

# test IDL variables
class TestVariables < Minitest::Test
  include TestMixin

  def test_that_reachable_raise_analysis_respects_transitive_known_values
    idl = <<~IDL.strip
      %version: 1.0
      enum Choice {
        A 0
        B 1
      }

      enum ExceptionCode {
        ACode 0
        BCode 1
      }

      builtin function raise {
        arguments ExceptionCode code
        description { raise an exception}
      }

      function nested_choose {
        arguments Choice choice
        description {
          Chooses A or B
        }
        body {
          if (choice == Choice::A) {
            raise(ExceptionCode::ACode);
          } else {
            raise(ExceptionCode::BCode);
          }
        }
      }

      function choose {
        arguments Choice choice
        description {
          Chooses A or B
        }
        body {
          nested_choose(choice);
        }
      }

      function test {
        description {
          run the test
        }
        body {
          choose(Choice::B);
        }
      }

    IDL

    t = Tempfile.new("idl")
    t.write idl
    t.close

    path = Pathname.new(t.path)

    ast = @compiler.compile_file(path)
    ast.add_global_symbols(@symtab)
    @symtab.deep_freeze
    @archdef.global_ast = ast
    ast.freeze_tree(@symtab)

    test_ast = ast.functions.select { |f| f.name == "test" }[0]

    # should return (1 << BCode), also known as 2
    assert_equal (1 << 1), test_ast.body.prune(@symtab.deep_clone).reachable_exceptions(@symtab.deep_clone)
  end

  def test_that_reachable_raise_analysis_respects_known_paths_down_an_unknown_path
    idl = <<~IDL.strip
      %version: 1.0
      enum Choice {
        A 0
        B 1
      }

      enum ExceptionCode {
        ACode 0
        BCode 1
      }

      Bits<64> unknown;

      builtin function raise {
        arguments ExceptionCode code
        description { raise and exception}
      }

      function choose {
        arguments Choice choice
        description {
          Chooses A or B
        }
        body {
          if (unknown == 1) {
            if (choice == Choice::A) {
              raise(ExceptionCode::ACode);
            } else {
              raise(ExceptionCode::BCode);
            }
          }
        }
      }

      function test {
        description {
          run the test
        }
        body {
          choose(Choice::B);
        }
      }

    IDL

    t = Tempfile.new("idl")
    t.write idl
    t.close

    path = Pathname.new(t.path)

    ast = @compiler.compile_file(path)
    ast.add_global_symbols(@symtab)
    @symtab.deep_freeze
    @archdef.global_ast = ast
    ast.freeze_tree(@symtab)

    test_ast = ast.functions.select { |f| f.name == "test" }[0]
    pruned_test_ast = test_ast.body.prune(@symtab.deep_clone)
    assert_equal (1 << 1), pruned_test_ast.reachable_exceptions(@symtab.deep_clone)
  end
end
