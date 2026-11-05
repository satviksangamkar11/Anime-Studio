"""Decode saved browser-tool results that contain {"name": "<title>_<hash>_2K.jpg", "data": "data:image/jpeg;base64,..."} into Downloads (exact Flow name)."""
import base64, re, sys
from pathlib import Path

pat = re.compile(r'name\\*"\s*:\s*\\*"([A-Za-z0-9_\-]+_[0-9a-f]+_2K\.jpg)\\*"\s*,\s*\\*"data\\*"\s*:\s*\\*"data:image/jpeg;base64,([A-Za-z0-9+/=]+)')
for f in sys.argv[1:]:
    hits = pat.findall(Path(f).read_text(encoding="utf-8"))
    if not hits:
        print("NO IMAGE", f)
    for name, b64 in hits:
        out = Path(r"C:\Users\Satvik\Downloads") / name
        out.write_bytes(base64.b64decode(b64))
        print(out.name, out.stat().st_size)
