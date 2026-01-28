import yaml
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple
import re


# Custom YAML representer
class CustomDumper(yaml.SafeDumper):
    """Custom YAML dumper that preserves block style for better readability"""
    pass

def dict_representer(dumper, data):
    return dumper.represent_mapping('tag:yaml.org,2002:map', data.items())

CustomDumper.add_representer(dict, dict_representer)

class ParameterTagger:
    def __init__(self, conventions_file: str):
        """Initialize the tagger with conventions from a YAML file"""
        conv_path = Path(conventions_file)
        if not conv_path.is_absolute():
            if not conv_path.exists():
                script_dir = Path(__file__).parent
                conv_path = script_dir / conventions_file
        
        if not conv_path.exists():
            print(f"ERROR: Conventions file not found: {conventions_file}")
            sys.exit(1)
        
        with open(str(conv_path), 'r') as f:
            self.conventions = yaml.safe_load(f)
        
        # Build lookup tables for efficient tagging
        self.param_to_suffix = {}
        self.build_lookup_tables()
    
    def build_lookup_tables(self):
        """Build efficient lookup tables from conventions"""
        for category in ['register_operands', 'immediate_operands', 'function_codes', 'compressed_fields', 'vector_fields', 'fp_fields']:
            if category not in self.conventions:
                continue
            
            for op_type, info in self.conventions[category].items():
                if 'names' in info:
                    suffix = info['tag_suffix']
                    for name in info['names']:
                        self.param_to_suffix[name] = suffix
        
        # Handle special cases
        if 'opcode' in self.conventions:
            for name in self.conventions['opcode']['names']:
                self.param_to_suffix[name] = self.conventions['opcode']['tag_suffix']
    
    def generate_tag(self, param_name: str, instruction_name: str) -> Tuple[str, str]:
        """
        Generate a tag for a parameter based on conventions
        
        Returns:
            (tag, suffix) tuple, or (None, None) if no match found
        """
        if param_name in self.param_to_suffix:
            suffix = self.param_to_suffix[param_name]
            tag = f"inst-{instruction_name}-{suffix}"
            return tag, suffix
        
        # Fallback for unnamed parameters - try to infer from context
        # This is where custom logic can be added
        return None, None
    
    def tag_instruction_file(self, file_path: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Add tags to parameters in an instruction YAML file using surgical edits
        to preserve formatting, comments, and structure.
        
        Args:
            file_path: Path to instruction YAML file
            dry_run: If True, only show what would be changed
        
        Returns:
            Dictionary with tagging results
        """
        result = {
            'file': file_path,
            'modified': False,
            'changes': [],
            'errors': [],
            'skipped': []
        }
        
        # Read the file content
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            result['errors'].append(f"Failed to read file: {e}")
            return result
        
        # Parse YAML to identify which parameters need tagging
        try:
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
        except Exception as e:
            result['errors'].append(f"Failed to parse YAML: {e}")
            return result
        
        if not data:
            result['errors'].append("Empty YAML file")
            return result
        
        # Get instruction name
        inst_name = data.get('name')
        if not inst_name:
            result['errors'].append("No 'name' field found in instruction")
            return result
        
        # Build list of parameters to tag
        params_to_tag = {}
        if 'encoding' in data and 'variables' in data['encoding']:
            for var in data['encoding']['variables']:
                param_name = var.get('name')
                if not param_name:
                    result['skipped'].append("Parameter with no name found")
                    continue
                
                # Skip if already has a tag
                if 'tag' in var:
                    continue
                
                # Generate tag
                tag, suffix = self.generate_tag(param_name, inst_name)
                
                if tag:
                    params_to_tag[param_name] = tag
                    result['changes'].append({
                        'parameter': param_name,
                        'tag': tag,
                        'suffix': suffix
                    })
                    result['modified'] = True
                else:
                    result['skipped'].append(f"No convention for parameter: {param_name}")
        
        # If no changes needed, return
        if not params_to_tag:
            return result
        
        # Apply surgical edits to preserve formatting
        if not dry_run:
            try:
                modified_lines = self._apply_surgical_edits(lines, params_to_tag)
                if modified_lines != lines:
                    with open(file_path, 'w') as f:
                        f.write('\n'.join(modified_lines))
                    result['written'] = True
            except Exception as e:
                result['errors'].append(f"Failed to write file: {e}")
                result['modified'] = False
        
        return result
    
    def _apply_surgical_edits(self, lines: List[str], params_to_tag: Dict[str, str]) -> List[str]:
        """
        Apply surgical edits to add tags without changing formatting.
        Looks for 'name: param_name' lines and adds 'tag: tag_value' after location line.
        """
        modified_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            modified_lines.append(line)
            
            # Check if this line contains a parameter name we need to tag
            param_found = None
            for param_name in params_to_tag:
                if f'name: {param_name}' in line or f"name: '{param_name}'" in line or f'name: "{param_name}"' in line:
                    param_found = param_name
                    break
            
            if param_found:
                # Found a parameter to tag, look for the location line
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    modified_lines.append(next_line)
                    if 'location:' in next_line:
                        indent = len(next_line) - len(next_line.lstrip())
                        indent_str = ' ' * indent
                        i += 1
                        if i < len(lines):
                            peek_line = lines[i]
                            if not peek_line.strip().startswith('tag:') and not peek_line.strip().startswith('- '):
                                modified_lines.insert(-1, f"{indent_str}tag: {params_to_tag[param_found]}")
                            elif peek_line.strip().startswith('- '):
                                modified_lines.insert(-1, f"{indent_str}tag: {params_to_tag[param_found]}")
                            else:
                                modified_lines.append(peek_line)
                                i += 1
                        else:
                            modified_lines.insert(-1, f"{indent_str}tag: {params_to_tag[param_found]}")
                        break
                    
                    i += 1
            else:
                i += 1
        
        return modified_lines
    
    def tag_extension(self, ext_dir: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Tag all instructions in an extension directory
        
        Args:
            ext_dir: Path to extension directory
            dry_run: If True, only show what would be changed
        
        Returns:
            Summary of all tagging operations
        """
        results = {
            'extension': ext_dir,
            'total_files': 0,
            'modified_files': 0,
            'total_changes': 0,
            'all_results': []
        }
        
        ext_path = Path(ext_dir)
        if not ext_path.exists():
            results['error'] = f"Extension directory not found: {ext_dir}"
            return results
        
        # Find all .yaml files in the extension directory
        yaml_files = list(ext_path.glob('*.yaml'))
        results['total_files'] = len(yaml_files)
        
        for yaml_file in sorted(yaml_files):
            result = self.tag_instruction_file(str(yaml_file), dry_run)
            results['all_results'].append(result)
            
            if result['modified']:
                results['modified_files'] += 1
                results['total_changes'] += len(result['changes'])
        
        return results
    
    def print_results(self, results: Dict[str, Any], verbose: bool = False):
        """Pretty print tagging results"""
        if 'error' in results:
            print(f"ERROR: {results['error']}")
            return
        
        # File-level results
        if 'all_results' in results:
            print(f"\nExtension Tagging Summary:")
            print(f"  Directory: {results['extension']}")
            print(f"  Total files: {results['total_files']}")
            print(f"  Modified files: {results['modified_files']}")
            print(f"  Total changes: {results['total_changes']}")
            
            if verbose:
                for result in results['all_results']:
                    if result['changes']:
                        print(f"\n  {Path(result['file']).name}:")
                        for change in result['changes']:
                            print(f"    {change['parameter']} -> {change['tag']}")
                    
                    if result['errors']:
                        print(f"  ERRORS in {Path(result['file']).name}:")
                        for error in result['errors']:
                            print(f"    - {error}")
        else:
            print(f"\nFile: {Path(results['file']).name}")
            print(f"  Modified: {results['modified']}")
            
            if results['changes']:
                print(f"  Changes ({len(results['changes'])}):")
                for change in results['changes']:
                    print(f"    {change['parameter']} -> {change['tag']}")
            
            if results['errors']:
                print(f"  Errors:")
                for error in results['errors']:
                    print(f"    - {error}")
            
            if results['skipped']:
                print(f"  Skipped ({len(results['skipped'])}):")
                for skip in results['skipped'][:3]:
                    print(f"    - {skip}")


def main():
    parser = argparse.ArgumentParser(
        description='Tag instruction parameters according to UDB conventions'
    )
    parser.add_argument(
        'target',
        nargs='?',
        help='File or directory to tag'
    )
    parser.add_argument(
        '-c', '--conventions',
        default='parameter_conventions.yaml',
        help='Path to conventions file (default: parameter_conventions.yaml)'
    )
    parser.add_argument(
        '-d', '--dry-run',
        action='store_true',
        help='Show what would be changed without modifying files'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '-e', '--extension',
        help='Tag all instructions in an extension directory'
    )
    
    args = parser.parse_args()
    
    # Verify conventions file exists
    if not Path(args.conventions).exists():
        print(f"ERROR: Conventions file not found: {args.conventions}")
        sys.exit(1)
    
    tagger = ParameterTagger(args.conventions)
    if args.extension:
        results = tagger.tag_extension(args.extension, args.dry_run)
    elif args.target:
        if not Path(args.target).exists():
            print(f"ERROR: File not found: {args.target}")
            sys.exit(1)
        
        results = tagger.tag_instruction_file(args.target, args.dry_run)
    else:
        parser.print_help()
        sys.exit(1)
    
    tagger.print_results(results, args.verbose)
    
    if 'errors' in results and results['errors']:
        sys.exit(1)
    
    if args.dry_run:
        print("\n[DRY RUN - No files were modified]")


if __name__ == '__main__':
    main()
