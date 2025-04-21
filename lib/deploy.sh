#!/usr/bin/env bash

# deploy artifacts to a directory, in preparation for GitHub deployment

echo "DEPLOY: Starting"

ROOT=$(dirname $(dirname $(realpath ${BASH_SOURCE[0]})))

DEPLOY_DIR="$ROOT/_site"
PAGES_URL="https://riscv-software-src.github.io/riscv-unified-db"

mkdir -p $DEPLOY_DIR

echo "DEPLOY: Create _site/example_cfg"
mkdir -p $DEPLOY_DIR/example_cfg

echo "DEPLOY: Create _site/manual"
mkdir -p $DEPLOY_DIR/manual

echo "DEPLOY: Create _site/pdfs"
mkdir -p $DEPLOY_DIR/pdfs

echo "DEPLOY: Create _site/htmls"
mkdir mkdir -p $DEPLOY_DIR/htmls

echo "DEPLOY: Resolve / Create Index"
./do gen:resolved_arch
cp -R gen/resolved_arch/_ $DEPLOY_DIR/resolved_arch

echo "DEPLOY: Create _site/isa_explorer"
mkdir -p $DEPLOY_DIR/isa_explorer
echo "DEPLOY: Create isa_explorer_browser_ext"
./do gen:isa_explorer_browser_ext
echo "DEPLOY: Create isa_explorer_browser_inst"
./do gen:isa_explorer_browser_inst
echo "DEPLOY: Create isa_explorer_browser_csr"
./do gen:isa_explorer_browser_csr
echo "DEPLOY: Copy isa_explorer_browser"
cp -R gen/isa_explorer/browser $DEPLOY_DIR/isa_explorer
echo "DEPLOY: Create isa_explorer_spreadsheet"
./do gen:isa_explorer_spreadsheet
echo "DEPLOY: Copy isa_explorer_spreadsheet"
cp -R gen/isa_explorer/spreadsheet $DEPLOY_DIR/isa_explorer

echo "DEPLOY: Build manual"
./do gen:html_manual MANUAL_NAME=isa VERSIONS=all
echo "DEPLOY: Copy manual html"
cp -R gen/manual/isa/top/all/html $DEPLOY_DIR/manual
echo "DEPLOY: Build html documentation for example_rv64_with_overlay"
./do gen:html[example_rv64_with_overlay]

# Filling up my root dir with a "doc" directory when I run this script.
#echo "DEPLOY: Generate YARD docs"
#./do gen:tool_doc

echo "DEPLOY: Copy cfg html"
cp -R gen/cfg_html_doc/example_rv64_with_overlay/html $DEPLOY_DIR/example_cfg

for profile in RVI20 RVA20 RVA22 RVA23 RVB23; do
  echo "DEPLOY: Create $profile Profile Release PDF Spec"
  ./do gen:profile_release_pdf[$profile]
  echo "DEPLOY: Copy $profile Profile Release PDF Spec"
  cp gen/profile/pdf/${profile}ProfileRelease.pdf $DEPLOY_DIR/pdfs
done

for crd in AC100 AC200 MC100-32 MC100-64 MC200-32 MC200-64 MC300-32 MC300-64; do
  echo "DEPLOY: Create $profile Profile Release PDF Spec"
  ./do gen:profile_release_pdf[$profile]
  echo "DEPLOY: Copy $profile Profile Release PDF Spec"
  cp gen/profile/pdf/${profile}ProfileRelease.pdf $DEPLOY_DIR/pdfs

  echo "DEPLOY: Create ${crd}-CRD PDF Spec"
  ./do gen:proc_crd_pdf[$crd]
  echo "DEPLOY: Copy ${crd}-CRD PDF"
  cp gen/proc_crd/pdf/${crd}-CRD.pdf $DEPLOY_DIR/pdfs
done

for ctp in MC100-32 MockProcessor; do
  echo "DEPLOY: Create ${ctp}-CTP PDF Spec"
  ./do gen:proc_ctp_pdf[$ctp]
  echo "DEPLOY: Copy ${ctp}-CTP PDF"
  cp gen/proc_ctp/pdf/${ctp}-CTP.pdf $DEPLOY_DIR/pdfs
done

echo "DEPLOY: Create index"
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
    <h3>RISC-V ISA Explorer</h3>
    Candidate replacement for <a href="https://docs.google.com/spreadsheets/d/1A40dfm0nnn2-tgKIhdi3UYQ1GBr8iRiV2edFowvgp7E/edit?gid=1157775000">Profiles & Bases & Extensions Google Sheet</a>
    using data in riscv-unified-db.
    <ul>
      <li><a href="$PAGES_URL/isa_explorer/browser/ext_table.html">Extensions</a></li>
      <li><a href="$PAGES_URL/isa_explorer/browser/inst_table.html">Instructions</a></li>
      <li><a href="$PAGES_URL/isa_explorer/browser/csr_table.html">CSRs</a></li>
      <li><a href="$PAGES_URL/isa_explorer.xlsx">Excel version (includes Extensions, Instructions, CSRs)</a></li>
    </ul>

    <br/>
    <h3>Profile Releases</h3>
    <ul>
      <li><a href="$PAGES_URL/pdfs/RVI20.pdf">RVI20 Profile Release</a></li>
      <li><a href="$PAGES_URL/pdfs/RVA20.pdf">RVA20 Profile Release</a></li>
      <li><a href="$PAGES_URL/pdfs/RVA22.pdf">RVA22 Profile Release</a></li>
      <li><a href="$PAGES_URL/pdfs/RVA23.pdf">RVA23 Profile Release</a></li>
      <li><a href="$PAGES_URL/pdfs/RVB23.pdf">RVB23 Profile Release</a></li>
    </ul>

    <br/>
    <h3>CSC CRDs (Certification Requirements Documents)</h3>
    <ul>
      <li><a href="$PAGES_URL/pdfs/AC100-CRD.pdf">AC100 CRD (based on RVB23)</a></li>
      <li><a href="$PAGES_URL/pdfs/AC200-CRD.pdf">AC200 CRD (based on RVA23)</a></li>
      <li><a href="$PAGES_URL/pdfs/MC100-32-CRD.pdf">MC100-32 CRD</a></li>
      <li><a href="$PAGES_URL/pdfs/MC100-64-CRD.pdf">MC100-64 CRD</a></li>
      <li><a href="$PAGES_URL/pdfs/MC200-32-CRD.pdf">MC200-32 CRD</a></li>
      <li><a href="$PAGES_URL/pdfs/MC200-64-CRD.pdf">MC200-64 CRD</a></li>
      <li><a href="$PAGES_URL/pdfs/MC300-32-CRD.pdf">MC300-32 CRD</a></li>
      <li><a href="$PAGES_URL/pdfs/MC300-64-CRD.pdf">MC300-64 CRD</a></li>
    </ul>

    <br/>
    <h3>CSC CTPs (Certification Test Plans)</h3>
    <ul>
      <li><a href="$PAGES_URL/pdfs/MC100-32-CTP.pdf">MC100-32 CTP</a></li>
      <li><a href="$PAGES_URL/pdfs/MockProcessor-CTP.pdf">MockProcessor CTP (for UDB testing)</a></li>
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

echo "DEPLOY: Complete"
