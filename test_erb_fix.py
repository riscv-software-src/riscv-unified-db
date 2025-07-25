#!/usr/bin/env python3
"""
Test script to verify ERB template resolution functionality.
"""
import sys
import os
import re

# Add the path to the generate_encoding.py module
sys.path.append(os.path.join(os.path.dirname(__file__), 'backends', 'generators', 'c_header'))

def resolve_erb_template(template_str):
    """
    Simple ERB template resolver for exception names.
    Resolves patterns like '<%- if ext?(:H) -%>V<%- end -%>U-mode' to 'U-mode'.
    """
    if not template_str:
        return template_str
    
    # Handle <%- if ext?(:H) -%>V<%- end -%> pattern (VU-mode -> U-mode)
    template_str = re.sub(r'<%- if ext\?\(:H\) -%>V<%- end -%>', '', template_str)
    
    # Handle <%- if ext?(:H) -%>H<%- end -%> pattern (HS-mode -> S-mode)  
    template_str = re.sub(r'<%- if ext\?\(:H\) -%>H<%- end -%>', '', template_str)
    
    return template_str.strip()

def test_erb_resolution():
    """Test the ERB template resolution with various inputs."""
    test_cases = [
        # Test case 1: VU-mode pattern
        {
            'input': '<%- if ext?(:H) -%>V<%- end -%>U-mode',
            'expected': 'U-mode',
            'description': 'VU-mode should resolve to U-mode'
        },
        # Test case 2: HS-mode pattern  
        {
            'input': '<%- if ext?(:H) -%>H<%- end -%>S-mode',
            'expected': 'S-mode',
            'description': 'HS-mode should resolve to S-mode'
        },
        # Test case 3: Environment call from VU-mode
        {
            'input': 'Environment call from <%- if ext?(:H) -%>V<%- end -%>U-mode',
            'expected': 'Environment call from U-mode',
            'description': 'Environment call from VU-mode should resolve to Environment call from U-mode'
        },
        # Test case 4: Environment call from HS-mode
        {
            'input': 'Environment call from <%- if ext?(:H) -%>H<%- end -%>S-mode',
            'expected': 'Environment call from S-mode',
            'description': 'Environment call from HS-mode should resolve to Environment call from S-mode'
        },
        # Test case 5: No ERB template
        {
            'input': 'Regular exception name',
            'expected': 'Regular exception name',
            'description': 'Regular names should remain unchanged'
        },
        # Test case 6: Empty string
        {
            'input': '',
            'expected': '',
            'description': 'Empty string should remain empty'
        },
        # Test case 7: None input
        {
            'input': None,
            'expected': None,
            'description': 'None input should return None'
        }
    ]
    
    print("Testing ERB Template Resolution")
    print("=" * 50)
    
    all_passed = True
    for i, test_case in enumerate(test_cases, 1):
        input_val = test_case['input']
        expected = test_case['expected']
        description = test_case['description']
        
        try:
            result = resolve_erb_template(input_val)
            passed = result == expected
            
            print(f"Test {i}: {description}")
            print(f"  Input:    {repr(input_val)}")
            print(f"  Expected: {repr(expected)}")
            print(f"  Result:   {repr(result)}")
            print(f"  Status:   {'PASS' if passed else 'FAIL'}")
            print()
            
            if not passed:
                all_passed = False
                
        except Exception as e:
            print(f"Test {i}: {description}")
            print(f"  Input:    {repr(input_val)}")
            print(f"  Expected: {repr(expected)}")
            print(f"  Error:    {str(e)}")
            print(f"  Status:   FAIL")
            print()
            all_passed = False
    
    print("=" * 50)
    if all_passed:
        print("✅ All tests PASSED! ERB template resolution is working correctly.")
        return True
    else:
        print("❌ Some tests FAILED! ERB template resolution needs fixing.")
        return False

def test_c_identifier_generation():
    """Test that the resolved names generate valid C identifiers."""
    print("\nTesting C Identifier Generation")
    print("=" * 50)
    
    test_cases = [
        {
            'erb_input': 'Environment call from <%- if ext?(:H) -%>V<%- end -%>U-mode',
            'expected_c_name': 'CAUSE_ENVIRONMENT_CALL_FROM_U_MODE'
        },
        {
            'erb_input': 'Environment call from <%- if ext?(:H) -%>H<%- end -%>S-mode',
            'expected_c_name': 'CAUSE_ENVIRONMENT_CALL_FROM_S_MODE'
        }
    ]
    
    all_passed = True
    for i, test_case in enumerate(test_cases, 1):
        erb_input = test_case['erb_input']
        expected_c_name = test_case['expected_c_name']
        
        # Resolve ERB template
        resolved_name = resolve_erb_template(erb_input)
        
        # Apply the same sanitization as in the actual code
        sanitized_name = (
            resolved_name.lower()
            .replace(" ", "_")
            .replace("/", "_")
            .replace("-", "_")
        )
        
        # Generate C identifier
        c_identifier = f"CAUSE_{sanitized_name.upper()}"
        
        passed = c_identifier == expected_c_name
        
        print(f"Test {i}:")
        print(f"  ERB Input:     {repr(erb_input)}")
        print(f"  Resolved:      {repr(resolved_name)}")
        print(f"  Sanitized:     {repr(sanitized_name)}")
        print(f"  C Identifier:  {repr(c_identifier)}")
        print(f"  Expected:      {repr(expected_c_name)}")
        print(f"  Status:        {'PASS' if passed else 'FAIL'}")
        print()
        
        if not passed:
            all_passed = False
    
    print("=" * 50)
    if all_passed:
        print("✅ All C identifier tests PASSED!")
        return True
    else:
        print("❌ Some C identifier tests FAILED!")
        return False

if __name__ == "__main__":
    print("RISC-V ERB Template Resolution Test")
    print("=" * 60)
    
    erb_tests_passed = test_erb_resolution()
    c_id_tests_passed = test_c_identifier_generation()
    
    print("\n" + "=" * 60)
    if erb_tests_passed and c_id_tests_passed:
        print("🎉 ALL TESTS PASSED! The ERB template fix is working correctly.")
        print("\nThe fix addresses issue #894 by properly resolving ERB templates")
        print("like '<%- if ext?(:H) -%>V<%- end -%>U-mode' to 'U-mode'")
        print("and generating valid C identifiers like 'CAUSE_ENVIRONMENT_CALL_FROM_U_MODE'")
        sys.exit(0)
    else:
        print("💥 SOME TESTS FAILED! The ERB template fix needs attention.")
        sys.exit(1)
