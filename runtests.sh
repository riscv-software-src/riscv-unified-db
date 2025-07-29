#!/bin/bash

tests="simple \
	add addi \
	and andi \
	auipc \
	beq bge bgeu blt bltu bne \
	fence_i \
	jal jalr \
	lb lbu lh lhu lw ld_st \
	lui \
	ma_data \
	or ori \
	sb sh sw st_ld \
	sll slli \
	slt slti sltiu sltu \
	sra srai \
	srl srli \
	sub \
	xor xori"

for rvtest in $tests
do
    echo $rvtest
    ./gen/cpp_hart_gen/rv32_Debug/build/iss -m rv32 -c ./cfgs/mc100-32-riscv-tests.yaml ext/riscv-tests/isa/rv32ui-p-$rvtest
done
