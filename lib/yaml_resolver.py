import glob, os

from copy import deepcopy
from tqdm import tqdm
from ruamel.yaml import YAML
from mergedeep import merge, Strategy

OUT_DIR="arch_resolved"
UDB_ROOT=os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

yaml = YAML(typ="rt")
yaml.default_flow_style = False
yaml.preserve_quotes = True


def read_yaml(file_path):
  with open(file_path, 'r') as file:
    data = yaml.load(file)
  return data

def write_yaml(file_path, data):
  with open(file_path, 'w') as file:
    yaml.dump(data, file)

def dig(obj, *keys):
  if len(keys) == 0:
    return obj

  try:
    next_obj = obj[keys[0]]
    if len(keys) == 1:
      return next_obj
    else:
      return dig(next_obj, *keys[1:])
  except KeyError:
    return None

resolved_objs = {}
def resolve(path, rel_path, arch_root):
  if path in resolved_objs:
    return resolved_objs[path]
  else:
    unresolved_data = read_yaml(path)
    resolved_objs[path] = _resolve(unresolved_data, [], rel_path, unresolved_data, arch_root)
    return resolved_objs[path]

def _resolve(obj, obj_path, obj_file_path, doc_obj, arch_root):
  if not (isinstance(obj, list) or isinstance(obj, dict)):
    return obj

  if isinstance(obj, list):
    obj = list(map(lambda o: _resolve(o, obj_path, obj_file_path, doc_obj, arch_root), obj))
    return obj

  if "$inherits" in obj:
    # handle the inherits key first so that any override will have priority
    inherits_targets = [obj["$inherits"]] if isinstance(obj["$inherits"], str) else obj["$inherits"]
    obj["$child_of"] = obj["$inherits"]

    new_obj = yaml.load("{}")

    for inherits_target in inherits_targets:
      ref_file_path = inherits_target.split("#")[0]
      ref_obj_path = inherits_target.split("#")[1].split("/")[1:]

      ref_obj = None
      if ref_file_path == "":
        ref_file_path = obj_file_path
        # this is a reference in the same document
        ref_obj = dig(doc_obj, *ref_obj_path)
        if ref_obj == None:
          raise ValueError(f"{ref_obj_path} cannot be found in #{doc_obj}")
        ref_obj = _resolve(ref_obj, ref_obj_path, ref_file_path, doc_obj, arch_root)
      else:
        # this is a reference to another doc
        if not os.path.exists(os.path.join(UDB_ROOT, arch_root, ref_file_path)):
          raise ValueError(f"{ref_file_path} does not exist in {arch_root}/")
        ref_file_full_path = os.path.join(UDB_ROOT, arch_root, ref_file_path)

        ref_doc_obj = resolve(ref_file_full_path, ref_file_path, arch_root)
        ref_obj = dig(ref_doc_obj, *ref_obj_path)

        ref_obj = _resolve(ref_obj, ref_obj_path, ref_file_path, ref_doc_obj, arch_root)

      for key in ref_obj:
        if isinstance(new_obj.get(key), dict):
          merge(new_obj[key], ref_obj, strategy=Strategy.REPLACE)
        else:
          new_obj[key] = deepcopy(ref_obj[key])

      print(f"{obj_file_path} {obj_path} inherits {ref_file_path} {ref_obj_path}")
      ref_obj["$parent_of"] = f"{obj_file_path}#/{"/".join(obj_path)}"

    del obj["$inherits"]

    # now new_obj is the child and obj is the parent
    # merge them
    keys = []
    for key in obj.keys():
      keys.append(key)
    for key in new_obj.keys():
      if keys.count(key) == 0:
        keys.append(key)

    final_obj = yaml.load('{}')
    for key in keys:
      if not key in obj:
        final_obj[key] = new_obj[key]
      elif not key in new_obj:
        final_obj[key] = _resolve(obj[key], obj_path + [key], obj_file_path, doc_obj, arch_root)
      else:
        if isinstance(new_obj[key], dict):
          if not isinstance(new_obj[key], dict):
            raise ValueError("should be a hash")
          final_obj[key] = merge(yaml.load('{}'), new_obj[key], obj[key], strategy=Strategy.REPLACE)
        else:
          final_obj[key] = _resolve(obj[key], obj_path + [key], obj_file_path, doc_obj, arch_root)


    return final_obj
  else:
    for key in obj:
      obj[key] = _resolve(obj[key], obj_path + [key], obj_file_path, doc_obj, arch_root)

    return obj

arch_paths = glob.glob("arch/**/*.yaml", recursive=True, root_dir=UDB_ROOT)
for arch_path in tqdm(arch_paths):
  resolved_arch_path = f"{UDB_ROOT}/{OUT_DIR}/{arch_path}"
  os.makedirs(os.path.dirname(resolved_arch_path), exist_ok=True)
  write_yaml(resolved_arch_path, resolve(arch_path, os.path.join(*arch_path.split("/")[1:]), "arch"))
