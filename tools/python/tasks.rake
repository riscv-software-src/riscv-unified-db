# Copyright (c) Ventana Micro Systems
# SPDX-License-Identifier: BSD-3-Clause-Clear

namespace :chore do

  desc "Update golden profile_extensions output"
  task :update_golden_profile_extensions do
    Rake::Task["gen:resolved_arch"].invoke
    sh "#{$root}/tools/python/profile_extensions.py #{$root}/gen/resolved_spec/_ > #{$root}/tools/python/profile_extensions.golden"
  end

end

namespace :test do

  desc "Test that generated profile_extensions matched golden version"
  task :profile_extensions do
    Rake::Task["gen:resolved_arch"].invoke

    $logger.info "Testing profile_extensions"
    sh "#{$root}/tools/python/profile_extensions.py #{$root}/gen/resolved_spec/_ > test-profile_extensions.txt"
    sh "diff -u #{$root}/tools/python/profile_extensions.golden test-profile_extensions.txt" do |ok, res|

      rm "test-profile_extensions.txt", :force => true, :verbose => false
      if ok
        puts "PASSED"
      else
        warn <<~MSG

          The list of extensions associated with profiles has changed.

          If this is expected, run:
          ./do chore:update_golden_profile_extensions
          git add tools/python/profile_extensions.golden

          And commit.
        MSG
        exit 1
      end
    end
  end
end
