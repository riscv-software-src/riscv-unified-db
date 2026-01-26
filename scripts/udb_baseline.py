import yaml
import json
from pathlib import Path

from collections import defaultdict
import sys

def load_udb_parameters(category: str):
    """
    Load all parameters from UDB YAML files for specified category.
    Returns dict of all known parameters.
    """
    base_dir = Path(__file__).parent.parent / "spec" / "std" / "isa"
    category_dir = base_dir / category
    parameters = {}
    
    print(f"Loading {category} parameters from: {category_dir}")
    
    if not category_dir.exists():
        print(f"ERROR: Category directory not found: {category_dir}")
        return {}
    
    # Route to category-specific loader
    if category == "csr":
        parameters = load_csr_parameters(category_dir)
    elif category == "param":
        parameters = load_param_parameters(category_dir)
    elif category == "ext":
        parameters = load_ext_parameters(category_dir)
    elif category == "inst":
        parameters = load_inst_parameters(category_dir)
    elif category == "exception_code":
        parameters = load_exception_parameters(category_dir)
    elif category == "interrupt_code":
        parameters = load_interrupt_parameters(category_dir)
    elif category == "profile":
        parameters = load_profile_parameters(category_dir)
    else:
        print(f"ERROR: Unknown category: {category}")
        return {}
    
    return parameters

def load_csr_parameters(category_dir):
    """Extract CSR field parameters"""
    parameters = {}
    for yaml_file in sorted(category_dir.glob("*.yaml")):
        if yaml_file.name == "schema.adoc":
            continue
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if not data or "fields" not in data:
                continue
            csr_name = data.get("name", yaml_file.stem).upper()
            for field_name, field_data in data.get("fields", {}).items():
                param_name = f"{csr_name}_{field_name}"
                parameters[param_name] = {
                    "csr": csr_name,
                    "field": field_name,
                    "file": yaml_file.name,
                    "type": field_data.get("type", "RW"),
                    "description": field_data.get("description", "")[:100]
                }
        except Exception as e:
            print(f"Warning: Failed to parse {yaml_file.name}: {e}")
    return parameters

def load_param_parameters(category_dir):
    """Extract configuration parameters"""
    parameters = {}
    for yaml_file in sorted(category_dir.glob("*.yaml")):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            param_name = data.get("name", yaml_file.stem).upper()
            parameters[param_name] = {
                "category": "param",
                "file": yaml_file.name,
                "type": data.get("type", "unknown"),
                "description": data.get("description", "")[:100],
                "legal_values": data.get("legal_values", "")
            }
        except Exception as e:
            print(f"Warning: Failed to parse {yaml_file.name}: {e}")
    return parameters

def load_ext_parameters(category_dir):
    """Extract ISA extension parameters"""
    parameters = {}
    for yaml_file in sorted(category_dir.glob("*.yaml")):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            ext_name = data.get("name", yaml_file.stem).upper()
            parameters[ext_name] = {
                "category": "ext",
                "file": yaml_file.name,
                "version": data.get("version", ""),
                "description": data.get("description", "")[:100],
                "dependencies": data.get("dependencies", [])
            }
        except Exception as e:
            print(f"Warning: Failed to parse {yaml_file.name}: {e}")
    return parameters

def load_inst_parameters(category_dir):
    """Extract instruction parameters"""
    parameters = {}
    for yaml_file in sorted(category_dir.glob("*.yaml")):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            inst_name = data.get("name", yaml_file.stem).upper()
            parameters[inst_name] = {
                "category": "inst",
                "file": yaml_file.name,
                "mnemonic": data.get("mnemonic", ""),
                "inst_type": data.get("inst_type", ""),
                "description": data.get("description", "")[:100]
            }
        except Exception as e:
            print(f"Warning: Failed to parse {yaml_file.name}: {e}")
    return parameters

def load_exception_parameters(category_dir):
    """Extract exception code parameters"""
    parameters = {}
    for yaml_file in sorted(category_dir.glob("*.yaml")):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            exc_name = data.get("name", yaml_file.stem).upper()
            parameters[exc_name] = {
                "category": "exception_code",
                "file": yaml_file.name,
                "code": data.get("code", ""),
                "description": data.get("description", "")[:100]
            }
        except Exception as e:
            print(f"Warning: Failed to parse {yaml_file.name}: {e}")
    return parameters

def load_interrupt_parameters(category_dir):
    """Extract interrupt code parameters"""
    parameters = {}
    for yaml_file in sorted(category_dir.glob("*.yaml")):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            int_name = data.get("name", yaml_file.stem).upper()
            parameters[int_name] = {
                "category": "interrupt_code",
                "file": yaml_file.name,
                "code": data.get("code", ""),
                "description": data.get("description", "")[:100]
            }
        except Exception as e:
            print(f"Warning: Failed to parse {yaml_file.name}: {e}")
    return parameters

