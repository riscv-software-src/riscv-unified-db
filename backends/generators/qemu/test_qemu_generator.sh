#!/bin/bash
# Test script for QEMU generator
# Demonstrates different use cases and verifies output

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="/tmp/qemu_gen_test_$$"
PYTHON="python3"

echo "=========================================="
echo "QEMU Generator Test Suite"
echo "=========================================="

# Create test directory
mkdir -p "$TEST_DIR"
echo "Test directory: $TEST_DIR"

# Test 1: Basic I extension only
echo -e "\n[Test 1] Generating for I extension only..."
$PYTHON "$SCRIPT_DIR/qemu_generator.py" \
    --extensions=I \
    --output-dir="$TEST_DIR/test1_i_only" \
    --arch=RV64 \
    --verbose 2>&1 | grep -E "(Enabled|successfully generated|CSR|Disassembly)" || true

# Test 2: Multiple extensions
echo -e "\n[Test 2] Generating for I,M,A,F,D extensions..."
$PYTHON "$SCRIPT_DIR/qemu_generator.py" \
    --extensions=I,M,A,F,D \
    --output-dir="$TEST_DIR/test2_imafed" \
    --arch=RV64 2>&1 | grep -E "(successfully generated|CSR|Disassembly)" || true

# Test 3: All extensions
echo -e "\n[Test 3] Generating for all extensions..."
$PYTHON "$SCRIPT_DIR/qemu_generator.py" \
    --include-all \
    --output-dir="$TEST_DIR/test3_all" \
    --arch=RV64 2>&1 | grep -E "(successfully generated|CSRs|Disassembly)" || true

# Test 4: RV32 architecture
echo -e "\n[Test 4] Generating for RV32 architecture..."
$PYTHON "$SCRIPT_DIR/qemu_generator.py" \
    --extensions=I,M \
    --output-dir="$TEST_DIR/test4_rv32" \
    --arch=RV32 2>&1 | grep -E "(successfully generated|CSR|Disassembly)" || true

# Verify output files exist
echo -e "\n=========================================="
echo "Verification Results"
echo "=========================================="

verify_files() {
    local dir=$1
    local test_name=$2

    if [ -f "$dir/insn32_generated.decode" ] && \
       [ -f "$dir/cpu_bits_generated.h" ] && \
       [ -f "$dir/riscv_disas_generated.c" ]; then
        echo "✓ $test_name: All output files present"

        # Check file contents
        if grep -q "@insn32_" "$dir/insn32_generated.decode" 2>/dev/null; then
            echo "  ✓ insn32_generated.decode has instruction entries"
        fi

        if grep -q "#define CSR_" "$dir/cpu_bits_generated.h" 2>/dev/null; then
            echo "  ✓ cpu_bits_generated.h has CSR definitions"
        fi

        if grep -q "{\"" "$dir/riscv_disas_generated.c" 2>/dev/null; then
            echo "  ✓ riscv_disas_generated.c has disassembly entries"
        fi
    else
        echo "✗ $test_name: Missing output files"
        return 1
    fi
}

verify_files "$TEST_DIR/test1_i_only" "Test 1 (I only)"
verify_files "$TEST_DIR/test2_imafed" "Test 2 (IMAFED)"
verify_files "$TEST_DIR/test3_all" "Test 3 (All)"
verify_files "$TEST_DIR/test4_rv32" "Test 4 (RV32)"

echo -e "\n=========================================="
echo "Summary"
echo "=========================================="
echo "All tests completed successfully!"
echo "Test artifacts stored in: $TEST_DIR"
echo "=========================================="
