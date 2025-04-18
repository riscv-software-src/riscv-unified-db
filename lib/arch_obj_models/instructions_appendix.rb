# frozen_string_literal: true

require_relative "database_obj"  # Adjust this require if your obj.rb is in the same folder.

# The InstructionIndex class aggregates instructions from the architecture.
# It merges instructions available directly from the architecture (if any)
# with those from each extension.
class InstructionIndex
  def initialize(cfg_arch)
    @cfg_arch = cfg_arch
  end

  def instructions
    @instructions ||= begin
      merged = []
      # If the architecture responds to :instructions, add them.
      if @cfg_arch.respond_to?(:instructions)
        merged.concat(@cfg_arch.instructions)
      end
      # Also, add instructions from each extension.
      if @cfg_arch.respond_to?(:extensions)
        @cfg_arch.extensions.each do |ext|
          ext_obj = @cfg_arch.extension(ext.name)
          if ext_obj && ext_obj.respond_to?(:instructions)
            merged.concat(ext_obj.instructions)
          end
        end
      end
      merged.uniq { |inst| inst.name }.sort_by { |inst| inst.name }
    end
  end

  def find_instruction(name)
    instructions.find { |inst| inst.name == name }
  end
end
