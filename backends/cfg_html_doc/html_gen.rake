# typed: false
# frozen_string_literal: true

# fill out templates for every csr, inst, ext, and func
["csr", "inst", "ext", "func"].each do |type|
  rule %r{#{$root}/gen/cfg_html_doc/.*/antora/modules/#{type}s/pages/.*\.adoc} => proc { |tname|
    config_name = Pathname.new(tname).relative_path_from("#{$root}/gen/cfg_html_doc").to_s.split("/")[0]
    [
      "#{$root}/\.stamps/adoc-gen-#{type}s-#{config_name}\.stamp",
      __FILE__
    ]
  } do |t|
    config_name = Pathname.new(t.name).relative_path_from("#{$root}/gen/cfg_html_doc").to_s.split("/")[0]
    rest = Pathname.new(t.name).relative_path_from("#{$root}/gen/cfg_html_doc/#{config_name}/antora/modules/#{type}s/pages")
    FileUtils.mkdir_p File.dirname(t.name)
    src = $root / "gen" / "cfg_html_doc" / config_name / "adoc" / "#{type}s" / rest
    File.write t.name, Udb::Helpers::AntoraUtils.resolve_links(src)
  end
end

rule %r{#{$root}/gen/cfg_html_doc/.*/antora/modules/nav.adoc} => proc { |tname|
  config_name = Pathname.new(tname).relative_path_from("#{$root}/gen/cfg_html_doc").to_s.split("/")[0]
  Dir.glob("#{$root}/gen/cfg_html_doc/#{config_name}/antora/modules/csrs/**/*.adoc") +
    Dir.glob("#{$root}/gen/cfg_html_doc/#{config_name}/antora/modules/insts/**/*.adoc") +
    Dir.glob("#{$root}/gen/cfg_html_doc/#{config_name}/antora/modules/exts/**/*.adoc") +
    [
      "#{CFG_HTML_DOC_DIR}/templates/toc.adoc.erb",
      __FILE__
    ]
} do |t|
  config_name = Pathname.new(t.name).relative_path_from("#{$root}/gen/cfg_html_doc").to_s.split("/")[0]

  toc_path = CFG_HTML_DOC_DIR / "templates" / "toc.adoc.erb"
  erb = ERB.new(toc_path.read, trim_mode: "-")
  erb.filename = toc_path.to_s

  cfg_arch = $resolver.cfg_arch_for(config_name)
  File.write t.name, Udb::Helpers::AntoraUtils.resolve_links(erb.result(binding))
end

rule %r{#{$root}/gen/cfg_html_doc/.*/antora/modules/ROOT/pages/config.adoc} => proc { |tname|
  config_name = Pathname.new(tname).relative_path_from("#{$root}/gen/cfg_html_doc").to_s.split("/")[0]
  [
    "#{CFG_HTML_DOC_DIR}/templates/config.adoc.erb",
    __FILE__
  ]
} do |t|
  config_name = Pathname.new(t.name).relative_path_from("#{$root}/gen/cfg_html_doc").to_s.split("/")[0]

  config_path = CFG_HTML_DOC_DIR / "templates" / "config.adoc.erb"
  erb = ERB.new(config_path.read, trim_mode: "-")
  erb.filename = config_path.to_s

  cfg_arch = $resolver.cfg_arch_for(config_name)
  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, Udb::Helpers::AntoraUtils.resolve_links(cfg_arch.convert_monospace_to_links(erb.result(binding)))
end

rule %r{#{$root}/gen/cfg_html_doc/.*/antora/modules/ROOT/pages/landing.adoc} => proc { |tname|
  config_name = Pathname.new(tname).relative_path_from("#{$root}/gen/cfg_html_doc").to_s.split("/")[0]
  [
    "#{$root}/gen/cfg_html_doc/#{config_name}/adoc/ROOT/landing.adoc",
    __FILE__
  ]
} do |t|
  config_name = Pathname.new(t.name).relative_path_from("#{$root}/gen/cfg_html_doc").to_s.split("/")[0]
  cfg_arch = $resolver.cfg_arch_for(config_name)

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, Udb::Helpers::AntoraUtils.resolve_links(cfg_arch.convert_monospace_to_links(File.read(t.prerequisites[0])))
end

