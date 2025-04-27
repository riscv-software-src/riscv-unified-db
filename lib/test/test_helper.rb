require 'simplecov'

SimpleCov.start do
  enable_coverage :branch

  add_group 'Arch Obj Models', 'arch_obj_models'
  add_group 'IDL Core', 'idl'
  add_group 'IDL Regression Tests', 'idl/tests'
  add_group 'Top-level Tests', 'test'
end

puts "[SimpleCov] Coverage started."

require 'minitest/autorun'
