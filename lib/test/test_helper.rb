require 'simplecov'

SimpleCov.start do
  add_filter '/test/'
  add_group 'Arch Models', 'arch_obj_models'
  add_group 'IDL', 'idl'
end

require 'minitest/autorun'
