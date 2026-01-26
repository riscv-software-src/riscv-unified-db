import json
import yaml
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import sys
from difflib import SequenceMatcher

def fuzzy_match_names(name1: str, name2: str, threshold: float = 0.75) -> bool:
    """
    Fuzzy match parameter names using sequence similarity.
    Returns True if names are similar enough to be considered the same parameter.
    """
    # Exact match
    if name1 == name2:
        return True
    
    # Extract CSR and field names (format: CSR_FIELD_SEMANTIC)
    parts1 = name1.split('_')
    parts2 = name2.split('_')
    
    # If CSR and field match, consider parameters equivalent
    if len(parts1) >= 2 and len(parts2) >= 2:
        if parts1[0] == parts2[0] and parts1[1] == parts2[1]:
            return True
    
    # Fallback to sequence similarity for fuzzy matching
    similarity = SequenceMatcher(None, name1, name2).ratio()
    return similarity >= threshold

def normalize_parameter_names(llm1_params: list, llm2_params: list):
    """
    Match parameters from two LLMs using fuzzy matching.
    Returns sets of matched and unmatched parameters.
    """
    llm1_dict = {p.get("name"): p for p in llm1_params if isinstance(p, dict) and "name" in p}
    llm2_dict = {p.get("name"): p for p in llm2_params if isinstance(p, dict) and "name" in p}
    
    matched_pairs = []
    matched_llm1 = set()
    matched_llm2 = set()
    
    # Try to match each LLM1 param with LLM2 params
    for name1, param1 in llm1_dict.items():
        for name2, param2 in llm2_dict.items():
            if name2 in matched_llm2:
                continue
            
            if fuzzy_match_names(name1, name2):
                matched_pairs.append((name1, name2, param1, param2))
                matched_llm1.add(name1)
                matched_llm2.add(name2)
                break
    
    return matched_pairs, set(llm1_dict.keys()) - matched_llm1, set(llm2_dict.keys()) - matched_llm2

def load_baseline(category: str):
    """Load UDB baseline for specified category"""
    baseline_file = Path(__file__).parent.parent / "baseline" / category / "udb_baseline.json"
    if not baseline_file.exists():
        return set(), {}
    
    with open(baseline_file) as f:
        data = json.load(f)
    
    # Extract parameter names
    known_params = set(data["parameters"].keys())
    return known_params, data["parameters"]

def load_evaluation_metrics():
    """Load evaluation metrics definitions and thresholds from YAML"""
    metrics_file = Path(__file__).parent.parent / "prompts" / "EVALUATION_METRICS.yaml"
    with open(metrics_file) as f:
        content = f.read()
    return content

def load_llm_results(category: str, item_name: str):
    """Load LLM extraction results from evaluation/{category}/"""
    results_file = Path(__file__).parent.parent / "evaluation" / category / f"{item_name}_results.json"
    if not results_file.exists():
        return None    
    with open(results_file) as f:
        return json.load(f)

