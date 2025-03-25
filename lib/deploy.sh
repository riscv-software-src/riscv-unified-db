#!/bin/bash

# deploy artifacts to a directory, in preparation for GitHub deployment

ROOT=$(dirname $(dirname $(realpath $BASH_SOURCE[0])))

DEPLOY_DIR="$ROOT/_site"
PAGES_URL="https://riscv-software-src.github.io/riscv-unified-db"

mkdir -p $DEPLOY_DIR

echo "Create _site/example_cfg"
mkdir -p $DEPLOY_DIR/example_cfg

echo "Create _site/manual"
mkdir -p $DEPLOY_DIR/manual

echo "Create _site/pdfs"
mkdir -p $DEPLOY_DIR/pdfs



echo "Resolve / Create Index"
./do gen:resolved_arch

echo "Build manual"
./do gen:html_manual MANUAL_NAME=isa VERSIONS=all

echo "Copy manual html"
cp -R gen/manual/isa/top/all/html $DEPLOY_DIR/manual

echo "Build html documentation for example_rv64_with_overlay"
./do gen:html[example_rv64_with_overlay]

echo "Generate YARD docs"
./do gen:tool_doc

echo "Create _site/htmls"
mkdir mkdir -p $DEPLOY_DIR/htmls

echo "Copy cfg html"
cp -R gen/cfg_html_doc/example_rv64_with_overlay/html $DEPLOY_DIR/example_cfg

echo "Create RVA20 Profile Release PDF Spec"
./do gen:profile[RVA20]

echo "Copy RVA20 Profile Release PDF"
cp gen/profile_doc/pdf/RVA20.pdf $DEPLOY_DIR/pdfs/RVA20.pdf

echo "Create RVA22 Profile Release PDF Spec"
./do gen:profile[RVA22]

echo "Copy RVA22 Profile Release PDF"
cp gen/profile_doc/pdf/RVA22.pdf $DEPLOY_DIR/pdfs/RVA22.pdf

echo "Create RVI20 Profile Release PDF Spec"
./do gen:profile[RVI20]

echo "Copy RVI20 Profile Release PDF"
cp gen/profile_doc/pdf/RVA20.pdf $DEPLOY_DIR/pdfs/RVI20.pdf

echo "Create MC100-32 PDF Spec"
./do gen:cert_model_pdf[MC100-32]

echo "Copy MC100-32 PDF"
cp gen/certificate_doc/pdf/MC100-32.pdf $DEPLOY_DIR/pdfs/MC100-32.pdf

echo "Create MC100-32 HTML Spec"
./do gen:cert_model_html[MC100-32]

echo "Copy MC100-32 HTML"
cp gen/certificate_doc/html/MC100-32.html $DEPLOY_DIR/htmls/MC100-32.html

echo "Create MC100-64 PDF Spec"
./do gen:cert_model_pdf[MC100-64]

echo "Copy MC100-64 PDF"
cp gen/certificate_doc/pdf/MC100-64.pdf $DEPLOY_DIR/pdfs/MC100-64.pdf

echo "Create MC100-64 HTML Spec"
./do gen:cert_model_html[MC100-64]

echo "Copy MC100-64 HTML"
cp gen/certificate_doc/html/MC100-64.html $DEPLOY_DIR/htmls/MC100-64.html

echo "Create index"
cat <<- EOF > $DEPLOY_DIR/index.html
<!doctype html>
<html lang="en-us">
  <head>
    <title>Release artifacts for $GITHUB_REF_NAME</title>
  </head>
  <body>
    <h1>Release artifacts for <code>riscv-unified-db</code>, ref $GITHUB_REF_NAME</h1>
    <h2>Commit $GITHUB_SHA</h2>
    <p>Created on $(date)</p>

    <br/>
    <h3>Resolved architecture</h3>
    <ul>
      <li><a href="$PAGES_URL/resolved_arch/index.yaml">index.yaml</a> Database index, as array of relative paths from $PAGES_URL/resolved_arch</li>
    </ul>

    <br/>
    <h3>ISA Manual</h3>
    <ul>
      <li><a href="$PAGES_URL/manual/html/index.html">Generated HTML ISA manuals, all versions</a></li>
    </ul>

    <br/>
    <h3>Profiles</h3>
    <ul>
      <li><a href="$PAGES_URL/pdfs/RVI20.pdf">RVI20</a></li>
      <li><a href="$PAGES_URL/pdfs/RVA20.pdf">RVA20</a></li>
      <li><a href="$PAGES_URL/pdfs/RVA22.pdf">RVA22</a></li>
    </ul>

    <br/>
    <h3>Certification Requirements Documents</h3>
    <ul>
      <li><a href="$PAGES_URL/pdfs/MC100-32.pdf">MC100-32</a></li>
      <li><a href="$PAGES_URL/pdfs/MC100-64.pdf">MC100-64</a></li>
    </ul>

    <br/>
    <h3>Configuration-specific documentation</h3>
    <ul>
      <li><a href="$PAGES_URL/example_cfg/html/index.html">Architecture documentation for example RV64 config</a></li>
    </ul>

    <br/>
    <h3>UDB Tool Documentation</h3>
    <ul>
      <li><a href="$PAGES_URL/ruby/idl/index.html">IDL language documentation</a></li>
      <li><a href="$PAGES_URL/ruby/arch_def/index.html">Ruby UDB interface documentation</a></li>
    </ul>
  </body>
</html>
EOF
