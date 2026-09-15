import os

def search_in_file(path, terms):
    if not os.path.exists(path):
        return
    with open(path, 'rb') as f:
        # Seek to last 50MB
        f.seek(0, 2)
        size = f.tell()
        start = max(0, size - 50 * 1024 * 1024)
        f.seek(start)
        content = f.read().decode('utf-8', errors='ignore')
        
        for term in terms:
            if term.lower() in content.lower():
                print(f"FOUND {term} in {path}")
                idx = content.lower().find(term.lower())
                print(content[max(0, idx-100):min(len(content), idx+100)])

search_in_file("/Users/user/Library/Logs/Antigravity/language_server.log", ["ptyHost", "BigInt", "serialize a BigInt"])
search_in_file("/Users/user/Library/Logs/Antigravity/main.log", ["ptyHost", "BigInt", "serialize a BigInt"])
