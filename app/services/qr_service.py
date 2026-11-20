"""Generación de códigos QR en memoria (sin tocar el disco)."""
import base64
import io
import uuid

import qrcode
from qrcode.constants import ERROR_CORRECT_M


def _build_png(content: str, box_size: int = 10, border: int = 3) -> bytes:
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(content)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_qr_png_bytes(token: str | uuid.UUID) -> bytes:
    """Devuelve el PNG del QR como bytes."""
    return _build_png(str(token))


def generate_qr_base64(token: str | uuid.UUID) -> str:
    """Devuelve el QR como data URI Base64, listo para usar en <img> / ui.image."""
    encoded = base64.b64encode(generate_qr_png_bytes(token)).decode("ascii")
    return f"data:image/png;base64,{encoded}"
