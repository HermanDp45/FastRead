#!/usr/bin/env python3
"""Embed examples/*.json into index.html so the example buttons work offline from file://.

Usage:  python3 tools/embed_examples.py
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
packs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "examples").glob("*.json"))]
blob = json.dumps(packs, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

html_path = ROOT / "index.html"
html = html_path.read_text(encoding="utf-8")
new, n = re.subn(r"/\*EXAMPLES:BEGIN\*/.*?/\*EXAMPLES:END\*/",
                 lambda _: f"/*EXAMPLES:BEGIN*/{blob}/*EXAMPLES:END*/", html, flags=re.S)
if n != 1:
    raise SystemExit("marker /*EXAMPLES:BEGIN*/ … /*EXAMPLES:END*/ not found in index.html")
html_path.write_text(new, encoding="utf-8")
print(f"embedded {len(packs)} example(s): " + ", ".join(p.get("title", "?") for p in packs))
