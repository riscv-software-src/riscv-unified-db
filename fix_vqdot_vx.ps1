# Fix vqdot.vx.yaml
$content = @"
# Copyright (c) Kallal Mukherjee.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# yaml-language-server: `$schema=../../../../schemas/inst_schema.json

`$schema: "inst_schema.json#"
kind: instruction
name: vqdot.vx
long_name: Vector quad widening signed dot product (vector-scalar)
description: |
  Vector quad widening signed dot product instruction performing the dot product between a 4-element vector of 8-bit signed integer elements and a scalar 4-element vector of 8-bit signed integer elements, accumulating the result into a 32-bit signed integer accumulator.

  This instruction is only defined for SEW=32. It works on an element group with four 8-bit values stored together in a 32-bit bundle. For each input bundle for the dot product there is a corresponding (same index) SEW-wide element in the accumulator source (and destination).

  The "q" in the mnemonic indicates that the instruction is quad-widening. The number of body bundles is determined by ``vl``. The operation can be masked, each mask bit determines whether the corresponding element result is active or not.

  The operation performed is:
  ``````
  vd[i] = vs2[i][0] * xs1[0] + vs2[i][1] * xs1[1] + vs2[i][2] * xs1[2] + vs2[i][3] * xs1[3] + vd[i]
  ``````

  Where vs2[i] is a 32-bit bundle containing four 8-bit signed integers and xs1 contains four 8-bit signed integers in its lower 32 bits.
definedBy: Zvqdotq
assembly: vd, vs2, xs1, vm
encoding:
  match: 101100-----------110-----1010111
  variables:
    - name: vm
      location: 25-25
    - name: vs2
      location: 24-20
    - name: xs1
      location: 19-15
    - name: vd
      location: 11-7
access:
  s: always
  u: always
  vs: always
  vu: always
data_independent_timing: false
operation(): |
  # Vector quad widening signed dot product (vector-scalar)
  # SEW must be 32, operates on 4-element vectors of 8-bit signed integers
  
  if (SEW != 32) {
    raise(ExceptionCode::IllegalInstruction, mode(), encoding);
  }
  
  # Extract 4 8-bit signed elements from scalar register (lower 32 bits)
  xs1_elem0 = signed_byte(xs1[7:0]);
  xs1_elem1 = signed_byte(xs1[15:8]);
  xs1_elem2 = signed_byte(xs1[23:16]);
  xs1_elem3 = signed_byte(xs1[31:24]);
  
  # Process each vector element
  for (i = 0; i < vl; i++) {
    if (vm[i] || vm == 1) {  # Check mask
      # Extract 4 8-bit signed elements from vector bundle
      vs2_elem0 = signed_byte(vs2[i][7:0]);
      vs2_elem1 = signed_byte(vs2[i][15:8]);
      vs2_elem2 = signed_byte(vs2[i][23:16]);
      vs2_elem3 = signed_byte(vs2[i][31:24]);
      
      # Compute dot product: sum of element-wise products
      dot_product = vs2_elem0 * xs1_elem0 + 
                    vs2_elem1 * xs1_elem1 + 
                    vs2_elem2 * xs1_elem2 + 
                    vs2_elem3 * xs1_elem3;
      
      # Accumulate into destination
      vd[i] = signed_word(vd[i]) + dot_product;
    }
  }
"@; Set-Content "spec\std\isa\inst\Zvqdotq\vqdot.vx.yaml" -Value $content
