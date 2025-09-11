# frozen_string_literal: true

namespace :chore do
  desc "Update the golden instruction appendix file"
  task :update_golden_appendix do
    # First generate the instruction appendix
    Rake::Task["gen:instruction_appendix_adoc"].invoke
    
    # Define file paths
    output_file = "gen/instructions_appendix/all_instructions.adoc"
    golden_file = "backends/instructions_appendix/all_instructions.golden.adoc"
    
    # Check if the output file exists
    unless File.exist?(output_file)
      puts "ERROR: Generated file not found at #{output_file}"
      exit 1
    end
    
    # Copy the output file to the golden file
    FileUtils.mkdir_p(File.dirname(golden_file))
    FileUtils.cp(output_file, golden_file)
    
    puts "SUCCESS: Updated golden file #{golden_file} from #{output_file}"
  end
end
