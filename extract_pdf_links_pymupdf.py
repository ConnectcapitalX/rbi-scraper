import fitz  # PyMuPDF
import os
import json

pdf_path = "downloads/NT105ML28112019.pdf"
out_dir = "extracted_circulars/NT105ML28112019"
os.makedirs(out_dir, exist_ok=True)
links_path = os.path.join(out_dir, "links.json")

doc = fitz.open(pdf_path)
all_links = []

for page_num in range(len(doc)):
    page = doc[page_num]
    for link in page.get_links():
        if link.get("uri"):
            # Get the text near the link rectangle
            rect = fitz.Rect(link["from"])
            words = page.get_text("words")
            context = ""
            for w in words:
                word_rect = fitz.Rect(w[:4])
                if rect.intersects(word_rect):
                    context += w[4] + " "
            all_links.append({
                "url": link["uri"],
                "page": page_num + 1,
                "context": context.strip()
            })

with open(links_path, "w") as f:
    json.dump(all_links, f, indent=2)

print(f"Extracted {len(all_links)} links to {links_path}") 