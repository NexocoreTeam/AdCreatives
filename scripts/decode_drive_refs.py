"""Decode base64 image content from Drive MCP tool-results and save to disk."""
import json
import base64
import os
import sys

tool_results_dir = r"C:\Users\ReadyPlayerOne\.claude\projects\C--Users-ReadyPlayerOne-AdCreatives\7e6ca3be-eb10-43c1-bd2d-68ebf5238dff\tool-results"
out_dir = r"C:\Users\ReadyPlayerOne\AdCreatives\clients\savedbygrace\reference_ads\drive-clothing"

# Specific timestamps from this session's downloads (in download order)
files = [
    ("mcp-cabdba60-ffd5-4eae-9ad7-f741a3f0257a-download_file_content-1779838076824.txt", "11BkeaJatIRj3VMNldwgHvRbtVpohkp3a"),
    ("mcp-cabdba60-ffd5-4eae-9ad7-f741a3f0257a-download_file_content-1779838080862.txt", "1mdpf5_XOpItKRwp2JkjB_eszZLbdXr1m"),
    ("mcp-cabdba60-ffd5-4eae-9ad7-f741a3f0257a-download_file_content-1779838086715.txt", "1ukpzpvJmHbsko7LoAH1NFrE9TD0UXgtl"),
    ("mcp-cabdba60-ffd5-4eae-9ad7-f741a3f0257a-download_file_content-1779838091573.txt", "15qQEct2cCvUqcHHgxMQCmEoEdK7LA6Sh"),
    ("mcp-cabdba60-ffd5-4eae-9ad7-f741a3f0257a-download_file_content-1779838095619.txt", "1x_Q9kcQHwldS9sTLpkAJgH2-PepO81s-"),
    ("mcp-cabdba60-ffd5-4eae-9ad7-f741a3f0257a-download_file_content-1779838097427.txt", "1rhPyDhnz9jy-OILZGa5Z_RUpkQ15uqk8"),
    ("mcp-cabdba60-ffd5-4eae-9ad7-f741a3f0257a-download_file_content-1779838099815.txt", "1CA2Qh-bdcvohHm-2rlSJhcWmlQN5nZcD"),
    ("mcp-cabdba60-ffd5-4eae-9ad7-f741a3f0257a-download_file_content-1779838104132.txt", "1PEFpeuDeGJ4NzLxfOB8naPDLgIaKhBNn"),
    ("mcp-cabdba60-ffd5-4eae-9ad7-f741a3f0257a-download_file_content-1779838107748.txt", "143exXZ4iwDw_3GLjgPCaMQqPjb6Q9ihm"),
    ("mcp-cabdba60-ffd5-4eae-9ad7-f741a3f0257a-download_file_content-1779838110848.txt", "1mZI2kTaPK0sVW5mW-79Xn18pMzR2fUmW"),
]

os.makedirs(out_dir, exist_ok=True)
results = []

for fname, expected_id in files:
    fpath = os.path.join(tool_results_dir, fname)
    if not os.path.exists(fpath):
        results.append(f"MISSING file: {fname}")
        continue
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        title = data.get("title", f"{expected_id}.jpg")
        content_b64 = data.get("content", "")
        mime = data.get("mimeType", "")
        file_id = data.get("id", expected_id)
        if file_id != expected_id:
            results.append(f"WARN: ID mismatch in {fname} (expected {expected_id}, got {file_id})")
        # Decode base64
        img_bytes = base64.b64decode(content_b64)
        out_path = os.path.join(out_dir, title)
        with open(out_path, "wb") as out_f:
            out_f.write(img_bytes)
        results.append(f"OK: {expected_id} -> {title} ({len(img_bytes):,} bytes, {mime})")
    except Exception as e:
        results.append(f"FAIL: {fname} -> {e}")

for r in results:
    print(r)
