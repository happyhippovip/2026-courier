#!/usr/bin/env python3
import os
import json
import glob
from pathlib import Path

# Anchor to the repository tree holding this script so the tool behaves
# identically regardless of the caller's working directory.
REPO_ROOT = Path(__file__).resolve().parent.parent

def chunk_markdown(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Very basic chunking by headers
    chunks = []
    current_chunk = []
    for line in content.split('\n'):
        if line.startswith('#'):
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
        current_chunk.append(line)
    if current_chunk:
        chunks.append("\n".join(current_chunk))
        
    return chunks

def main(root=None):
    base = Path(root) if root is not None else REPO_ROOT
    doc_files = sorted(glob.glob(str(base / "docs" / "*.md")))
    output_records = []
    
    for f in doc_files:
        chunks = chunk_markdown(f)
        rel = str(Path(f).relative_to(base))
        for i, chunk in enumerate(chunks):
            if chunk.strip():
                output_records.append({
                    "id": f"{os.path.basename(f)}_chunk_{i}",
                    "source": rel,
                    "content": chunk.strip()
                })
                
    output_file = base / "docs" / "ingestion_ready.jsonl"
    with open(output_file, "w", encoding="utf-8") as out:
        for record in output_records:
            out.write(json.dumps(record) + "\n")
            
    print(f"Ingested {len(doc_files)} files into {len(output_records)} chunks -> {output_file}")

if __name__ == "__main__":
    main()
