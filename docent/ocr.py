"""
Text extraction. No cloud OCR service, no vendor lock-in:

- Native-text PDFs are read directly with pypdf.
- Scanned PDFs (little or no embedded text) are rasterized page-by-page
  with poppler's `pdftoppm` and read with Tesseract.
- Images go straight to Tesseract.

This is the only place in Docent that touches raw files, so it's the
one module worth keeping boring and dependency-light.
"""
import subprocess
import tempfile
from pathlib import Path

import pytesseract
from PIL import Image
from pypdf import PdfReader

MIN_NATIVE_CHARS_PER_PAGE = 40  # below this, assume the page is a scan


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    return _extract_image(path)


def _extract_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    native_pages = [page.extract_text() or "" for page in reader.pages]

    needs_ocr = [
        i for i, text in enumerate(native_pages)
        if len(text.strip()) < MIN_NATIVE_CHARS_PER_PAGE
    ]

    if not needs_ocr:
        return "\n\n".join(native_pages).strip()

    # Mixed or fully scanned document: rasterize the pages that lack
    # usable native text and OCR just those.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        prefix = tmp_path / "page"
        subprocess.run(
            ["pdftoppm", "-r", "300", "-png", str(path), str(prefix)],
            check=True,
            capture_output=True,
        )
        rasterized = sorted(tmp_path.glob("page-*.png"))

        for i in needs_ocr:
            if i < len(rasterized):
                native_pages[i] = pytesseract.image_to_string(Image.open(rasterized[i]))

    return "\n\n".join(native_pages).strip()


def _extract_image(path: Path) -> str:
    return pytesseract.image_to_string(Image.open(path)).strip()
