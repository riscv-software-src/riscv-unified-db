#!/bin/bash
# SPDX-FileCopyrightText: 2026 Harvey Mudd Clinic Team
# SPDX-License-Identifier: BSD-3-Clause-Clear


set -euo pipefail

# ─────────────────────────────────────────────
# regen-udb-ls.sh  (macOS)
# Rebuilds udb-ls-all.jar and copies it into the
# udb-vscode extension's server folder.
#
# Override paths via env vars if needed:
#   PARENT_DIR   path to org.xtext.udb.parent
#   VSCODE_DIR   path to udb-vscode
# ─────────────────────────────────────────────

usage() {
    cat <<'EOF'
regen-udb-ls.sh  -  rebuild the UDB language server and install it
                    into the udb-vscode extension's server/ folder.

Usage:
  ./regen-udb-ls.sh        Rebuild and install the language server.
  ./regen-udb-ls.sh -h     Show this help.

Environment overrides:
  PARENT_DIR   Path to org.xtext.udb.parent
  VSCODE_DIR   Path to udb-vscode  (server/ is created inside it)
EOF
}

case "${1:-}" in
    -h|--help) usage; exit 0 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PARENT_DIR="${PARENT_DIR:-$SCRIPT_DIR/tools/eclipse/dev/org.xtext.udb.parent}"
VSCODE_SERVER_DIR="${VSCODE_DIR:-$SCRIPT_DIR/udb-vscode}/server"
IDE_TARGET="$PARENT_DIR/org.xtext.udb.ide/target"
JRUBY_DIR="$PARENT_DIR/org.xtext.udb.jruby"

RED='\033[0;31m'; GREEN='\033[0;32m'
YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── preflight checks ─────────────────────────
info "Checking prerequisites..."

if ! command -v mvn &>/dev/null; then
    error "Maven not found. Install with: brew install maven"
    exit 1
fi
success "Maven found: $(mvn -v | head -1)"

if [ ! -d "$PARENT_DIR" ]; then
    error "Parent project not found at: $PARENT_DIR"
    error "Set PARENT_DIR env var to override."
    exit 1
fi

if [ ! -d "$VSCODE_SERVER_DIR" ]; then
    warn "VS Code server dir not found at: $VSCODE_SERVER_DIR — creating it..."
    mkdir -p "$VSCODE_SERVER_DIR"
    success "Created: $VSCODE_SERVER_DIR"
fi

# ── build ────────────────────────────────────
cd "$PARENT_DIR"
info "Working directory: $PARENT_DIR"

run_build() {
    info "Running: mvn clean verify -DskipTests"
    mvn clean verify -DskipTests || return 1
    info "Running: mvn -DskipTests package"
    mvn -DskipTests package || return 1
}

if ! run_build; then
    warn "Build failed — attempting Tycho cache fix..."
    rm -rf ~/.m2/repository/.cache/tycho
    export MAVEN_OPTS="${MAVEN_OPTS:-} -Djdk.xml.maxGeneralEntitySizeLimit=0 -Djdk.xml.totalEntitySizeLimit=0"
    info "Retrying build..."
    if ! run_build; then
        error "Build failed even after cache clear. Check Maven output above."
        exit 1
    fi
fi

# ── locate JAR ───────────────────────────────
info "Locating generated JAR in $IDE_TARGET ..."
JAR_PATH=$(find "$IDE_TARGET" -maxdepth 1 -name "*SNAPSHOT-ls.jar" | head -1)

if [ -z "$JAR_PATH" ]; then
    error "No *SNAPSHOT-ls.jar found in $IDE_TARGET"
    exit 1
fi
success "Found: $JAR_PATH"

# ── copy and rename ───────────────────────────
DEST="$VSCODE_SERVER_DIR/udb-ls-all.jar"
info "Copying to $DEST ..."
cp "$JAR_PATH" "$DEST"
success "Done! JAR installed at: $DEST"

# ── copy idlc and vendor ──────────────────────
for FOLDER in idlc vendor; do
    SRC="$JRUBY_DIR/$FOLDER"
    if [ ! -d "$SRC" ]; then
        warn "$FOLDER folder not found at: $SRC — skipping."
        continue
    fi
    info "Copying $FOLDER to $VSCODE_SERVER_DIR/$FOLDER ..."
    rm -rf "$VSCODE_SERVER_DIR/$FOLDER"
    cp -r "$SRC" "$VSCODE_SERVER_DIR/$FOLDER"
    success "Copied $FOLDER to: $VSCODE_SERVER_DIR/$FOLDER"
done

echo ""
echo -e "${GREEN}────────────────────────────────────────────${NC}"
echo -e "${GREEN} Language server rebuilt successfully.${NC}"
echo -e "${GREEN} Remember: only commit the new .jar file.${NC}"
echo -e "${GREEN}────────────────────────────────────────────${NC}"
