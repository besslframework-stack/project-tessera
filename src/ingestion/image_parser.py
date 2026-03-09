"""Image parser with OCR support.

Extracts text from images using pytesseract (optional dependency).
Falls back to metadata-only Document when OCR is unavailable.

Supported: .png, .jpg, .jpeg, .gif, .bmp, .tiff, .webp
"""

from __future__ import annotations

import logging
from pathlib import Path

from llama_index.core.schema import Document

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp"}


def _try_ocr(file_path: Path) -> str | None:
    """Attempt OCR on an image file using pytesseract.

    Returns extracted text, or None if pytesseract is not available.
    """
    try:
        from PIL import Image
        import pytesseract

        img = Image.open(file_path)

        # Try Korean + English first, fall back to English only
        try:
            text = pytesseract.image_to_string(img, lang="kor+eng")
        except Exception:
            text = pytesseract.image_to_string(img, lang="eng")

        return text.strip() if text.strip() else None

    except ImportError:
        return None
    except Exception as exc:
        logger.debug("OCR failed for %s: %s", file_path, exc)
        return None


def _get_image_metadata(file_path: Path) -> dict:
    """Extract basic image metadata (size, format) using Pillow if available."""
    metadata = {
        "source_path": str(file_path),
        "file_name": file_path.name,
        "file_type": "image",
        "doc_type": "image",
        "file_size_bytes": file_path.stat().st_size if file_path.exists() else 0,
    }

    try:
        from PIL import Image

        img = Image.open(file_path)
        metadata["image_width"] = img.width
        metadata["image_height"] = img.height
        metadata["image_format"] = img.format or file_path.suffix.upper().lstrip(".")
        metadata["image_mode"] = img.mode

        # Extract EXIF data if available
        exif = img.getexif()
        if exif:
            # Common EXIF tags
            exif_tags = {
                270: "image_description",
                315: "image_artist",
                306: "image_datetime",
                271: "image_camera_make",
                272: "image_camera_model",
            }
            for tag_id, key in exif_tags.items():
                if tag_id in exif:
                    val = str(exif[tag_id]).strip()
                    if val:
                        metadata[key] = val[:200]

    except ImportError:
        metadata["image_format"] = file_path.suffix.upper().lstrip(".")
    except Exception as exc:
        logger.debug("Image metadata extraction failed for %s: %s", file_path, exc)

    return metadata


def parse_image_file(file_path: Path) -> list[Document]:
    """Parse an image file into a Document.

    Tries OCR first. If OCR is unavailable or returns no text,
    creates a metadata-only document with filename and image properties.
    """
    metadata = _get_image_metadata(file_path)

    # Try OCR
    ocr_text = _try_ocr(file_path)

    if ocr_text:
        metadata["ocr"] = True
        text = f"[Image: {file_path.name}]\n\n{ocr_text}"
    else:
        metadata["ocr"] = False
        # Create a descriptive text from metadata
        parts = [f"[Image: {file_path.name}]"]
        if "image_width" in metadata:
            parts.append(f"Size: {metadata['image_width']}x{metadata['image_height']}")
        if "image_description" in metadata:
            parts.append(f"Description: {metadata['image_description']}")
        text = "\n".join(parts)

    if not text.strip():
        return []

    return [Document(text=text, metadata=metadata)]
