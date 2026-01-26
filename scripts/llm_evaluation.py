import os
import json
import yaml
import time
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
from huggingface_hub import InferenceClient
from difflib import SequenceMatcher
import sys

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path, override=True)

class LLMTester:
    def __init__(self, category: str = "csr"):
        """Initialize HuggingFace + Groq models for evaluation"""
        self.category = category.lower()
        
        # Load HuggingFace API key
        self.hf_token = os.getenv("HUGGINGFACE_API_KEY")
        if not self.hf_token:
            print("ERROR: HUGGINGFACE_API_KEY not found in .env")
            sys.exit(1)
        
        # Initialize HuggingFace InferenceClient (model 1)
        self.hf_client = InferenceClient(api_key=self.hf_token)
        
        # Load all 9 Groq API keys for model 2
        self.api_keys = []
        for i in range(1, 10):
            key = os.getenv(f"GROQ_API_KEY_{i}")
            if key:
                self.api_keys.append(key)
        
        if not self.api_keys:
            print("ERROR: No API keys found in .env (GROQ_API_KEY_1 through GROQ_API_KEY_9)")
            sys.exit(1)
        
        # Validate category
        valid_categories = ["csr", "param", "ext", "inst", "exception_code", "interrupt_code", "profile"]
        if self.category not in valid_categories:
            raise ValueError(f"Invalid category: {category}. Must be one of {valid_categories}")
        
        # Initialize Groq clients with all API keys (model 2)
        self.groq_clients = [Groq(api_key=key) for key in self.api_keys]
        self.current_client_idx = 0  # For round-robin rotation
        
        # Per-model delays to avoid rate limits
        self.model_delays = {
            "openai/gpt-oss-120b": 3.0,
            "meta-llama/llama-4-scout-17b-16e-instruct": 5.0
        }
        
        print(f"Initialized LLM evaluation for category: {self.category}")
        print(f" openai/gpt-oss-120b (HuggingFace) -- model 1")
        print(f" meta-llama/llama-4-scout-17b-16e-instruct (Groq) -- model 2")
    
    def get_next_groq_client(self):
        """Get next Groq client in round-robin rotation"""
        client = self.groq_clients[self.current_client_idx]
        self.current_client_idx = (self.current_client_idx + 1) % len(self.groq_clients)
        return client
    
    def load_prompt(self):
        """Load category-specific prompt"""
        prompt_path = Path(__file__).parent.parent / "prompts" / f"PROMPT_{self.category.upper()}.md"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt not found: {prompt_path}")
        with open(prompt_path) as f:
            return f.read()
    
    def _ensemble_vote(self, results_list, threshold=1):
        """Ensemble voting: keep parameters appearing in ≥threshold result sets"""
        from collections import defaultdict
        
        param_votes = defaultdict(int)
        param_details = {}
        
        # Count votes for each parameter by name
        for result_set in results_list:
            if not isinstance(result_set, list):
                continue
            seen_names = set()
            for param in result_set:
                if isinstance(param, dict) and "name" in param:
                    name = param["name"]
                    if name not in seen_names:
                        param_votes[name] += 1
                        seen_names.add(name)
                        # Keep the first occurrence of each param
                        if name not in param_details:
                            param_details[name] = param
        
        # Filter by threshold
        voted_params = [param_details[name] for name in param_votes 
                       if param_votes[name] >= threshold]
        
        return voted_params
    
    def _fuzzy_match_names(self, name1: str, name2: str, threshold: float = 0.75) -> bool:
        """Check if two parameter names are semantically similar"""
        if name1 == name2:
            return True
        parts1 = name1.split('_')
        parts2 = name2.split('_')
        if len(parts1) >= 2 and len(parts2) >= 2:
            if parts1[0] == parts2[0] and parts1[1] == parts2[1]:
                return True
        similarity = SequenceMatcher(None, name1, name2).ratio()
        return similarity >= threshold
    
    def _fuzzy_match_parameters(self, llm1_params, llm2_params):
        """Match parameters across models using fuzzy matching"""
        llm1_dict = {p.get("name"): p for p in llm1_params if isinstance(p, dict) and "name" in p}
        llm2_dict = {p.get("name"): p for p in llm2_params if isinstance(p, dict) and "name" in p}
        
        matched_pairs = []
        llm1_matched = set()
        llm2_matched = set()
        for name1, param1 in llm1_dict.items():
            best_match = None
            best_score = 0
            
            for name2, param2 in llm2_dict.items():
                if name2 in llm2_matched:
                    continue
                
                if name1 == name2:
                    matched_pairs.append((param1, param2))
                    llm1_matched.add(name1)
                    llm2_matched.add(name2)
                    break
                
                    # CSR+FIELD prefix match
                parts1 = name1.split('_')
                parts2 = name2.split('_')
                if (len(parts1) >= 2 and len(parts2) >= 2 and
                    parts1[0] == parts2[0] and parts1[1] == parts2[1]):
                    if not best_match:
                        best_match = (name2, param2)
                        best_score = 0.9
                
                # Sequence similarity fallback
                if not best_match or best_score < 0.85:
                    similarity = SequenceMatcher(None, name1, name2).ratio()
                    if similarity >= 0.75 and similarity > best_score:
                        best_match = (name2, param2)
                        best_score = similarity
            
            if best_match:
                matched_pairs.append((param1, best_match[1]))
                llm1_matched.add(name1)
                llm2_matched.add(best_match[0])
        
        return matched_pairs, llm1_matched, llm2_matched
    
    def load_spec_section(self, item_name: str):
        """Load specification text for any category"""
        spec_dir = Path(__file__).parent.parent / "spec/std/isa" / self.category
        spec_path = spec_dir / f"{item_name}.yaml"
        
        # If not found in root, search in subdirectories
        if not spec_path.exists():
            found_paths = list(spec_dir.glob(f"**/{item_name}.yaml"))
            if found_paths:
                spec_path = found_paths[0]
            else:
                return None
        
        with open(spec_path) as f:
            data = yaml.safe_load(f)
        
        if not data:
            return None
        
        # Build spec text based on category
        if self.category == "csr":
            return self._format_csr_spec(data)
        elif self.category == "param":
            return self._format_param_spec(data)
        elif self.category == "ext":
            return self._format_ext_spec(data)
        elif self.category == "inst":
            return self._format_inst_spec(data)
        elif self.category == "exception_code":
            return self._format_exception_spec(data)
        elif self.category == "interrupt_code":
            return self._format_interrupt_spec(data)
        elif self.category == "profile":
            return self._format_profile_spec(data)
        
        return None
    
    def _format_csr_spec(self, data):
        """Format CSR specification text with token limit"""
        spec_text = f"""
CSR Register: {data.get('name', 'unknown').upper()}
Address: 0x{data.get('address', 0):x}
Privilege Mode: {data.get('priv_mode', '')}
Length: {data.get('length', '')}

Description:
{data.get('description', '')}

Fields:
"""
        if 'fields' in data:
            for field_name, field_info in data['fields'].items():
                spec_text += f"\n{field_name}:\n"
                spec_text += f"  Description: {field_info.get('description', '')[:150]}\n"
                spec_text += f"  Type: {field_info.get('type', 'RW')}\n"
        
        # Truncate based on model to avoid token limits
        max_chars = 2000
        if len(spec_text) > max_chars:
            spec_text = spec_text[:max_chars] + "\n\n[... specification truncated ...]"
        
        return spec_text
    
    def _format_param_spec(self, data):
        """Format parameter specification text"""
        spec_text = f"""
Parameter: {data.get('name', 'unknown').upper()}
Long Name: {data.get('long_name', '')}
Type: {data.get('type', 'unknown')}

Description:
{data.get('description', '')}

Constraints:
{data.get('constraints', 'None specified')}

Legal Values:
{data.get('legal_values', 'Implementation dependent')}
"""
        return spec_text
    
    def _format_ext_spec(self, data):
        """Format extension specification text"""
        spec_text = f"""
Extension: {data.get('name', 'unknown').upper()}
Long Name: {data.get('long_name', '')}
Version: {data.get('version', '')}
Defines: {data.get('defines', 'See description')}

Description:
{data.get('description', '')}

Dependencies:
{data.get('dependencies', 'None')}
"""
        return spec_text
    
    def _format_inst_spec(self, data):
        """Format instruction specification text"""
        spec_text = f"""
Instruction: {data.get('name', 'unknown').upper()}
Long Name: {data.get('long_name', '')}
Mnemonic: {data.get('mnemonic', '')}
Type: {data.get('inst_type', '')}

Description:
{data.get('description', '')}

Operands:
{data.get('operands', 'See specification')}

Encoding:
{data.get('encoding', 'See specification')}

Behavior:
{data.get('behavior', 'See specification')}
"""
        return spec_text
    
    def _format_exception_spec(self, data):
        """Format exception code specification text"""
        spec_text = f"""
Exception Code: {data.get('code', 'unknown')}
Name: {data.get('name', 'unknown').upper()}
Description:
{data.get('description', '')}

Trap Behavior:
{data.get('trap_behavior', 'See specification')}

Privilege Level:
{data.get('priv_level', 'See specification')}
"""
        return spec_text
    
    def _format_interrupt_spec(self, data):
        """Format interrupt code specification text"""
        spec_text = f"""
Interrupt Code: {data.get('code', 'unknown')}
Name: {data.get('name', 'unknown').upper()}
Description:
{data.get('description', '')}

Handler Behavior:
{data.get('handler_behavior', 'See specification')}

Privilege Level:
{data.get('priv_level', 'See specification')}
"""
        return spec_text
    
    def _format_profile_spec(self, data):
        """Format profile specification text"""
        spec_text = f"""
Profile: {data.get('name', 'unknown').upper()}
Long Name: {data.get('long_name', '')}
Description:
{data.get('description', '')}

Required Extensions:
{data.get('required_extensions', 'See specification')}

Optional Extensions:
{data.get('optional_extensions', 'See specification')}

Constraints:
{data.get('constraints', 'None specified')}
"""
        return spec_text
    
    def call_huggingface(self, model: str, prompt: str, spec_text: str, temperature: float = 0.2, max_retries: int = 3) -> list:
        """Call HuggingFace Inference API"""
        for attempt in range(max_retries):
            try:
                # Add explicit JSON formatting instructions
                json_instruction = "CRITICAL: You MUST respond with ONLY a valid JSON array. Start with [ and end with ]. No markdown, no explanations, no code blocks."
                full_prompt = f"{json_instruction}\n\n{prompt}\n\n[SPECIFICATION TEXT]\n{spec_text}\n\nOutput format: [object1, object2, ...]"
                
                # Use streaming to handle large responses better
                response_text = ""
                try:
                    for message in self.hf_client.chat_completion(
                        model=model,
                        messages=[
                            {"role": "system", "content": "You are a JSON extraction expert. You MUST respond with ONLY valid JSON arrays. Do not include markdown, explanations, or any text outside the JSON array."},
                            {"role": "user", "content": full_prompt}
                        ],
                        max_tokens=2048,
                        temperature=temperature,
                        stream=True,
                    ):
                        # Handle different response structures
                        try:
                            if hasattr(message, 'choices') and len(message.choices) > 0:
                                if hasattr(message.choices[0], 'delta') and hasattr(message.choices[0].delta, 'content'):
                                    if message.choices[0].delta.content:
                                        response_text += message.choices[0].delta.content
                                elif hasattr(message.choices[0], 'text'):
                                    response_text += message.choices[0].text
                        except (IndexError, AttributeError) as e:
                            # Silently continue on parsing issues
                            continue
                except Exception as stream_error:
                    # If streaming fails, try non-streaming
                    print(f"    [{model}] Streaming failed, retrying non-streaming...")
                    response = self.hf_client.chat_completion(
                        model=model,
                        messages=[
                            {"role": "system", "content": "You are a JSON extraction expert. You MUST respond with ONLY valid JSON arrays. Do not include markdown, explanations, or any text outside the JSON array."},
                            {"role": "user", "content": full_prompt}
                        ],
                        max_tokens=2048,
                        temperature=temperature,
                        stream=False,
                    )
                    if hasattr(response, 'choices') and len(response.choices) > 0:
                        response_text = response.choices[0].message.content
                    else:
                        response_text = str(response)
                
                response_text = response_text.strip()
                
                # Try to extract JSON from response
                try:
                    # Remove markdown code
                    if "```json" in response_text:
                        response_text = response_text.replace("```json", "").replace("```", "").strip()
                    elif "```" in response_text:
                        response_text = response_text.replace("```", "").strip()
                    
                    # Find JSON array boundaries
                    json_start = response_text.find('[')
                    json_end = response_text.rfind(']') + 1
                    
                    if json_start < 0:
                        print(f"    [{model}] No '[' found in response")
                        # Maybe it's just raw objects, try to wrap it
                        if response_text.strip().startswith('{'):
                            response_text = '[' + response_text + ']'
                            json_start = 0
                            json_end = len(response_text)
                        else:
                            print(f"    [{model}] Cannot parse response: {response_text[:200]}")
                            return []
                    
                    if json_start >= 0:
                        if json_end <= json_start:
                            json_str = response_text[json_start:] + "]"
                        else:
                            json_str = response_text[json_start:json_end]
                        
                        try:
                            result = json.loads(json_str)
                            print(f"    [{model}] Extracted {len(result)} parameters")
                            return result
                        except json.JSONDecodeError as parse_err:
                            # Try to fix common JSON issues
                            try:
                                json_str = json_str.rstrip(',') + "]"
                                result = json.loads(json_str)
                                print(f"    [{model}] Extracted {len(result)} parameters (fixed JSON)")
                                return result
                            except json.JSONDecodeError:
                                import re
                                # Try to extract individual JSON objects
                                objects = re.findall(r'\{[^{}]*\}', json_str)
                                if objects:
                                    valid_objects = []
                                    for obj_str in objects:
                                        try:
                                            valid_objects.append(json.loads(obj_str))
                                        except:
                                            pass
                                    if valid_objects:
                                        print(f"    [{model}] Extracted {len(valid_objects)} parameters (recovered)")
                                        return valid_objects
                                print(f"    [{model}] JSON parse failed: {str(parse_err)[:100]}")
                                return []
                    else:
                        print(f"    [{model}] No JSON array found in response")
                        return []
                except Exception as json_err:
                    print(f"    [{model}] JSON extraction error: {str(json_err)[:100]}")
                    return []
            
            except Exception as e:
                error_str = str(e)
                
                # Handle rate limits
                if "429" in error_str or "rate limit" in error_str.lower():
                    wait_time = min(2 ** (attempt + 1), 30)
                    print(f"    [{model}] Rate limited - attempt {attempt+1}/{max_retries}")
                    print(f"    [{model}] Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                # Handle quota errors
                if "quota" in error_str.lower():
                    print(f"    [{model}] Quota exceeded")
                    return []
                
                # Handle token limit errors
                if "413" in error_str or "too large" in error_str.lower():
                    print(f"    [{model}] Request too large (token limit)")
                    return []
                
                print(f"    [{model}] Error: {error_str[:150]}")
                return []
            
            except Exception as e:
                error_str = str(e)
                
                # Handle rate limits
                if "429" in error_str or "rate limit" in error_str.lower():
                    wait_time = min(2 ** (attempt + 1), 30)
                    print(f"    [{model}] Rate limited - attempt {attempt+1}/{max_retries}")
                    print(f"    [{model}] Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                # Handle quota errors
                if "quota" in error_str.lower():
                    print(f"    [{model}] Quota exceeded")
                    return []
                
                # Handle token limit errors
                if "413" in error_str or "too large" in error_str.lower():
                    print(f"    [{model}] Request too large (token limit)")
                    return []
                
                print(f"    [{model}] Error: {error_str[:150]}")
                return []
        
        print(f"    [{model}] [FAILED] Max retries ({max_retries}) exceeded")
        return []
    
    def call_groq(self, model: str, prompt: str, spec_text: str, temperature: float = 0.2, max_retries: int = 3) -> list:
        """Call Groq API with exponential backoff retry and API key rotation on rate limits"""
        
        for attempt in range(max_retries):
            try:
                # Switch API key on 429 errors (more aggressive rotation)
                client = self.get_next_groq_client()
                spec_size = len(spec_text)
                
                full_prompt = f"{prompt}\n\n[INSERT SPECIFICATION TEXT HERE]\n{spec_text}\n\nRESPOND WITH ONLY A JSON ARRAY, NO OTHER TEXT OR EXPLANATION."
                
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a JSON extraction expert. Respond ONLY with valid JSON arrays, no markdown formatting, no explanations, no code blocks."},
                        {"role": "user", "content": full_prompt}
                    ],
                    max_tokens=1024,
                    temperature=temperature,
                )
                
                response_text = response.choices[0].message.content.strip()
                
                # Try to extract JSON from response
                try:
                    # Remove markdown code
                    if "```json" in response_text:
                        response_text = response_text.replace("```json", "").replace("```", "").strip()
                    elif "```" in response_text:
                        response_text = response_text.replace("```", "").strip()
                    
                    json_start = response_text.find('[')
                    json_end = response_text.rfind(']') + 1
                    
                    if json_start >= 0:
                        if json_end <= json_start:
                            json_str = response_text[json_start:] + "]"
                        else:
                            json_str = response_text[json_start:json_end]
                        
                        try:
                            result = json.loads(json_str)
                            print(f"    [{model}] Extracted {len(result)} parameters")
                            return result
                        except json.JSONDecodeError:
                            # Try to fix common JSON issues
                            try:
                                # Remove trailing comma before closing bracket
                                json_str = json_str.rstrip(',') + "]"
                                result = json.loads(json_str)
                                print(f"    [{model}] Extracted {len(result)} parameters (fixed JSON)")
                                return result
                            except json.JSONDecodeError:
                                # Try to extract valid JSON objects from the malformed string
                                import re
                                objects = re.findall(r'\{[^}]*\}', json_str)
                                if objects:
                                    valid_objects = []
                                    for obj_str in objects:
                                        try:
                                            valid_objects.append(json.loads(obj_str))
                                        except:
                                            pass
                                    if valid_objects:
                                        print(f"    [{model}] Extracted {len(valid_objects)} parameters (recovered from malformed JSON)")
                                        return valid_objects
                                raise
                    else:
                        print(f"    [{model}] No JSON array found in response")
                        return []
                except json.JSONDecodeError as e:
                    print(f"    [{model}] JSON parse error: {str(e)[:100]}")
                    return []
            
            except Exception as e:
                error_str = str(e)
                
                # Handle rate limit errors - switch API key and add exponential backoff
                if "429" in error_str or "rate limit" in error_str.lower() or "too many requests" in error_str.lower():
                    wait_time = min(2 ** (attempt + 1), 30)  # 2s, 4s, 8s, max 30s
                    print(f"    [{model}] Rate limited (429) - attempt {attempt+1}/{max_retries}")
                    print(f"    [{model}] Switching API key and waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                # Handle quota errors
                if "quota" in error_str.lower():
                    print(f"    [{model}] Quota exceeded - check API billing")
                    return []
                
                # Handle token limit errors
                if "413" in error_str or "too large" in error_str.lower():
                    print(f"    [{model}] Request too large (token limit)")
                    return []
                
                print(f"    [{model}] Error: {error_str[:150]}")
                return []
        
        print(f"    [{model}] [FAILED] Max retries ({max_retries}) exceeded")
        return []
    
    def test_item(self, item_name: str, num_calls_per_model: int = 1):
        """Test extraction with HuggingFace (model 1) and Groq Scout (model 2)"""
        print(f"\nEvaluating: {self.category}/{item_name}")
        
        # Load resources
        try:
            prompt = self.load_prompt()
            spec_text = self.load_spec_section(item_name)
        except Exception as e:
            print(f"[ERROR] Failed to load resources: {e}")
            return None
        
        if not spec_text:
            print(f"[ERROR] Item {item_name} not found in {self.category}")
            return None
        
        # Models
        model_hf = "openai/gpt-oss-120b"
        model_scout = "meta-llama/llama-4-scout-17b-16e-instruct"
        
        temperatures = [0.0, 0.2, 0.5][:num_calls_per_model]
        
        # Collect results from both models
        hf_results = []
        scout_results = []
        
        for i, temp in enumerate(temperatures):
            print(f"  Call {i+1}/{num_calls_per_model} (temperature={temp}):")
            
            # Call HuggingFace model 1
            print(f"    Calling model 1 (HuggingFace)")
            result_hf = self.call_huggingface(model_hf, prompt, spec_text, temperature=temp)
            hf_results.append(result_hf)
            
            # Wait between calls
            delay = self.model_delays[model_hf]
            print(f"    Waiting {delay}s")
            time.sleep(delay)
            
            # Call Scout model 2 (Groq)
            print(f"    Calling model 2 (Groq Scout)")
            result_scout = self.call_groq(model_scout, prompt, spec_text, temperature=temp)
            scout_results.append(result_scout)
            
            # Wait before next iteration
            if i < num_calls_per_model - 1:
                delay = self.model_delays[model_scout]
                print(f"    Waiting {delay}s before next call...")
                time.sleep(delay)
        
        # Ensemble voting within each model
        hf_voted = self._ensemble_vote(hf_results, threshold=1)
        scout_voted = self._ensemble_vote(scout_results, threshold=1)
        
        hf_count = len(hf_voted) if isinstance(hf_voted, list) else 0
        scout_count = len(scout_voted) if isinstance(scout_voted, list) else 0
        
        # Calculate convergence percentage using fuzzy matching
        matched_pairs = []
        if hf_voted and scout_voted:
            hf_names = [p.get("name") for p in hf_voted if isinstance(p, dict) and "name" in p]
            scout_names = [p.get("name") for p in scout_voted if isinstance(p, dict) and "name" in p]
            
            matched = set()
            for hf_name in hf_names:
                for scout_name in scout_names:
                    if scout_name not in matched and self._fuzzy_match_names(hf_name, scout_name, threshold=0.7):
                        matched_pairs.append((hf_name, scout_name))
                        matched.add(scout_name)
                        break
        
        total_unique = hf_count + scout_count - len(matched_pairs)
        convergence = (len(matched_pairs) / max(hf_count, scout_count) * 100) if max(hf_count, scout_count) > 0 else 0
        
        print(f"\n  Results:")
        print(f"     OpenAI GPT-OSS-120B: {hf_count} parameters")
        print(f"     Groq Scout: {scout_count} parameters")
        print(f"     Matched (fuzzy): {len(matched_pairs)} parameters")
        print(f"     Convergence: {convergence:.1f}%")
        
        # Save results
        output_dir = Path(__file__).parent.parent / "evaluation" / self.category
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results = {
            "category": self.category,
            "item_name": item_name,
            "model_1": model_hf,
            "model_2": model_scout,
            "hf_response": hf_voted,
            "hf_count": hf_count,
            "scout_response": scout_voted,
            "scout_count": scout_count,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "metrics": {
                "hf_extracted": hf_count,
                "scout_extracted": scout_count,
                "total_unique": total_unique,
                "convergence_percentage": round(convergence, 1),
                "fuzzy_matched": len(matched_pairs),
                "matched_pairs": matched_pairs
            }
        }
        
        output_file = output_dir / f"{item_name}_results.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        return results


def discover_csr_files():
    """Discover all CSR files from spec directory"""
    csr_dir = Path(__file__).parent.parent / "spec/std/isa/csr"
    csr_files = []
    if csr_dir.exists():
        for yaml_file in csr_dir.glob("**/*.yaml"):
            csr_name = yaml_file.stem
            csr_files.append(csr_name)
    return sorted(csr_files)

def get_comprehensive_csr_sample():
    """Return quick sample covering key CSR domains"""
    return [
        # Machine-Level (1)
        "mepc",
        
        # Supervisor-Level (1)
        "sstatus",
        
        # Hypervisor (1)
        "hstatus",
        
        # Floating-Point (F extension) (1)
        "frm",
        
        # Vector (V extension) (1)
        "vtype",
        
        # Address Translation (1)
        "satp",
        
        # Physical Memory Protection (1)
        "pmpcfg0",
        
        # Counters (1)
        "mcycle",
        
        # Indirect CSR Access (1)
        "miselect",
        
        # Debug (1)
        "dcsr"
    ]

if __name__ == "__main__":
    # Parse command line arguments
    category = "csr"
    custom_items = None
    
    if len(sys.argv) > 1:
        category = sys.argv[1]
    if len(sys.argv) > 2:
        custom_items = sys.argv[2:]
    
    # Setup evaluation directory
    eval_dir = BASE_DIR / "evaluation" / category
    eval_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize tester
    tester = LLMTester(category=category)
    
    # Determine items to evaluate
    if category == "csr" and custom_items is None:
        items = get_comprehensive_csr_sample()
    elif custom_items:
        items = custom_items
    else:
        items_to_test = {
            "csr": get_comprehensive_csr_sample(),
            "param": ["mhartid", "mcountinhibit"],
            "ext": ["m", "f", "d", "v"],
            "inst": ["add", "load", "store", "branch"],
            "exception_code": ["0", "1", "2"],
            "interrupt_code": ["1", "5", "9"],
            "profile": ["rvi", "rva", "rvm"]
        }
        items = items_to_test.get(category, [])
    
    if not items:
        print(f"[ERROR] No test items configured for category: {category}")
        sys.exit(1)
    
    # Start evaluation
    print(f"{'='*80}")
    print(f"Starting evaluation: {category}")
    print(f"{'='*80}\n")
    
    results = []
    failed = []
    
    for idx, item in enumerate(items, 1):
        print(f"[{idx}/{len(items)}] Evaluation: {item}")
        result_data = tester.test_item(item, num_calls_per_model=1)
        
        if result_data:
            results.append(item)
        else:
            failed.append(item)
        
        # Save results
        output_file = eval_dir / f"{item}_results.json"
        with open(output_file, "w") as f:
            json.dump(result_data, f, indent=2)
        print(f"  Results saved to: {output_file}")
        
        if idx < len(items):
            time.sleep(3)
    
    # Summary
    print(f"\n{'='*80}")
    print(f"Evaluation Complete!")
    print(f"[OK] Tested: {len(results)}/{len(items)} items")
    if failed:
        print(f"[FAILED] Failed: {len(failed)} items - {', '.join(failed[:5])}")
    print(f"Results saved to: {eval_dir}")
    print(f"{'='*80}\n")