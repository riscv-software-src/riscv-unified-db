import yaml
from pathlib import Path
from typing import List, Dict

def load_udb_parameters(param_dir: str) -> Dict[str, Dict]:
    """Load all UDB parameter YAML files"""
    param_path = Path(param_dir)
    params = {}
    
    for yaml_file in sorted(param_path.glob('*.yaml')):
        try:
            with open(yaml_file, 'r') as f:
                param_data = yaml.safe_load(f)
            if param_data:
                param_name = yaml_file.stem
                params[param_name] = param_data
        except Exception as e:
            print(f"Error loading {yaml_file}: {e}")
    
    return params

def select_diverse_examples(params: Dict[str, Dict]) -> List[Dict]:
    """
    Select 15 diverse examples covering different extensions and categories.
    
    Categories to cover:
    - Vector extension (2-3)
    - Privileged/CSR (2-3)
    - Floating-point (2)
    - Atomic (1)
    - Multiply (1)
    - Compressed (1)
    - Other extensions (3-4)
    """
    
    # Define selection criteria - prioritize known parameters
    priority_params = [
        'VLEN',              # Vector: config-dependent, named, explicit
        'ELEN',              # Vector: config-dependent, named, explicit
        'ASID_WIDTH',        # Privileged: config-dependent, named, explicit
        'NUM_PMP_ENTRIES',   # Privileged: config-dependent, named, explicit
        'MTVEC_MODES',       # Privileged: config-dependent, named, explicit
        'FLEN',              # Floating-point: config-dependent, named, explicit
    ]
    
    selected = []
    seen_names = set()
    
    # add priority parameters if they exist
    for param_name in priority_params:
        if param_name in params and param_name not in seen_names:
            param = params[param_name].copy()
            param['udb_name'] = param_name
            selected.append(param)
            seen_names.add(param_name)
    
    # Then add more diverse examples to reach 15
    extension_counts = {}
    for param_name, param_data in params.items():
        if param_name in seen_names or len(selected) >= 15:
            continue
        
        defined_by = param_data.get('definedBy', 'unknown')
        # Convert dict to string for counting
        if isinstance(defined_by, dict):
            defined_by = str(defined_by)
        
        # Diversify by extension
        if extension_counts.get(defined_by, 0) < 2:
            param_copy = param_data.copy()
            param_copy['udb_name'] = param_name
            selected.append(param_copy)
            extension_counts[defined_by] = extension_counts.get(defined_by, 0) + 1
            seen_names.add(param_name)
    
    return selected[:15]

def create_example_entry(param_name: str, param_data: Dict) -> Dict:
    """Create a structured example entry for prompt use"""
    
    return {
        'name': param_data.get('name', param_name),
        'udb_name': param_name,
        'description': param_data.get('description', 'No description'),
        'definedBy': param_data.get('definedBy', 'unknown'),
        'schema': param_data.get('schema', {}),
        'type': 'Configuration-dependent',  
        'naming': 'Named',  
        'explicitness': 'Explicit',
        'in_udb': True,
        'udb_path': f'riscv-unified-db/spec/std/isa/param/{param_name}.yaml'
    }

def save_examples(examples: List[Dict], output_file: str) -> None:
    """Save examples to YAML file"""
    
    examples_dict = {}
    for i, example in enumerate(examples, 1):
        examples_dict[f'EXAMPLE_{i}'] = example
    
    with open(output_file, 'w') as f:
        yaml.dump(examples_dict, f, default_flow_style=False, sort_keys=False)
    
    print(f"Saved {len(examples)} examples to {output_file}")
    for i, example in enumerate(examples, 1):
        print(f"  {i}. {example['udb_name']}: {example['name']}")

def main():
    base_dir = Path(__file__).parent.parent
    udb_param_dir = base_dir / 'spec' / 'std' / 'isa' / 'param'
    output_dir = base_dir / 'prompts'
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / 'UDB_EXAMPLES.yaml'
    
    print("Loading UDB parameters...")
    params = load_udb_parameters(str(udb_param_dir))
    print(f"Loaded {len(params)} parameters from UDB")
    
    print("\nSelecting diverse examples...")
    examples = select_diverse_examples(params)
    print(f"Selected {len(examples)} diverse examples")
    
    print("\nCreating example entries...")
    example_entries = [create_example_entry(ex.get('udb_name', name), ex) 
                       for name, ex in enumerate(examples)]
    
    print("\nSaving examples...")
    save_examples(examples, str(output_file))

if __name__ == '__main__':
    main()