def compare_results(llm_results, known_params, baseline_params):
    """Compare LLM results with UDB baseline and calculate all 10 metrics"""
    llm1_params = llm_results.get("hf_response", [])  # OpenAI GPT-OSS-120B
    llm2_params = llm_results.get("scout_response", [])  # Groq Scout
    
    # Use fuzzy matching to normalize names
    matched_pairs, llm1_unmatched, llm2_unmatched = normalize_parameter_names(llm1_params, llm2_params)
    
    llm1_dict = {p.get("name"): p for p in llm1_params if isinstance(p, dict) and "name" in p}
    llm2_dict = {p.get("name"): p for p in llm2_params if isinstance(p, dict) and "name" in p}
    
    # Count agreement using fuzzy matching
    llm1_names = set(llm1_dict.keys())
    llm2_names = set(llm2_dict.keys())
    
    # Identify novel parameters (fuzzy match against known)
    novel_llm1 = set()
    novel_llm2 = set()
    
    for name in llm1_names:
        found_in_baseline = any(fuzzy_match_names(name, baseline_name) for baseline_name in known_params)
        if not found_in_baseline:
            novel_llm1.add(name)
    
    for name in llm2_names:
        found_in_baseline = any(fuzzy_match_names(name, baseline_name) for baseline_name in known_params)
        if not found_in_baseline:
            novel_llm2.add(name)
    
    # Agreement and divergence calculation
    agreement_count = len(matched_pairs)
    llm1_only = llm1_names - llm2_names
    llm2_only = llm2_names - llm1_names
    
    # Novelty calculation
    total_params = len(llm1_names | llm2_names)
    novel_count = len(novel_llm1 | novel_llm2)
    novelty_percent = (novel_count / total_params * 100) if total_params > 0 else 0
    
    #Behavioral Impact
    behavioral_count = 0
    for param_name in llm1_names | llm2_names:
        param = llm1_dict.get(param_name) or llm2_dict.get(param_name)
        if param and param.get("behavioral_impact"):
            behavioral_count += 1
    behavioral_percent = (behavioral_count / total_params * 100) if total_params > 0 else 0
    
    #Documentation Gap (Implicit/Undocumented)
    implicit_count = 0
    for param_name in llm1_names | llm2_names:
        param = llm1_dict.get(param_name) or llm2_dict.get(param_name)
        if param:
            explicitness = param.get("explicitness", "").lower()
            if explicitness in ["implicit", "undocumented"]:
                implicit_count += 1
    documentation_gap_percent = (implicit_count / total_params * 100) if total_params > 0 else 0
    
    #Validation Feasibility
    validatable_count = 0
    for param_name in llm1_names | llm2_names:
        param = llm1_dict.get(param_name) or llm2_dict.get(param_name)
        if param:
            validation = param.get("validation_method", "").lower()
            if validation in ["spec_quote", "code_execution", "trap_test"]:
                validatable_count += 1
    validation_feasibility = (validatable_count / total_params * 100) if total_params > 0 else 0
    
    #Hallucination Rate
    hallucination_count = 0
    for param_name in llm1_names | llm2_names:
        param = llm1_dict.get(param_name) or llm2_dict.get(param_name)
        if param and not param.get("spec_quote"):
            hallucination_count += 1
    hallucination_rate = (hallucination_count / total_params * 100) if total_params > 0 else 0
    
    # LLM Agreement
    agreement_percent = (agreement_count / max(total_params, 1) * 100) if total_params > 0 else 0
    
    # Confidence Calibration
    confidence_scores = []
    for name1, name2, param1, param2 in matched_pairs:
        c1 = param1.get("confidence", 3) if isinstance(param1, dict) else 3
        c2 = param2.get("confidence", 3) if isinstance(param2, dict) else 3
        avg_confidence = (c1 + c2) / 2
        confidence_scores.append(avg_confidence)
    avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 3.0
    
    # Convergence Rate (from llm_evaluation.py metrics)
    convergence_rate = llm_results.get("metrics", {}).get("convergence_percentage", 0)
    
    # Confidence Alignment (same confidence scores between models)
    confidence_alignment_count = 0
    for name1, name2, param1, param2 in matched_pairs:
        c1 = param1.get("confidence", 3) if isinstance(param1, dict) else 3
        c2 = param2.get("confidence", 3) if isinstance(param2, dict) else 3
        if abs(c1 - c2) <= 1:
            confidence_alignment_count += 1
    confidence_alignment_percent = (confidence_alignment_count / agreement_count * 100) if agreement_count > 0 else 0
    
    # Categorization Agreement
    category_agreement_count = 0
    for name1, name2, param1, param2 in matched_pairs:
        if isinstance(param1, dict) and isinstance(param2, dict):
            if param1.get("type") == param2.get("type") and param1.get("behavioral_impact") == param2.get("behavioral_impact"):
                category_agreement_count += 1
    categorization_agreement = (category_agreement_count / agreement_count * 100) if agreement_count > 0 else 0
    
    metrics = {
        "llm1_total": len(llm1_names),
        "llm2_total": len(llm2_names),
        "total_unique": total_params,
        "llm1_known": len(llm1_names - novel_llm1),
        "llm1_novel": len(novel_llm1),
        "llm2_known": len(llm2_names - novel_llm2),
        "llm2_novel": len(novel_llm2),
        "total_agreement": agreement_count,
        "llm1_only": len(llm1_only),
        "llm2_only": len(llm2_only),
        "novel_agreement": len(novel_llm1 & novel_llm2),
        "llm1_novel_params": list(novel_llm1),
        "llm2_novel_params": list(novel_llm2),
        "llm1_only_params": list(llm1_only),
        "llm2_only_params": list(llm2_only),
        "novel_agreement_params": list(novel_llm1 & novel_llm2),
        "metric_1_novelty_percent": round(novelty_percent, 2),
        "metric_2_behavioral_percent": round(behavioral_percent, 2),
        "metric_3_documentation_gap_percent": round(documentation_gap_percent, 2),
        "metric_4_validation_feasibility": round(validation_feasibility, 2),
        "metric_5_hallucination_rate": round(hallucination_rate, 2),
        "metric_6_llm_agreement_percent": round(agreement_percent, 2),
        "metric_7_avg_confidence": round(avg_confidence, 2),
        "metric_8_convergence_rate": round(convergence_rate, 2),
        "metric_9_confidence_alignment": round(confidence_alignment_percent, 2),
        "metric_10_categorization_agreement": round(categorization_agreement, 2)
    }
    
    return metrics

