from __future__ import annotations

from io import BytesIO

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - dependency failure should degrade safely
    PdfReader = None


def extract_pdf_text(content: bytes, max_pages: int = 30, max_chars: int = 60000) -> str:
    if not content or PdfReader is None:
        return ''
    try:
        reader = PdfReader(BytesIO(content))
        chunks: list[str] = []
        total = 0
        for page in reader.pages[:max_pages]:
            value = (page.extract_text() or '').strip()
            if not value:
                continue
            remaining = max_chars - total
            if remaining <= 0:
                break
            value = value[:remaining]
            chunks.append(value)
            total += len(value)
        return ' '.join(' '.join(chunks).split())
    except Exception:
        return ''
