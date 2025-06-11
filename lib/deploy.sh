#!/usr/bin/env bash

# deploy artifacts to a directory, in preparation for GitHub deployment

# Initialize globals used to track failures.
exit_status=0
declare -a failures # Array

ROOT=$(dirname $(dirname $(realpath ${BASH_SOURCE[0]})))

DEPLOY_DIR="$ROOT/_site"
PAGES_URL="https://riscv-software-src.github.io/riscv-unified-db"

function deploy_log() {
  echo "[DEPLOY] $(date) $*"
}

# Put "FAIL" between [DEPLOY] and date to make it easier to grep for failures (ie.., "\[DEPLOY\] FAIL" RE does the trick)
# Don't put "FAIL" in [DEPLOY] so that we can first grep for [DEPLOY] and see all messages from this deploy.sh script.
# Record failures but don't exit so that we can see which artifacts pass & fail.
function deploy_fail() {
  echo "[DEPLOY] FAIL $(date) $*"
  failures+=("$*")    # Append to array
  exit_status=1
}

function deploy_mkdir() {
  [[ $# -ne 1 ]] && {
    deploy_fail "deploy_mkdir(): Passed $# args but it needs 1"

    # Exit if args are wrong.
    exit 1
  }

  local dst_dir="$1"
  mkdir -p $dst_dir || {
    deploy_fail "mkdir -p $dst_dir failed"
  }
}

function deploy_do() {
  deploy_log
  deploy_log 'vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv'
  deploy_log "./do $*"
  deploy_log '^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^'
  deploy_log
  ./do "$@" || {
    deploy_fail "./do $*"
  }
}

function deploy_cp_recursive() {
  [[ $# -ne 2 ]] && {
    deploy_fail "deploy_cp_recursive(): Passed $# args but it needs 2"

    # Exit if args are wrong.
    exit 1
  }

  local src_dir="$1"
  local dst_dir="$2"

  cp -R ${src_dir} ${dst_dir} || {
    deploy_fail "cp -R ${src_dir} ${dst_dir} failed"
  }
}

function deploy_cp() {
  [[ $# -ne 2 ]] && {
    deploy_fail "deploy_cp(): Passed $# args but it needs 2"

    # Exit if args are wrong.
    exit 1
  }

  local src_file="$1"
  local dst_dir="$2"

  cp ${src_file} ${dst_dir} || {
    deploy_fail "cp ${src_file} ${dst_dir} failed"
  }
}

deploy_log '***************************************************************'
deploy_log '*                      DEPLOY STARTING                        *'
deploy_log '***************************************************************'

deploy_mkdir $DEPLOY_DIR
deploy_mkdir $DEPLOY_DIR/example_cfg
deploy_mkdir $DEPLOY_DIR/manual
deploy_mkdir $DEPLOY_DIR/pdfs
deploy_mkdir $DEPLOY_DIR/htmls

deploy_log "Resolve / Create Index for base architecture"
deploy_do "gen:resolved_arch"
tar czf $DEPLOY_DIR/resolved_arch.tar.gz gen/resolved_arch/_
deploy_cp_recursive gen/resolved_arch/_ $DEPLOY_DIR/resolved_arch

deploy_log "Create _site/isa_explorer"
deploy_mkdir $DEPLOY_DIR/isa_explorer
deploy_log "Create isa_explorer_browser_ext"
deploy_log "Create isa_explorer_browser_inst"
deploy_log "Create isa_explorer_browser_csr"

parallel :::                                          \
  "./do gen:udb:api_doc"                              \
  "./do gen:isa_explorer_browser_csr"                 \
  "./do gen:isa_explorer_browser_ext"                 \
  "./do gen:isa_explorer_browser_inst"                \
  "./do gen:isa_explorer_spreadsheet"                 \
  "./do gen:html_manual MANUAL_NAME=isa VERSIONS=all" \
  "./do gen:html[example_rv64_with_overlay]"          \
  "./do gen:instruction_appendix"                     \
  "./do gen:profile_release_pdf[RVI20]"               \
  "./do gen:profile_release_pdf[RVA20]"               \
  "./do gen:profile_release_pdf[RVA22]"               \
  "./do gen:profile_release_pdf[RVA23]"               \
  "./do gen:profile_release_pdf[RVB23]"               \
  "./do gen:proc_crd_pdf[AC100]"                      \
  "./do gen:proc_crd_pdf[AC200]"                      \
  "./do gen:proc_crd_pdf[MC100-32]"                   \
  "./do gen:proc_crd_pdf[MC100-64]"                   \
  "./do gen:proc_crd_pdf[MC200-32]"                   \
  "./do gen:proc_crd_pdf[MC200-64]"                   \
  "./do gen:proc_crd_pdf[MC300-32]"                   \
  "./do gen:proc_crd_pdf[MC300-64]"                   \
  "./do gen:proc_ctp_pdf[MC100-32]"                   \
  "./do gen:proc_ctp_pdf[MockProcessor]"

deploy_log "Copy UDB API"
deploy_cp_recursive gen/udb_api_doc $DEPLOY_DIR/htmls/udb_api_doc

deploy_log "Copy isa_explorer_browser"
deploy_cp_recursive gen/isa_explorer/browser $DEPLOY_DIR/isa_explorer

deploy_log "Copy isa_explorer_spreadsheet"
deploy_cp_recursive gen/isa_explorer/spreadsheet $DEPLOY_DIR/isa_explorer

deploy_log "Copy manual html"
deploy_cp_recursive gen/manual/isa/top/all/html $DEPLOY_DIR/manual

deploy_log "Copy cfg html"
deploy_cp_recursive gen/cfg_html_doc/example_rv64_with_overlay/html $DEPLOY_DIR/example_cfg

deploy_cp gen/instructions_appendix/instructions_appendix.pdf $DEPLOY_DIR/pdfs

for profile in RVI20 RVA20 RVA22 RVA23 RVB23; do
  deploy_log "Copy $profile Profile Release PDF Spec"
  deploy_cp gen/profile/pdf/${profile}ProfileRelease.pdf $DEPLOY_DIR/pdfs
done

for crd in AC100 AC200 MC100-32 MC100-64 MC200-32 MC200-64 MC300-32 MC300-64; do
  deploy_log "Copy ${crd}-CRD PDF"
  deploy_cp gen/proc_crd/pdf/${crd}-CRD.pdf $DEPLOY_DIR/pdfs
done

for ctp in MC100-32 MockProcessor; do
  deploy_log "Copy ${ctp}-CTP PDF"
  deploy_cp gen/proc_ctp/pdf/${ctp}-CTP.pdf $DEPLOY_DIR/pdfs
done

deploy_log "Create index"
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
      <li>
        <a href="$PAGES_URL/resolved_arch/index.yaml">index.yaml</a>
        Database index, as array of relative paths from $PAGES_URL/resolved_arch
        <ul>
          <li>
            For example, you can find <a href="$PAGES_URL/resolved_arch/ext/Sm.yaml">Sm.yaml</a> at $PAGES_URL/resolved_arch/ext/Sm.yaml
          </li>
        </ul>
      </li>
      <li>
        <a href="$PAGES_URL/resolved_arch.tar.gz">resolved_arch.tar.gz</a>
        The contents of the resolved architecture as a tarball
      </li>
    </ul>

    <br/>
    <h3>ISA Manual</h3>
    <ul>
      <li><a href="$PAGES_URL/manual/html/index.html">Generated HTML ISA manuals, all versions</a></li>
    </ul>

    <br/>
    <h3>Instruction Appendix</h3>
    <ul>
      <li><a href="$PAGES_URL/pdfs/instructions_appendix.pdf">Generated PDF appendix of all instructions</a></li>
    </ul>

    <br/>
    <h3>RISC-V ISA Explorer</h3>
    Candidate replacement for <a href="https://docs.google.com/spreadsheets/d/1A40dfm0nnn2-tgKIhdi3UYQ1GBr8iRiV2edFowvgp7E/edit?gid=1157775000">Profiles & Bases & Extensions Google Sheet</a>
    using data in riscv-unified-db.
    <ul>
      <li><a href="$PAGES_URL/isa_explorer/browser/ext_table.html">Extensions</a></li>
      <li><a href="$PAGES_URL/isa_explorer/browser/inst_table.html">Instructions</a></li>
      <li><a href="$PAGES_URL/isa_explorer/browser/csr_table.html">CSRs</a></li>
      <li><a href="$PAGES_URL/isa_explorer/spreadsheet/isa_explorer.xlsx">Excel version (includes Extensions, Instructions, CSRs)</a></li>
    </ul>

    <br/>
    <h3>Profile Releases</h3>
    <ul>
      <li><a href="$PAGES_URL/pdfs/RVI20ProfileRelease.pdf">RVI20 Profile Release</a></li>
      <li><a href="$PAGES_URL/pdfs/RVA20ProfileRelease.pdf">RVA20 Profile Release</a></li>
      <li><a href="$PAGES_URL/pdfs/RVA22ProfileRelease.pdf">RVA22 Profile Release</a></li>
      <li><a href="$PAGES_URL/pdfs/RVA23ProfileRelease.pdf">RVA23 Profile Release</a></li>
      <li><a href="$PAGES_URL/pdfs/RVB23ProfileRelease.pdf">RVB23 Profile Release</a></li>
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
    <h3>UDB Gem Documentation</h3>
    <ul>
      <li><a href="$PAGES_URL/htmls/udb_api_doc/index.html"><code>udb</code> Ruby API</a></li>
    </ul>

    <br/>
    <h3>IDL Documentation</h3>
    <ul>
      <li><a href="$PAGES_URL/ruby/idl/index.html">IDL language documentation</a></li>
    </ul>
  </body>
</html>
EOF

[[ $exit_status -eq 1 ]] && {
  deploy_log
  deploy_log '***************************************************************'
  deploy_log '*                      DEPLOY FAILED                          *'
  deploy_log '***************************************************************'
  deploy_log
  deploy_log "LIST OF FAILURES:"

  # Iterate through each failure array element.
  for f in "${failures[@]}"; do
    deploy_log "  $f"
  done
}

deploy_log
deploy_log "Overall exit status is $exit_status"
deploy_log

deploy_log '***************************************************************'
deploy_log '*                      DEPLOY COMPLETE                        *'
deploy_log '***************************************************************'

exit $exit_status
