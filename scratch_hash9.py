import hashlib
import os

with open("coordination/mac_to_windows/archive/REQ-MAC-7B6D8CA4.json", "rb") as f:
    content = f.read()

# Replace LF with CRLF
content_crlf = content.replace(b"\n", b"\r\n")

print(hashlib.sha256(content_crlf).hexdigest())

target = "c7eecb7ae7ce30103bc5ef7a51b7d65af96a9615b74a43f4e232658d71759e42"
if hashlib.sha256(content_crlf).hexdigest() == target:
    print("MATCH!")

