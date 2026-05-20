"""Input loaders for PNG/JPG/PDF/SVG.

Each loader returns a :class:`LoadedImage` containing the canonical raster
bytes (always PNG), basic metadata, and (optionally) preserved native vector
geometry when the input was an SVG.
"""

from __future__ import annotations

import io
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from schemagraph.ir.ids import sha256_of_bytes
from schemagraph.ir.schema import SourceMeta, VectorLayer, VectorPath


@dataclass
class LoadedImage:
    """A normalized, in-memory representation of an input."""

    png_bytes: bytes
    width_px: int
    height_px: int
    source: SourceMeta
    native_vector: Optional[VectorLayer] = None
    extra: dict = field(default_factory=dict)


def _guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def load_input(path: str | Path, page: int = 1) -> LoadedImage:
    """Load an image / PDF / SVG into a canonical PNG-backed :class:`LoadedImage`."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    mime = _guess_mime(path)
    suffix = path.suffix.lower()

    if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}:
        return _load_raster(path, mime=mime)
    if suffix == ".pdf":
        return _load_pdf(path, page=page)
    if suffix == ".svg":
        return _load_svg(path)
    raise ValueError(f"unsupported input type: {path.suffix!r}")


def _load_raster(path: Path, mime: str) -> LoadedImage:
    from PIL import Image

    data = path.read_bytes()
    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png = buf.getvalue()
        w, h = img.size
    source = SourceMeta(
        uri=str(path.resolve()),
        sha256=sha256_of_bytes(data),
        mime=mime,
        width_px=w,
        height_px=h,
    )
    return LoadedImage(png_bytes=png, width_px=w, height_px=h, source=source)


def _load_pdf(path: Path, page: int) -> LoadedImage:
    try:
        import pypdf  # noqa: F401
    except Exception as e:  # pragma: no cover
        raise RuntimeError("pypdf is required to load PDFs") from e
    try:
        from pdf2image import convert_from_path  # type: ignore
    except Exception:
        convert_from_path = None  # type: ignore

    if convert_from_path is not None:
        images = convert_from_path(str(path), first_page=page, last_page=page)
        if not images:
            raise RuntimeError(f"PDF page {page} could not be rasterized")
        img = images[0].convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png = buf.getvalue()
        w, h = img.size
    else:
        # Fallback: render via PyMuPDF if available; otherwise raise.
        try:
            import fitz  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "Rendering PDFs requires either `pdf2image` (poppler) or `pymupdf`."
            ) from e
        doc = fitz.open(str(path))
        if page - 1 >= len(doc):
            raise RuntimeError(f"PDF has {len(doc)} pages; requested page {page}")
        p = doc.load_page(page - 1)
        pix = p.get_pixmap(dpi=200)
        png = pix.tobytes("png")
        w, h = pix.width, pix.height
    data = path.read_bytes()
    source = SourceMeta(
        uri=str(path.resolve()),
        sha256=sha256_of_bytes(data),
        mime="application/pdf",
        width_px=w,
        height_px=h,
        pages=1,
    )
    return LoadedImage(png_bytes=png, width_px=w, height_px=h, source=source)


def _load_svg(path: Path) -> LoadedImage:
    import cairosvg

    svg_bytes = path.read_bytes()
    png = cairosvg.svg2png(bytestring=svg_bytes, output_width=2048)
    from PIL import Image

    with Image.open(io.BytesIO(png)) as img:
        w, h = img.size
    vector = _svg_to_vector_layer(svg_bytes.decode("utf-8", errors="ignore"), w, h)
    source = SourceMeta(
        uri=str(path.resolve()),
        sha256=sha256_of_bytes(svg_bytes),
        mime="image/svg+xml",
        width_px=w,
        height_px=h,
    )
    return LoadedImage(
        png_bytes=png,
        width_px=w,
        height_px=h,
        source=source,
        native_vector=vector,
    )


def _svg_to_vector_layer(svg_text: str, width: int, height: int) -> VectorLayer:
    """Minimal SVG -> VectorLayer extraction (paths only; preserves `d=` strings)."""
    import re

    paths: list[VectorPath] = []
    for m in re.finditer(r"<path\b[^>]*\bd=\"([^\"]+)\"", svg_text):
        paths.append(VectorPath(kind="path", svg_d=m.group(1)))
    for m in re.finditer(
        r"<line\b[^>]*\bx1=\"([^\"]+)\"[^>]*\by1=\"([^\"]+)\"[^>]*\bx2=\"([^\"]+)\"[^>]*\by2=\"([^\"]+)\"",
        svg_text,
    ):
        x1, y1, x2, y2 = (float(g) for g in m.groups())
        paths.append(VectorPath(kind="line", points=[(x1, y1), (x2, y2)]))
    return VectorLayer(
        width_px=float(width),
        height_px=float(height),
        paths=paths,
        source="native_svg" if paths else "raster_vectorized",
    )
