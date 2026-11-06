"""Nemotron Ultra review through the 14-key scheduler (free). usage: python nemotron_review.py PROMPT_FILE OUT FILE..."""
import sys
from pathlib import Path
sys.path.insert(0, "flow/scripts")
import dots_coder as c
prompt = Path(sys.argv[1]).read_text(encoding="utf-8")
parts = [prompt, "Think briefly, then give the answer after a line that says exactly FINAL:"]
for f in sys.argv[3:]:
    t = Path(f).read_text(encoding="utf-8", errors="replace")[:120000]
    parts.append(f"=== FILE {f} ===\n" + "\n".join(f"{i}: {l}" for i, l in enumerate(t.splitlines(), 1)))
out = c.nemotron_ask("\n\n".join(parts))
Path(sys.argv[2]).write_text(out, encoding="utf-8")
print("written", len(out))
