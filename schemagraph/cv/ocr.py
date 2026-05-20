"""OCR text-span extraction.

Provides a uniform :func:`detect_text_spans` over multiple backends (Paddle,
Tesseract). Backends are loaded lazily and the function fails *open* by
returning an empty list when no backend is installed (VLMs typically handle
in-image text directly).
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from schemagraph.config import get_settings
from schemagraph.ir.schema import BBox, TextSpan


def detect_text_spans(gray: np.ndarray, *, backend: Optional[str] = None) -> list[TextSpan]:
    """Best-effort OCR. Returns [] if no backend is available."""
    settings = get_settings()
    chosen = backend or settings.ocr_backend
    if chosen in {"none"}:
        return []

    if chosen in {"auto", "paddle"}:
        try:
            return _paddle_ocr(gray)
        except Exception:
            if chosen == "paddle":
                return []

    if chosen in {"auto", "tesseract"}:
        try:
            return _tesseract_ocr(gray)
        except Exception:
            return []

    return []


def _paddle_ocr(gray: np.ndarray) -> list[TextSpan]:  # pragma: no cover - optional dep
    from paddleocr import PaddleOCR  # type: ignore

    ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    results = ocr.ocr(gray, cls=True)
    spans: list[TextSpan] = []
    for line in results or []:
        for box, (text, conf) in line:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            spans.append(
                TextSpan(
                    text=str(text),
                    bbox=BBox(x=min(xs), y=min(ys), w=max(xs) - min(xs), h=max(ys) - min(ys)),
                    confidence=float(conf),
                )
            )
    return spans


def _tesseract_ocr(gray: np.ndarray) -> list[TextSpan]:  # pragma: no cover - optional dep
    import pytesseract  # type: ignore

    data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
    spans: list[TextSpan] = []
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i]) / 100.0
        except Exception:
            conf = 0.5
        spans.append(
            TextSpan(
                text=text,
                bbox=BBox(
                    x=float(data["left"][i]),
                    y=float(data["top"][i]),
                    w=float(data["width"][i]),
                    h=float(data["height"][i]),
                ),
                confidence=conf,
            )
        )
    return spans
