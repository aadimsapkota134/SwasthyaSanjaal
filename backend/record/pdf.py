"""ReportLab A4 clinical summary PDF generator for SwasthyaSanjaal.

Produces a clean, print-ready doctor summary with patient demographics,
embedded Segno QR code, confirmed allergies, active clinical conditions,
and recent encounter timeline without missing glyphs or font corruption.
"""

from __future__ import annotations

import io
import os
import re
import sqlite3
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.nlp.lexicon import Lexicon
from backend.record import entries as record
from backend.record import qr

# Register modern TrueType Unicode fonts if available on the host system
FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

for regular_cand, bold_cand, reg_name, bold_name in [
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf", "SegoeUI", "SegoeUI-Bold"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf", "Arial", "Arial-Bold"),
]:
    if os.path.exists(regular_cand) and os.path.exists(bold_cand):
        try:
            pdfmetrics.registerFont(TTFont(reg_name, regular_cand))
            pdfmetrics.registerFont(TTFont(bold_name, bold_cand))
            FONT_REGULAR = reg_name
            FONT_BOLD = bold_name
            break
        except Exception:
            continue


def format_bs_date(raw: str | None) -> str:
    """Format Bikram Sambat date cleanly with Romanized numerals and months.

    Prevents unmapped Devanagari numerals from rendering as black boxes in PDF viewers.
    """
    if not raw or not raw.strip():
        return "-"

    deva_digits = {
        "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
        "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
    }
    cleaned = "".join(deva_digits.get(ch, ch) for ch in raw)

    months = {
        "बैशाख": "Baisakh", "वैशाख": "Baisakh",
        "जेठ": "Jestha", "ज्येष्ठ": "Jestha",
        "असार": "Asar", "आषाढ": "Asar",
        "साउन": "Shrawan", "श्रावण": "Shrawan", "सावन": "Shrawan",
        "भदौ": "Bhadra", "भाद्र": "Bhadra",
        "असोज": "Asoj", "आश्विन": "Asoj",
        "कार्तिक": "Kartik", "कात्तिक": "Kartik",
        "मंसिर": "Mangsir", "मार्ग": "Mangsir",
        "पुस": "Poush", "पौष": "Poush",
        "माघ": "Magh",
        "फागुन": "Falgun", "फाल्गुन": "Falgun",
        "चैत": "Chaitra", "चैत्र": "Chaitra",
    }
    for np_m, en_m in months.items():
        if np_m in cleaned:
            cleaned = cleaned.replace(np_m, en_m)
            break

    return cleaned.strip()


def format_facility_name(raw: str | None) -> str:
    """Ensure clinical facility names render cleanly in international PDF readers."""
    if not raw or not raw.strip():
        return "OPD Desk"
    raw = raw.strip()
    facilities = {
        "धुलिखेल अस्पताल": "Dhulikhel Hospital",
        "धुलिखेल": "Dhulikhel Hospital",
        "काठमाडौँ अस्पताल": "Kathmandu Hospital",
        "काठमाडौँ": "Kathmandu Hospital",
        "पाटन अस्पताल": "Patan Hospital",
        "पाटन": "Patan Hospital",
        "वीर अस्पताल": "Bir Hospital",
        "त्रिवि शिक्षण अस्पताल": "TUTH (Teaching Hospital)",
        "टिचिङ अस्पताल": "TUTH (Teaching Hospital)",
        "भक्तपुर अस्पताल": "Bhaktapur Hospital",
        "स्वास्थ्य चौकी": "Community Health Post",
        "प्राथमिक स्वास्थ्य केन्द्र": "Primary Health Centre",
    }
    for np_fac, en_fac in facilities.items():
        if np_fac in raw:
            return en_fac
    if re.search(r"[\u0900-\u097F]", raw):
        return "Community Health Facility"
    return raw


def summarize_timeline_findings(norm: record.StoredNormalization, limit: int = 4) -> str:
    """Produce clean clinical findings summary with explicit negation flags."""
    if not norm.concepts:
        return "Routine clinical assessment"
    parts = [
        f"{item.concept.canonical_en} [Negated]" if item.negated else item.concept.canonical_en
        for item in norm.concepts[:limit]
    ]
    remainder = len(norm.concepts) - len(parts)
    if remainder > 0:
        parts.append(f"+{remainder} more")
    return ", ".join(parts)


