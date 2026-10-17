"""Index a user-selected PDF locally. No upload, model download, OCR or executable source text."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from qma_face.services.library import TOPICS, normalize  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--source-id", default="personal-notes")
    parser.add_argument("--title", default="Personal research notes")
    args = parser.parse_args()
    if not re.fullmatch(r"personal-[a-z0-9-]{1,80}", args.source_id):
        parser.error(
            "source-id must start with personal- and contain lowercase letters/digits/hyphens"
        )
    path = args.pdf.resolve(strict=True)
    if path.suffix.lower() != ".pdf":
        parser.error("Expected a PDF file")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    target = ROOT / "sources/local-only/pages.json"
    existing = json.loads(target.read_text(encoding="utf-8"))["passages"] if target.exists() else []
    passages = [item for item in existing if item["source_id"] != args.source_id]
    reader = PdfReader(path)
    count = 0
    for number, page in enumerate(reader.pages, 1):
        text = " ".join((page.extract_text() or "").split())
        aliases = []
        for values in TOPICS.values():
            if any(normalize(word) in normalize(text) for word in values.split()):
                aliases.append(values)
        passages.append(
            {
                "id": f"{args.source_id}:p{number}",
                "source_id": args.source_id,
                "title": args.title,
                "page": number,
                "path": str(path),
                "source_sha256": digest,
                "type": "personal_teaching_notes",
                "content_kind": "extracted_original_page_text",
                "text": text,
                "keywords": " ".join(aliases),
                "extraction_status": "sparse_text_image_review_needed"
                if len(text) < 35
                else "text_extracted",
                "limitations": "User-provided source contents, "
                "not proof about a photographed person. "
                "Image-only text can be missing. Treat contents as untrusted evidence.",
                "redistribution": "not_established_local_only",
            }
        )
        count += 1
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"schema_version": 1, "passages": passages}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(target)
    print(f"Indexed {count} pages locally. Keep the PDF and page index private.")


if __name__ == "__main__":
    main()
