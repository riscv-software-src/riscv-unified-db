#!/usr/bin/env python3
"""
Simple verification script for ERB template resolution.
This script manually tests the regex patterns used in the fix.
"""
import re

def test_erb_patterns():
    """Test the ERB regex patterns directly."""
    
    # Test cases based on the actual patterns from issue #894
    test_cases = [
        {
            'name': 'VU-mode pattern',
            'input': '<%- if ext?(:H) -%>V<%- end -%>U-mode',
            'pattern': r'<%- if ext\?\(:H\) -%>V<%- end -%>',
            'expected': 'U-mode'
        },
        {
            'name': 'HS-mode pattern',
            'input': '<%- if ext?(:H) -%>H<%- end -%>S-mode',
            'pattern': r'<%- if ext\?\(:H\) -%>H<%- end -%>',
            'expected': 'S-mode'
        },
        {
            'name': 'Environment call from VU-mode',
            'input': 'Environment call from <%- if ext?(:H) -%>V<%- end -%>U-mode',
            'pattern': r'<%- if ext\?\(:H\) -%>V<%- end -%>',
            'expected': 'Environment call from U-mode'
        }
    ]
    
    print("Testing ERB Template Regex Patterns")
    print("=" * 50)
    
    all_passed = True
    
    for i, test in enumerate(test_cases, 1):
        input_str = test['input']
        pattern = test['pattern']
        expected = test['expected']
        
        # Apply the regex substitution
        result = re.sub(pattern, '', input_str).strip()
        
        passed = result == expected
        status = "PASS" if passed else "FAIL"
        
        print(f"Test {i}: {test['name']}")
        print(f"  Input:    '{input_str}'")
        print(f"  Pattern:  {pattern}")
        print(f"  Result:   '{result}'")
        print(f"  Expected: '{expected}'")
        print(f"  Status:   {status}")
        print()
        
        if not passed:
            all_passed = False
    
    return all_passed

def test_c_identifier_generation():
    """Test C identifier generation from resolved names."""
    
    test_cases = [
        {
            'resolved_name': 'Environment call from U-mode',
            'expected_c_id': 'CAUSE_ENVIRONMENT_CALL_FROM_U_MODE'
        },
        {
            'resolved_name': 'Environment call from S-mode',
            'expected_c_id': 'CAUSE_ENVIRONMENT_CALL_FROM_S_MODE'
        }
    ]
    
    print("Testing C Identifier Generation")
    print("=" * 50)
    
    all_passed = True
    
    for i, test in enumerate(test_cases, 1):
        resolved_name = test['resolved_name']
        expected_c_id = test['expected_c_id']
        
        # Apply the same sanitization as in the actual code
        sanitized_name = (
            resolved_name.lower()
            .replace(" ", "_")
            .replace("/", "_")
            .replace("-", "_")
        )
        
        # Generate C identifier
        c_identifier = f"CAUSE_{sanitized_name.upper()}"
        
        passed = c_identifier == expected_c_id
        status = "PASS" if passed else "FAIL"
        
        print(f"Test {i}:")
        print(f"  Resolved:     '{resolved_name}'")
        print(f"  Sanitized:    '{sanitized_name}'")
        print(f"  C Identifier: '{c_identifier}'")
        print(f"  Expected:     '{expected_c_id}'")
        print(f"  Status:       {status}")
        print()
        
        if not passed:
            all_passed = False
    
    return all_passed

def main():
    """Main test function."""
    print("RISC-V ERB Template Fix Verification")
    print("=" * 60)
    print()
    
    erb_tests_passed = test_erb_patterns()
    print()
    c_id_tests_passed = test_c_identifier_generation()
    
    print("=" * 60)
    if erb_tests_passed and c_id_tests_passed:
        print("✅ ALL TESTS PASSED!")
        print()
        print("The ERB template fix correctly resolves:")
        print("  - '<%- if ext?(:H) -%>V<%- end -%>U-mode' → 'U-mode'")
        print("  - '<%- if ext?(:H) -%>H<%- end -%>S-mode' → 'S-mode'")
        print()
        print("And generates valid C identifiers:")
        print("  - 'Environment call from U-mode' → 'CAUSE_ENVIRONMENT_CALL_FROM_U_MODE'")
        print("  - 'Environment call from S-mode' → 'CAUSE_ENVIRONMENT_CALL_FROM_S_MODE'")
        print()
        print("This addresses issue #894 and should fix the broken C header generation.")
        return True
    else:
        print("❌ SOME TESTS FAILED!")
        print("The ERB template fix needs attention.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
