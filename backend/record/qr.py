from __future__ import annotations

import base64
import io
import sqlite3

from backend.nlp.lexicon import Lexicon
from backend.record import entries as record
from backend.schemas import QrPayload


def encode_png_bytes(content: str, scale: int = 6, border: int = 2) -> bytes:
    """Generate high-contrast QR PNG bytes using Segno (with qrcode fallback)."""
    try:
        import segno

        qr = segno.make(content, error="m")
        buf = io.BytesIO()
        qr.save(buf, kind="png", scale=scale, border=border)
        return buf.getvalue()
    except ImportError:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_M

        code = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_M,
            box_size=scale,
            border=border,
        )
        code.add_data(content)
        code.make(fit=True)
        img = code.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


def encode_data_uri(content: str) -> str:
    """Return data:image/png;base64,... URI for instant browser rendering."""
    raw_bytes = encode_png_bytes(content)
    encoded = base64.b64encode(raw_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_qr_payload(patient: sqlite3.Row, con: sqlite3.Connection, lexicon: Lexicon) -> QrPayload:
    """Build emergency responder payload encoded into QR."""
    sanchai_id = patient["sanchai_id"] or patient["arogya_id"] or f"SANCHAI-{patient['id']}"
    sanjaal_id = (
        (patient["sanjaal_id"] if "sanjaal_id" in patient.keys() else None)
        or sanchai_id.replace("SANCHAI-", "SANJAAL-")
    )
    qr_token = patient["qr_token"]
    encodes = f"sanchai://p/{qr_token}"

    allergies: list[str] = []
    for a in record.list_allergies(con, patient["id"]):
        label = a["substance_en"]
        if a["substance_np"]:
            label = f"{label} ({a['substance_np']})"
        allergies.append(label)
    conditions = [
        f"{c.canonical_en} ({c.canonical_np})"
        for c in record.active_conditions(con, patient["id"], lexicon)
    ]

    return QrPayload(
        sanjaal_id=sanjaal_id,
        sanchai_id=sanchai_id,
        arogya_id=patient["arogya_id"],
        qr_token=qr_token,
        name=patient["name"],
        name_np=patient["name_np"],
        blood_group=patient["blood_group"],
        allergies=allergies,
        conditions=conditions,
        synthetic=True,
        encodes=encodes,
        qr_png=encode_data_uri(encodes),
    )
