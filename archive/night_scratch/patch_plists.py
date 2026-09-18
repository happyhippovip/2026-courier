import xml.etree.ElementTree as ET
import sys
import uuid

plist_files = sys.argv[1:]
api_key = "321606503a874d39b50f6137e3321b7f"
verifier_key = "421606503a874d39b50f6137e3321b7f"

for p in plist_files:
    try:
        tree = ET.parse(p)
        root = tree.getroot()
        dict_node = root.find('dict')
        
        env_dict = None
        
        # Check if EnvironmentVariables exists
        keys = list(dict_node)
        for i, elem in enumerate(keys):
            if elem.tag == 'key' and elem.text == 'EnvironmentVariables':
                env_dict = keys[i+1]
                break
                
        if env_dict is None:
            env_key = ET.Element('key')
            env_key.text = 'EnvironmentVariables'
            dict_node.append(env_key)
            env_dict = ET.Element('dict')
            dict_node.append(env_dict)
            
        def add_env(k, v):
            k_elem = ET.Element('key')
            k_elem.text = k
            v_elem = ET.Element('string')
            v_elem.text = v
            env_dict.append(k_elem)
            env_dict.append(v_elem)
            
        add_env("COURIER_API_KEY", api_key)
        add_env("COURIER_VERIFIER_API_KEY", verifier_key)
        
        with open(p, 'wb') as f:
            tree.write(f, encoding='utf-8', xml_declaration=True)
            
        print(f"Patched {p}")
    except Exception as e:
        print(f"Failed to patch {p}: {e}")