def print_comparison(csr_name, metrics, llm_results):
    """Print comparison results"""
    pass

def save_comparison(category: str, item_name: str, metrics):
    """Save comparison results to comparison/{category}/"""
    output_dir = Path(__file__).parent.parent / "comparison" / category
    output_dir.mkdir(parents=True, exist_ok=True)
    
    comparison_file = output_dir / f"{item_name}_comparison.json"
    with open(comparison_file, 'w') as f:
        json.dump(metrics, f, indent=2)

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
    
    print(f"Loading UDB baseline for category: {category}...")
    known_params, baseline_params = load_baseline(category)
    print(f"Loaded {len(known_params)} known parameters")
    
    # Import comprehensive CSR sample from llm_evaluation
    def get_comprehensive_csr_sample():
        """Return comprehensive sample covering all CSR domains"""
        return [
            "mepc", "mtvec", "mcause", "mip", "mie", "mstatus", "menvcfg", "medeleg", "mideleg",
            "mstatush", "mstateen0", "mstateen1", "mstateen2", "mstateen3",
            "sstatus", "sip", "sepc", "scause",
            "hstatus", "hie", "hip", "henvcfg", "hcounteren",
            "hstateen0", "hstateen1", "hstateen2", "hstateen3",
            "frm", "fcsr", "fflags",
            "vtype", "vl", "vstart", "vcsr", "vxrm", "vxsat",
            "satp", "vsatp", "hgatp", "pgctrl",
            "pmpcfg0", "pmpcfg1", "pmpcfg8", "pmpaddr0", "pmpaddr63",
            "mcycle", "minstret", "mcountinhibit", "mhpmcounter3", "mhpmevent3", "hpmcounter3",
            "mcounteren", "scounteren", "hcounteren",
            "miselect", "mireg0", "siselect", "sireg0",
            "dcsr", "dpc",
            "cycle", "instret", "time", "vlenb", "vcountinhibit"
        ]
    
    # Test items per category
    items_to_analyze = {
        "csr": get_comprehensive_csr_sample(),
        "param": ["mhartid", "mcountinhibit"],
        "ext": ["m", "f", "d", "v"],
        "inst": ["add", "load", "store", "branch"],
        "exception_code": ["0", "1", "2"],
        "interrupt_code": ["1", "5", "9"],
        "profile": ["rvi", "rva", "rvm"]
    }
    
    items = items_to_analyze.get(category, [])
    
    # Aggregate metrics
    aggregate_metrics = {
        "timestamp": datetime.now().isoformat(),
        "category": category,
        "total_items": 0,
        "successful_items": 0,
        "total_llm1_params": 0,
        "total_llm2_params": 0,
        "total_unique_params": 0,
        "total_novel": 0,
        "total_agreement": 0,
        "all_novel_params": set(),
        "item_results": {},
        "aggregate_metrics_10": {}
    }
    
    print(f"\nProcessing items in category '{category}'...")
    for item_name in items:
        llm_results = load_llm_results(category, item_name)
        if not llm_results:
            continue
        
        # Compare with comprehensive metrics
        metrics = compare_results(llm_results, known_params, baseline_params)
        save_comparison(category, item_name, metrics)
        
        # Print comparison
        llm1_total = metrics['llm1_total']
        llm2_total = metrics['llm2_total']
        agreement = metrics['total_agreement']
        llm1_only = metrics['llm1_only']
        llm2_only = metrics['llm2_only']
        
        print(f"  {item_name}: openai/gpt-oss-120b({llm1_total}), meta-llama/scout({llm2_total}), Agreement({agreement}), oss-only({llm1_only}), scout-only({llm2_only})")
        
        # Aggregate
        aggregate_metrics["total_items"] += 1
        aggregate_metrics["successful_items"] += 1
        aggregate_metrics["total_llm1_params"] += metrics["llm1_total"]
        aggregate_metrics["total_llm2_params"] += metrics["llm2_total"]
        aggregate_metrics["total_unique_params"] += metrics["total_unique"]
        aggregate_metrics["total_novel"] += len(metrics["llm1_novel_params"]) + len(metrics["llm2_novel_params"])
        aggregate_metrics["total_agreement"] += metrics["total_agreement"]
        aggregate_metrics["all_novel_params"].update(metrics["llm1_novel_params"])
        aggregate_metrics["all_novel_params"].update(metrics["llm2_novel_params"])
        aggregate_metrics["item_results"][item_name] = metrics
    
    # Calculate aggregate metrics
    total_params = aggregate_metrics["total_unique_params"]
    if total_params > 0:
        aggregate_metrics["aggregate_metrics_10"] = {
            "metric_1_novelty_percent": round(aggregate_metrics["total_novel"] / (aggregate_metrics["total_llm1_params"] + aggregate_metrics["total_llm2_params"]) * 100, 2) if (aggregate_metrics["total_llm1_params"] + aggregate_metrics["total_llm2_params"]) > 0 else 0,
            "metric_6_llm_agreement_percent": round(aggregate_metrics["total_agreement"] / total_params * 100, 2),
            "item_count": aggregate_metrics["successful_items"],
            "unique_novel_params": len(aggregate_metrics["all_novel_params"])
        }
    
    # Print summary
    print(f"\nComparison Summary for category '{category}':")
    print(f"  Total items: {aggregate_metrics['successful_items']}")
    print(f"  openai/gpt-oss-120b total: {aggregate_metrics['total_llm1_params']}")
    print(f"  meta-llama/llama-4-scout-17b-16e-instruct total: {aggregate_metrics['total_llm2_params']}")
    print(f"  Total unique: {aggregate_metrics['total_unique_params']}")
    print(f"  Agreement: {aggregate_metrics['total_agreement']}")
    
    novelty = aggregate_metrics["aggregate_metrics_10"].get("metric_1_novelty_percent", 0)
    agreement = aggregate_metrics["aggregate_metrics_10"].get("metric_6_llm_agreement_percent", 0)
    
    print(f"\nMetrics:")
    print(f"  Novelty: {novelty:.1f}%")
    print(f"  LLM Agreement: {agreement:.1f}%")
    
    # Save aggregate results
    aggregate_file = Path(__file__).parent.parent / "comparison" / category / "AGGREGATE_RESULTS.json"
    aggregate_metrics["all_novel_params"] = list(aggregate_metrics["all_novel_params"])
    with open(aggregate_file, 'w') as f:
        json.dump(aggregate_metrics, f, indent=2)
    
    print(f"\nResults saved to: {aggregate_file}")

if __name__ == "__main__":
    main()
