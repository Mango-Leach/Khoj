"""Image checks and re-encoding that need no model (CLAUDE.md section 11, "Gates before the model").

Every upload is decoded, checked for size, sharpness and light, and re-encoded as a small JPEG. Re-encoding drops the
metadata (location included) and means only well-formed pixels are ever stored or sent on. The thresholds are starting
values for the team to tune on real photos, not facts.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 1_500_000  # the phone shrinks photos to about 200 KB first, so this is generous
MAX_PIXELS = 40_000_000  # refuse a decompression bomb before decoding it
MAX_EDGE = 1024
JPEG_QUALITY = 80
MIN_EDGE = 400  # a long edge shorter than this cannot show a certificate legibly
MIN_SHARPNESS = 30.0  # variance of the Laplacian on the grey image
MIN_BRIGHTNESS = 40.0
MAX_BRIGHTNESS = 235.0
DUPLICATE_DISTANCE = 6  # of 64 bits: the same photo, resized or recompressed, falls well inside this


class ImageProblem(Exception):
    """An upload that cannot be used. `code` is stable and maps to a translated message."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def load(data: bytes) -> Image.Image:
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageProblem("photo_too_large")
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in ("JPEG", "PNG"):
            raise ImageProblem("photo_bad_format")
        if img.width * img.height > MAX_PIXELS:
            raise ImageProblem("photo_too_large")
        img = ImageOps.exif_transpose(img)  # honour the phone's rotation, then the metadata is gone
        return img.convert("RGB")
    except ImageProblem:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ImageProblem("photo_bad_format") from None


def shrink(img: Image.Image) -> Image.Image:
    out = img.copy()
    out.thumbnail((MAX_EDGE, MAX_EDGE))
    return out


def laplacian_variance(img: Image.Image) -> float:
    a = np.asarray(img.convert("L"), dtype=np.float64)
    if a.shape[0] < 3 or a.shape[1] < 3:
        return 0.0
    lap = a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:] - 4.0 * a[1:-1, 1:-1]
    return float(lap.var())


def brightness(img: Image.Image) -> float:
    return float(np.asarray(img.convert("L"), dtype=np.float64).mean())


def quality_problems(img: Image.Image) -> list[str]:
    """Why the photo should be retaken. Empty means it is usable."""
    problems: list[str] = []
    if max(img.size) < MIN_EDGE:
        problems.append("photo_too_small")
        return problems  # the other numbers mean little on a tiny image
    b = brightness(img)  # first: a dark or washed-out photo also looks blurry, and "too dark" is the useful message
    if b < MIN_BRIGHTNESS:
        problems.append("photo_dark")
    elif b > MAX_BRIGHTNESS:
        problems.append("photo_bright")
    if laplacian_variance(img) < MIN_SHARPNESS:
        problems.append("photo_blurry")
    return problems


def dhash(img: Image.Image) -> str:
    """A 64-bit difference hash as 16 hex characters. Near-identical photos give near-identical hashes."""
    g = np.asarray(img.convert("L").resize((9, 8), Image.Resampling.LANCZOS), dtype=np.int16)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return f"{value:016x}"


def hamming(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()


def encode(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue()


def prepare(data: bytes) -> tuple[bytes, str, float]:
    """Decode, check and re-encode an upload. Returns (jpeg bytes, perceptual hash, sharpness) or raises ImageProblem."""
    img = shrink(load(data))
    problems = quality_problems(img)
    if problems:
        raise ImageProblem(problems[0])
    return encode(img), dhash(img), laplacian_variance(img)
