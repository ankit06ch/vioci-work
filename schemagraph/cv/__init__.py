"""schemagraph.cv: classical CV primitive extraction (lines, boxes, circles, arrows, OCR)."""

from schemagraph.cv.primitives import detect_primitives
from schemagraph.cv.ocr import detect_text_spans

__all__ = ["detect_primitives", "detect_text_spans"]