def load_profile_parameters(category_dir):
    """Extract profile parameters"""
    parameters = {}
    for yaml_file in sorted(category_dir.glob("*.yaml")):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            prof_name = data.get("name", yaml_file.stem).upper()
            parameters[prof_name] = {
                "category": "profile",
                "file": yaml_file.name,
                "long_name": data.get("long_name", ""),
                "description": data.get("description", "")[:100],
                "required_extensions": data.get("required_extensions", [])
            }
        except Exception as e:
            print(f"Warning: Failed to parse {yaml_file.name}: {e}")
    return parameters

def analyze_parameters(parameters):
    """Analyze and categorize parameters."""
    analysis = {
        "total_count": len(parameters),
        "by_csr": defaultdict(list),
        "by_type": defaultdict(list),
        "writable_fields": [],
        "readonly_fields": [],
        "warl_fields": [],
        "csr_count": len(set(p["csr"] for p in parameters.values()))
    }
    
    for param_name, param_info in parameters.items():
        csr = param_info["csr"]
        field_type = param_info["field_info"].get("type", "").upper()
        
        analysis["by_csr"][csr].append(param_name)
        analysis["by_type"][field_type].append(param_name)
        
        if "RW" in field_type:
            analysis["writable_fields"].append(param_name)
        else:
            analysis["readonly_fields"].append(param_name)
        
        if "WARL" in field_type:
            analysis["warl_fields"].append(param_name)
    
    return analysis

def export_baseline_json(category: str, parameters, output_path):
    """Export parameters as JSON for comparison phase"""
    json_data = {
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "category": category,
        "source": f"UDB {category} YAML files",
        "total_parameters": len(parameters),
        "parameters": {}
    }
    
    for param_name, param_info in sorted(parameters.items()):
        json_data["parameters"][param_name] = {
            "category": category,
            "file": param_info.get("file", ""),
            "description": param_info.get("description", "")
        }
        # Add category-specific fields
        for key in param_info:
            if key not in ["file", "description"]:
                json_data["parameters"][param_name][key] = param_info[key]
    
    with open(output_path, "w") as f:
        json.dump(json_data, f, indent=2)
    
    print(f"Baseline exported to: {output_path}")

def print_summary(category: str, parameters, analysis):
    """Print summary statistics"""
    print("\n" + "="*80)
    print(f"UDB {category.upper()} PARAMETER BASELINE SUMMARY")
    print("="*80)
    print(f"\nTotal parameters: {analysis['total_count']}")
    
    if "by_category" in analysis:
        print(f"Categories: {len(analysis['by_category'])}")
        for cat, params in sorted(analysis["by_category"].items(), key=lambda x: -len(x[1]))[:5]:
            print(f"  {cat}: {len(params)} parameters")
    
    if "by_type" in analysis:
        print(f"\nTypes:")
        for type_name, params in sorted(analysis["by_type"].items(), key=lambda x: -len(x[1]))[:5]:
            print(f"  {type_name}: {len(params)} parameters")
    
    print("\n" + "="*80)
    print(f"Sample parameters (first 20):")
    print("="*80)
    for i, param_name in enumerate(sorted(parameters.keys())[:20], 1):
        param = parameters[param_name]
        desc = param.get("description", "")[:40]
        print(f"{i:2d}. {param_name:40s} {desc}")

def main():
    # Parse command line arguments
    category = "csr"  # Default
    if len(sys.argv) > 1:
        category = sys.argv[1].lower()
    
    valid_categories = ["csr", "param", "ext", "inst", "exception_code", "interrupt_code", "profile"]
    if category not in valid_categories:
        print(f"ERROR: Invalid category: {category}")
        print(f"Valid categories: {', '.join(valid_categories)}")
        sys.exit(1)
    
    print(f"Loading UDB {category} parameters...")
    parameters = load_udb_parameters(category)
    
    if not parameters:
        print("ERROR: No parameters loaded!")
        return
    
    # Analyze
    analysis = {
        "total_count": len(parameters),
        "by_type": defaultdict(list),
        "by_category": defaultdict(list)
    }
    
    for param_name, param_info in parameters.items():
        param_type = param_info.get("type", "unknown")
        analysis["by_type"][param_type].append(param_name)
    
    print_summary(category, parameters, analysis)
    
    # Export
    output_dir = Path(__file__).parent.parent / "baseline" / category
    output_dir.mkdir(parents=True, exist_ok=True)
    
    baseline_file = output_dir / "udb_baseline.json"
    export_baseline_json(category, parameters, baseline_file)
    
    print(f"\n[OK] Baseline created with {len(parameters)} parameters")
    print(f"[OK] Category: {category}")
    print(f"[OK] Ready for Phase 2 comparison")

if __name__ == "__main__":
    main()
