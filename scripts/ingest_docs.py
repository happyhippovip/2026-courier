#!/usr/bin/env python3
import os
import json
import glob
from pathlib import Path

def source_label(path: str) -> str:
    """Store source paths with forward slashes on every host.

    ``Path.as_posix()`` only rewrites the local separator, so a Windows
    ``docs\\note.md`` string stays unchanged when the test runs on Linux.
    """
    return str(path).replace("\\", "/")


def _refuse_symlink(path: Path) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("refusing to follow a symlink")

def chunk_markdown(file_path):
    path = Path(file_path)
    _refuse_symlink(path)
    with open(path, "r", encoding="utf-8") as f:
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

def main():
    docs = Path("docs")
    output_file = docs / "ingestion_ready.jsonl"
    _refuse_symlink(docs)
    _refuse_symlink(output_file)
    doc_files = glob.glob("docs/*.md")
    output_records = []
    
    for f in doc_files:
        chunks = chunk_markdown(f)
        for i, chunk in enumerate(chunks):
            if chunk.strip():
                output_records.append({
                    "id": f"{os.path.basename(f)}_chunk_{i}",
                    "source": source_label(f),
                    "content": chunk.strip()
                })
                
    _refuse_symlink(output_file)
    with open(output_file, "w", encoding="utf-8") as out:
        for record in output_records:
            out.write(json.dumps(record) + "\n")
            
    print(f"Ingested {len(doc_files)} files into {len(output_records)} chunks -> {output_file}")

if __name__ == "__main__":
    main()
