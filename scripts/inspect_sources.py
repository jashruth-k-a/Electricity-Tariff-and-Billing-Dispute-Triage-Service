"""Read-only helper to locate reference passages in downloaded primary sources."""
from pypdf import PdfReader

for filename, terms in [("tariff", ["tailoring", "more than one", "higher tariff"]),
                        ("supply", ["different purposes", "change of use", "42.05"])]:
    reader = PdfReader(f"data/raw/{filename}.pdf")
    print(filename, "pages", len(reader.pages))
    pages = range(max(0, len(reader.pages) - 150), len(reader.pages)) if filename == "tariff" else range(len(reader.pages))
    for number in pages:
        text = reader.pages[number].extract_text() or ""
        if any(term in text.lower() for term in terms):
            print("PDF PAGE", number + 1)
            print(text[:10000].encode("ascii", errors="replace").decode())
