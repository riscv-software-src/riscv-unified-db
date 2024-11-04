
require "pathname"

namespace :gen do
  desc "Generate index of the database"
  task :index do
    index_path = Pathname.new("#{$root}/gen/indexer/index-unified.json")
    Dir.chdir "#{$root}/backends/indexer" do
      FileUtils.mkdir_p index_path.dirname
      File.write index_path, `node index-unifieddb.js #{$root}`
    end
  end
end