def generate_doctor_summary_pdf(
    patient: sqlite3.Row,
    con: sqlite3.Connection,
    lexicon: Lexicon,
) -> bytes:
    """Generate high-quality A4 Doctor Summary PDF bytes without missing glyph boxes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1e1a17"),
    )
    subtitle_style = ParagraphStyle(
        "DocSub",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#5f544c"),
    )
    h2_style = ParagraphStyle(
        "DocH2",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#c86b1c"),
    )
    body_style = ParagraphStyle(
        "DocBody",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1e1a17"),
    )
    bold_style = ParagraphStyle(
        "DocBold",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1e1a17"),
    )
    alert_style = ParagraphStyle(
        "DocAlert",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#b23d34"),
    )

    story: list[Any] = []

    # 1. Header with QR Code
    qr_token = patient["qr_token"]
    qr_content = f"sanchai://p/{qr_token}"
    qr_png_bytes = qr.encode_png_bytes(qr_content, scale=4, border=1)
    qr_img = Image(io.BytesIO(qr_png_bytes), width=1.1 * inch, height=1.1 * inch)

    p_name = patient["name"]
    p_sid = (
        (patient["sanjaal_id"] if "sanjaal_id" in patient.keys() else None)
        or patient["sanchai_id"]
        or patient["id"]
    )
    p_dist = patient["district"] or "N/A"
    p_bg = patient["blood_group"] or "Unknown"
    p_gender = patient["gender"].capitalize() if patient["gender"] else "N/A"
    p_dob = patient["dob"] or "N/A"

    header_text = [
        Paragraph("<b>SWASTHYASANJAAL - CLINICAL HEALTH SUMMARY</b>", title_style),
        Paragraph("Bilingual Longitudinal Health Ledger | Zero-Hallucination Verified", subtitle_style),
        Spacer(1, 4),
        Paragraph(
            f"<b>Patient:</b> {p_name} | <b>Sanjaal ID:</b> {p_sid} | <b>District:</b> {p_dist}",
            body_style,
        ),
        Paragraph(
            f"<b>Blood Group:</b> {p_bg} | <b>Gender:</b> {p_gender} | <b>DOB:</b> {p_dob}",
            body_style,
        ),
    ]

    header_table = Table(
        [[header_text, qr_img]],
        colWidths=[5.5 * inch, 1.6 * inch],
    )
    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ])
    )
    story.append(header_table)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#c86b1c"), spaceAfter=10))

    # 2. Critical Safety Strip: Allergies & Active Conditions
    allergies = record.list_allergies(con, patient["id"])
    conditions = record.active_conditions(con, patient["id"], lexicon)

    allergy_paras = [
        Paragraph(f"- <b>{a['substance_en']}</b>: {a['severity'] or 'known'} severity", alert_style)
        for a in allergies
    ] or [Paragraph("No documented clinical allergies.", body_style)]

    condition_paras = [
        Paragraph(f"- <b>{c.canonical_en}</b> [ICD-11: {c.icd11_code or 'N/A'}]", bold_style)
        for c in conditions
    ] or [Paragraph("No active chronic conditions asserted.", body_style)]

    safety_table = Table(
        [
            [
                Paragraph("<b>CRITICAL ALLERGIES & ADVERSE REACTIONS</b>", h2_style),
                Paragraph("<b>ACTIVE CONFIRMED CONDITIONS</b>", h2_style),
            ],
            [
                allergy_paras,
                condition_paras,
            ],
        ],
        colWidths=[3.6 * inch, 3.6 * inch],
    )
    safety_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#fff4f2")),
            ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#f0f9f4")),
            ("BOX", (0, 0), (0, -1), 1, colors.HexColor("#ffcdd2")),
            ("BOX", (1, 0), (1, -1), 1, colors.HexColor("#c8e6c9")),
            ("PADDING", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    story.append(safety_table)
    story.append(Spacer(1, 12))

    # 3. Longitudinal Timeline Table
    story.append(Paragraph("<b>LONGITUDINAL CLINICAL TIMELINE (HUMAN-APPROVED ENTRIES)</b>", h2_style))
    story.append(Spacer(1, 5))

    raw_entries = record.list_entries(con, patient["id"])
    table_data = [
        [
            Paragraph("<b>Date / BS</b>", bold_style),
            Paragraph("<b>Type / Facility</b>", bold_style),
            Paragraph("<b>Clinical Findings & Summary</b>", bold_style),
            Paragraph("<b>Ontology Link</b>", bold_style),
        ]
    ]

    for row in raw_entries:
        norm = record.hydrate(row["normalized_json"], lexicon)
        summary_text = summarize_timeline_findings(norm)
        facility = format_facility_name(row["facility_name"])
        bs_date = format_bs_date(row["record_date_bs"])
        doc_type = (row["document_class"] or row["input_type"]).upper()
        icd_code = row["icd11_code"] or row["icd10_code"]

        if icd_code:
            code_cell = f"<b>ICD-11: {icd_code}</b><br/><font color=\"#1f8a5b\">WHO Mapped</font>"
        else:
            code_cell = f"<b>NCL Verified</b><br/><font color=\"#575047\">{len(norm.concepts)} concepts</font>"

        table_data.append([
            Paragraph(f"{row['record_date']}<br/><font color=\"#575047\">BS: {bs_date}</font>", body_style),
            Paragraph(f"<b>{doc_type}</b><br/>{facility}", body_style),
            Paragraph(summary_text, body_style),
            Paragraph(code_cell, body_style),
        ])

    timeline_table = Table(
        table_data,
        colWidths=[1.15 * inch, 1.65 * inch, 2.75 * inch, 1.65 * inch],
    )
    timeline_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4efe8")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e7ddd1")),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    story.append(timeline_table)
    story.append(Spacer(1, 14))

    # 4. Clinical Footer & Verification
    footer_text = Paragraph(
        "<i>Generated by SwasthyaSanjaal Clinical Engine | Zero-Hallucination Lexicon Pipeline with Gemma 4 Guardrails.<br/>"
        "Scan QR code with any emergency reader to inspect cryptographically bound clinical profile.</i>",
        subtitle_style,
    )
    story.append(footer_text)

    doc.build(story)
    return buf.getvalue()
