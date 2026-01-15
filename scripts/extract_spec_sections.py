import yaml
from pathlib import Path
from typing import List, Dict, Tuple

def extract_pdf_text(pdf_file: str, output_file: str) -> bool:
    """Extract text from PDF - skip if not available"""
    
    try:
        from pypdf import PdfReader
        
        with open(pdf_file, 'rb') as f:
            reader = PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(text)
        
        print(f"Extracted text from {pdf_file} ({len(text):,} characters)")
        return True
    except ImportError:
        print(f"PDF extraction library not available. Skipping extraction for {output_file}")
        with open(output_file, 'w') as f:
            f.write("PDF extraction requires pypdf library.\n")
            f.write(f"Source: {pdf_file}\n")
        return False
    except Exception as e:
        print(f"Error extracting {pdf_file}: {e}")
        return False

def read_text_file(file_path: str) -> str:
    """Read entire text file"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return ""

def create_spec_sections_yaml(pdf_name: str, spec_type: str) -> Dict:
    """
    Define specification sections to extract for each PDF.
    Returns dict mapping section names to page ranges (approximate).
    """
    
    if spec_type == 'unprivileged':
        sections = {
            'section_1_isa_overview': {
                'chapter': 2,
                'title': 'ISA Overview',
                'pages': '8-30',
                'key_topics': ['Base ISA', 'Registers', 'Instruction Formats']
            },
            'section_2_floating_point': {
                'chapter': 5,
                'title': 'Single-Precision Floating-Point',
                'pages': '60-80',
                'key_topics': ['FLEN', 'Floating-point Extensions', 'Rounding']
            },
            'section_3_atomic': {
                'chapter': 8,
                'title': 'Atomic Instructions',
                'pages': '110-125',
                'key_topics': ['Atomic Memory Operations', 'A Extension']
            },
            'section_4_vector_part1': {
                'chapter': 13,
                'title': 'Vector Extension (Part 1)',
                'pages': '200-250',
                'key_topics': ['VLEN', 'Vector Configuration', 'Basic Operations']
            },
            'section_5_vector_part2': {
                'chapter': 13,
                'title': 'Vector Extension (Part 2)',
                'pages': '250-300',
                'key_topics': ['Advanced Vector Operations', 'ELEN', 'SEW']
            }
        }
    else:  # privileged
        sections = {
            'section_1_privilege_levels': {
                'chapter': 2,
                'title': 'Privilege Levels',
                'pages': '8-30',
                'key_topics': ['Machine Mode', 'Supervisor Mode', 'User Mode']
            },
            'section_2_csrs': {
                'chapter': 2,
                'title': 'Control and Status Registers',
                'pages': '30-80',
                'key_topics': ['MSTATUS', 'MISA', 'CSR Architecture']
            },
            'section_3_machine_isa': {
                'chapter': 3,
                'title': 'Machine-Level ISA',
                'pages': '80-130',
                'key_topics': ['Machine Instructions', 'MTVEC', 'Exception Handling']
            },
            'section_4_supervisor_isa': {
                'chapter': 4,
                'title': 'Supervisor-Level ISA',
                'pages': '130-170',
                'key_topics': ['Supervisor Mode', 'Virtual Memory', 'SATP']
            },
            'section_5_pmp': {
                'chapter': 7,
                'title': 'Physical Memory Protection',
                'pages': '200-230',
                'key_topics': ['PMP Entries', 'NUM_PMP_ENTRIES', 'Memory Protection']
            }
        }
    
    return sections

def save_sections_yaml(sections: Dict, output_file: str) -> None:
    """Save section definitions to YAML"""
    with open(output_file, 'w') as f:
        yaml.dump(sections, f, default_flow_style=False, sort_keys=False)
    print(f"Saved section definitions to {output_file}")

def main():
    print("=" * 70)
    print("RISC-V Specification Text Extraction")
    print("=" * 70)
    
    # Paths - relative to script location
    base_dir = Path(__file__).parent.parent
    unprivileged_pdf = base_dir / 'riscv-unprivileged.pdf'
    privileged_pdf = base_dir / 'riscv-privileged.pdf'
    
    output_dir = base_dir / 'spec_sections'
    output_dir.mkdir(exist_ok=True)
    
    # Extract unprivileged spec
    print("\n1. Extracting unprivileged specification...")
    unprivileged_text_file = output_dir / 'unprivileged_text.txt'
    if Path(unprivileged_pdf).exists():
        success = extract_pdf_text(unprivileged_pdf, str(unprivileged_text_file))
        if success:
            text = read_text_file(str(unprivileged_text_file))
            print(f"   Extracted {len(text):,} characters")
    else:
        print(f"   File not found: {unprivileged_pdf}")
    
    # Extract privileged spec
    print("\n2. Extracting privileged specification...")
    privileged_text_file = output_dir / 'privileged_text.txt'
    if Path(privileged_pdf).exists():
        success = extract_pdf_text(privileged_pdf, str(privileged_text_file))
        if success:
            text = read_text_file(str(privileged_text_file))
            print(f"   Extracted {len(text):,} characters")
    else:
        print(f"   File not found: {privileged_pdf}")
    
    # Create section definitions
    print("\n3. Creating section definitions...")
    
    unprivileged_sections = create_spec_sections_yaml('unprivileged', 'unprivileged')
    save_sections_yaml(
        unprivileged_sections,
        output_dir / 'SPEC_SECTIONS_UNPRIVILEGED.yaml'
    )
    
    privileged_sections = create_spec_sections_yaml('privileged', 'privileged')
    save_sections_yaml(
        privileged_sections,
        output_dir / 'SPEC_SECTIONS_PRIVILEGED.yaml'
    )
    
    # Summary
    print("\n✓ Extraction completed")

if __name__ == '__main__':
    main()