rule %r{#{$root}/gen/cfg_html_doc/.*/antora/antora.yml} => proc { |tname|
  config_name = Pathname.new(tname).relative_path_from("#{$root}/gen/cfg_html_doc").to_s.split("/")[0]
  [
    "#{$root}/gen/cfg_html_doc/#{config_name}/antora/modules/nav.adoc",
    __FILE__
  ]
} do |t|
  config_name = Pathname.new(t.name).relative_path_from("#{$root}/gen/cfg_html_doc").to_s.split("/")[0]
  File.write t.name, <<~ANTORA_YML
    name: #{config_name}
    version: ~
    nav:
    - modules/nav.adoc
  ANTORA_YML
end

rule %r{#{$root}/gen/cfg_html_doc/.*/antora/playbook.yaml} => proc { |tname|
  config_name = Pathname.new(tname).relative_path_from("#{$root}/gen/cfg_html_doc").to_s.split("/")[0]
  [
    "#{$root}/gen/cfg_html_doc/#{config_name}/antora/antora.yml",
    __FILE__
  ]
} do |t|
  config_name = Pathname.new(t.name).relative_path_from("#{$root}/gen/cfg_html_doc").to_s.split("/")[0]

  File.write t.name, <<~PLAYBOOK
    site:
      title: RISC-V Specification for #{config_name}
      start_page: #{config_name}:ROOT:landing.adoc
    content:
      sources:
      - url: #{$root}
        start_path: gen/cfg_html_doc/#{config_name}/antora
    antora:
      extensions:
      - '@antora/lunr-extension'
    asciidoc:
      extensions:
      - 'asciidoctor-kroki'
      - '@asciidoctor/tabs'
      - 'asciidoctor-mathjax'   # auto-handles raw TeX delimiters
      attributes:
        stem: latexmath
    ui:
      bundle:
        url: https://gitlab.com/antora/antora-ui-default/-/jobs/artifacts/HEAD/raw/build/ui-bundle.zip?job=bundle-stable
        snapshot: true
      supplemental_files:
      - path: css/vendor/tabs.css
        contents: #{$root}/node_modules/@asciidoctor/tabs/dist/css/tabs.css
      - path: js/vendor/tabs.js
        contents: #{$root}/node_modules/@asciidoctor/tabs/dist/js/tabs.js
      - path: partials/footer-scripts.hbs
        contents: |
          <script id="site-script" src="{{{uiRootPath}}}/js/site.js" data-ui-root-path="{{{uiRootPath}}}"></script>
          <script async src="{{{uiRootPath}}}/js/vendor/highlight.js"></script>
          <script async src="{{{uiRootPath}}}/js/vendor/tabs.js"></script>
          {{#if env.SITE_SEARCH_PROVIDER}}
          {{> search-scripts}}
          {{/if}}
      - path: partials/head-styles.hbs
        contents: |
          <link rel="stylesheet" href="{{{uiRootPath}}}/css/site.css">
          <link rel="stylesheet" href="{{{uiRootPath}}}/css/vendor/tabs.css">
          <link rel="stylesheet" href="{{{uiRootPath}}}/css/vendor/custom.css">
      - path: js/vendor/highlight.js
        contents: #{$root}/backends/cfg_html_doc/ui/highlight.js
      - path: css/vendor/custom.css
        contents: |
          .small {
            font-size: 50%;
            font-weight: normal;
          }

          code.language-idl > a {
            text-decoration: none;
          }

          /* rotate text vertically */
          span.rotate {
            writing-mode: vertical-lr;
          }

          span.access-always {
            background-color: green;
            display: block;
            padding: 16px;
            border-radius: 8px;
            text-align: center;
            color: white;
            font-weight: bold;
          }

          span.access-sometimes {
            background-color: rgb(255, 193, 7);
            display: block;
            padding: 16px;
            border-radius: 8px;
            text-align: center;
            color: black;
            font-weight: bold;
          }

          span.access-never {
            background-color: #e71324;
            display: block;
            padding: 16px;
            border-radius: 8px;
            text-align: center;
            color: white;
            font-weight: bold;
          }

          .csr-field-info {
            margin-left: 1em;
            padding: 1em;
            border-radius: 25px;
            border: 2px solid;
          }
  PLAYBOOK
end

rule %r{#{$root}/\.stamps/html-gen-prose-.*\.stamp} => FileList[$root / "spec" / "std" / "isa" / "prose" / "**" / "*"] do |t|
  config_name = Pathname.new(t.name).basename(".stamp").sub("html-gen-prose-", "")
  FileUtils.rm_rf $root / "gen" / "cfg_html_doc" / config_name / "antora" / "modules" / "prose"
  FileUtils.mkdir_p $root / "gen" / "cfg_html_doc" / config_name / "antora" / "modules" / "prose"
  FileUtils.cp_r $root / "spec" / "std" / "isa" / "prose", $root / "gen" / "cfg_html_doc" / config_name / "antora" / "modules" / "prose" / "pages"

  Rake::Task["#{$root}/.stamps"].invoke

  FileUtils.touch t.name
end

rule %r{#{$root}/\.stamps/html-gen-.*\.stamp} => proc { |tname|
  config_name = Pathname.new(tname).basename(".stamp").sub("html-gen-", "")
  [
    "#{$root}/.stamps/adoc-gen-insts-#{config_name}.stamp",
    "#{$root}/.stamps/adoc-gen-csrs-#{config_name}.stamp",
    "#{$root}/.stamps/adoc-gen-exts-#{config_name}.stamp",
    "#{$root}/.stamps/adoc-gen-funcs-#{config_name}.stamp",
    "#{$root}/.stamps/html-gen-prose-#{config_name}.stamp",
    "#{$root}/gen/cfg_html_doc/#{config_name}/antora/modules/ROOT/pages/config.adoc",
    "#{$root}/gen/cfg_html_doc/#{config_name}/antora/modules/ROOT/pages/landing.adoc",
    __FILE__,
    "#{$root}/.stamps"
  ]
} do |t|
  config_name = Pathname.new(t.name).basename(".stamp").sub("html-gen-", "")

  ["csr", "inst", "ext", "func"].each do |type|
    Dir.glob("#{$root}/gen/cfg_html_doc/#{config_name}/adoc/#{type}s/**/*.adoc") do |f|
      rest = Pathname.new(f).relative_path_from("#{$root}/gen/cfg_html_doc/#{config_name}/adoc/#{type}s")
      dest_path =
        $root / "gen" / "cfg_html_doc" / config_name / "antora" / "modules" / "#{type}s" / "pages" / rest

      Rake::Task[dest_path.to_s].invoke
    end
  end

  Rake::Task[$root / "gen" / "cfg_html_doc" / config_name / "antora" / "modules" / "nav.adoc"].invoke
  Rake::Task[$root / "gen" / "cfg_html_doc" / config_name / "antora" / "modules" / "ROOT" / "pages" / "config.adoc"].invoke
  playbook_path = $root / "gen" / "cfg_html_doc" / config_name / "antora" / "playbook.yaml"
  Rake::Task[playbook_path].invoke

  $logger.info "Running Antora under npm to create #{config_name}"

  sh [
    "npm exec -- antora",
    "--stacktrace",
    "generate",
    "--cache-dir=#{$root}/.home/.antora",
    "--to-dir=#{$root}/gen/cfg_html_doc/#{config_name}/html",
    "--log-level=all",
    "--fetch",
    playbook_path
  ].join(" ")

  $logger.info "Done running Antora under npm to create #{config_name}"

  FileUtils.touch t.name
end

namespace :gen do
  desc <<~DESC
    Generate HTML documentation for config(s).

    Multiple configs may be specified as a comman-separated list.
    Note, the list cannot contain spaces.
  DESC
  task :html, [:config_name] => "gen:adoc" do |_t, args|
    configs = [args[:config_name]]
    configs += args.extras unless args.extras.empty?

    configs.each do |config|
      Rake::Task[($root / ".stamps" / "html-gen-#{config}.stamp")].invoke
    end
  end
end

namespace :serve do
  desc <<~DESC
    Start an HTML server to view the generated HTML documentation for config_name

    The default port is 8000, though it can be overridden with an argument
  DESC
  task :html, [:config_name, :port] do |_t, args|
    raise ArgumentError, "Missing required argument :config_name" if args[:config_name].nil?

    Rake::Task["gen:html"].invoke(args[:config_name])
    args.with_defaults(port: 8000)

    html_dir = $root / "gen" / "cfg_html_doc" / args[:config_name] / "html"
    Dir.chdir(html_dir) do
      require "webrick"

      server = WEBrick::HTTPServer.new Port: args[:port].to_i, DocumentRoot: html_dir.to_s
      trap("INT") { server.shutdown }
      puts "\n\nView server at http://#{`hostname`.strip}:#{args[:port]}\n\n"
      server.start
    end
  end
end
