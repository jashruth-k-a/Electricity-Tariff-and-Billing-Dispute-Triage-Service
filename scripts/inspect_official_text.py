"""Extract the downloaded sources page by page, retaining page numbers for review."""
import json
from pathlib import Path

from pypdf import PdfReader

directory = Path("data/research")
stats = []
for path in sorted(directory.glob("*.pdf")):
    reader = PdfReader(path)
    pages = [{"page": i, "text": page.extract_text() or ""} for i, page in enumerate(reader.pages, 1)]
    (directory / (path.stem + ".pages.json")).write_text(json.dumps(pages, indent=2), encoding="utf-8")
    (directory / (path.stem + ".txt")).write_text("\n\n".join(
        f"PDF PAGE {p['page']}\n{p['text']}" for p in pages), encoding="utf-8")
    result = {"file": path.name, "pages": len(pages), "characters": sum(len(p["text"]) for p in pages)}
    stats.append(result)
    print(json.dumps(result), flush=True)
(directory / "text-statistics.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
