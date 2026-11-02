"""Contractor-ready PDF report (ReportLab).

Contents: summary, original vs redesigned photos, material schedule with purchase
quantities, cost breakdown, category totals, and the method & assumptions used.
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.catalog import Catalog
from app.schemas import Estimate, ProjectData

FONT_DIR = Path(__file__).resolve().parent.parent / "data" / "fonts"
pdfmetrics.registerFont(TTFont("Noto", str(FONT_DIR / "NotoSans-Regular.ttf")))
pdfmetrics.registerFont(TTFont("Noto-Bold", str(FONT_DIR / "NotoSans-Bold.ttf")))

INK = colors.HexColor("#1F2A24")
MUTED = colors.HexColor("#6B7A70")
ACCENT = colors.HexColor("#1F5F45")
LINE = colors.HexColor("#DCE3DE")
TINT = colors.HexColor("#F1F5F2")

STYLES = {
    "title": ParagraphStyle("title", fontName="Noto-Bold", fontSize=20, leading=24, textColor=INK),
    "subtitle": ParagraphStyle("subtitle", fontName="Noto", fontSize=9.5, leading=13, textColor=MUTED),
    "h2": ParagraphStyle("h2", fontName="Noto-Bold", fontSize=12.5, leading=16, textColor=INK, spaceBefore=10, spaceAfter=6),
    "body": ParagraphStyle("body", fontName="Noto", fontSize=8.8, leading=12.5, textColor=INK),
    "small": ParagraphStyle("small", fontName="Noto", fontSize=7.4, leading=9.6, textColor=INK),
    "small_muted": ParagraphStyle("small_muted", fontName="Noto", fontSize=7, leading=9.2, textColor=MUTED),
    "small_right": ParagraphStyle("small_right", fontName="Noto", fontSize=7.4, leading=9.6, textColor=INK, alignment=TA_RIGHT),
    "kpi_value": ParagraphStyle("kpi_value", fontName="Noto-Bold", fontSize=15, leading=19, textColor=ACCENT),
    "kpi_label": ParagraphStyle("kpi_label", fontName="Noto", fontSize=7.5, leading=10, textColor=MUTED),
}

PAGE_W, PAGE_H = A4
MARGIN = 14 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


def format_inr(value: float) -> str:
    """Indian digit grouping: 1234567 -> ₹12,34,567."""
    n = round(value)
    digits = str(abs(n))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups) + "," + tail
    return ("-" if n < 0 else "") + "₹" + digits


def build_report(
    name: str,
    data: ProjectData,
    estimate: Estimate,
    catalog: Catalog,
    originals: dict[str, bytes],
    renders: dict[str, bytes],
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=16 * mm,
        title=f"{name} - Exterior renovation plan", author="FacadeAI",
    )
    story: list = []
    p = lambda text, style="body": Paragraph(text, STYLES[style])  # noqa: E731

    # --- Header & key figures ------------------------------------------------
    story += [
        p("Exterior Renovation Plan &amp; Estimate", "title"),
        p(f"{_esc(name)} &nbsp;·&nbsp; Design: <b>{_esc(estimate.design_name)}</b> &nbsp;·&nbsp; "
          f"{datetime.now().strftime('%d %b %Y')} &nbsp;·&nbsp; Rates: {_esc(estimate.city)} ({catalog.rates_updated})", "subtitle"),
        Spacer(1, 8),
        _kpi_row([
            (format_inr(estimate.grand_total),
             f"Most likely total (incl. GST)<br/>range {format_inr(estimate.low_total)} - {format_inr(estimate.high_total)}"),
            (f"{estimate.total_area_sqft:,.0f} sqft", "Surface area to finish"),
            (f"{estimate.total_railing_rft:,.0f} rft", "Railing length"),
            (str(len(estimate.lines)), "Surfaces in scope"),
        ]),
    ]

    # --- Before / after --------------------------------------------------------
    for view in data.views:
        if view.id not in originals:
            continue
        story.append(p(f"{_esc(view.name)}: existing vs proposed", "h2"))
        cell_w = (CONTENT_W - 6 * mm) / 2
        before = _image(originals[view.id], cell_w)
        after = _image(renders[view.id], cell_w) if view.id in renders else p("No rendered design for this photo.", "small_muted")
        table = Table(
            [[before, after], [p("Existing", "small_muted"), p(f"Proposed: {_esc(estimate.design_name)}", "small_muted")]],
            colWidths=[cell_w + 3 * mm, cell_w + 3 * mm],
        )
        table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        story.append(KeepTogether([table]))

    # --- Material schedule & costs ----------------------------------------------
    story.append(p("Material schedule and cost breakdown", "h2"))
    if estimate.lines:
        story.append(_lines_table(estimate))
    else:
        story.append(p("No materials have been applied in this design yet.", "body"))
    if estimate.site_lines:
        story.append(KeepTogether([p("Site &amp; preparation", "h2"), _site_table(estimate)]))

    story.append(Spacer(1, 8))
    story.append(KeepTogether([p("Summary", "h2"), _summary_table(estimate)]))

    # --- Method & assumptions ----------------------------------------------------
    story.append(p("How this estimate was produced", "h2"))
    for item in _method_notes(data, estimate, catalog):
        story.append(p(f"• {item}", "small"))
        story.append(Spacer(1, 2))
    if estimate.unassigned_regions:
        story.append(Spacer(1, 4))
        story.append(p("Detected surfaces left unchanged in this design: " + _esc(", ".join(estimate.unassigned_regions)), "small_muted"))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


# --------------------------------------------------------------------------- #
# Building blocks
# --------------------------------------------------------------------------- #
def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _kpi_row(items: list[tuple[str, str]]) -> Table:
    cells = [[Paragraph(v, STYLES["kpi_value"]), Paragraph(l, STYLES["kpi_label"])] for v, l in items]
    widths = [CONTENT_W * w for w in (0.34, 0.24, 0.2, 0.22)]
    table = Table([[_stack(c) for c in cells]], colWidths=widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TINT),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEAFTER", (0, 0), (-2, -1), 0.6, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
    ]))
    return table


def _stack(flowables: list) -> Table:
    t = Table([[f] for f in flowables])
    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    return t


def _image(jpeg: bytes, width: float) -> Image:
    with PILImage.open(io.BytesIO(jpeg)) as im:
        w, h = im.size
    height = min(width * h / w, 95 * mm)
    return Image(io.BytesIO(jpeg), width=height * w / h, height=height)


def _lines_table(estimate: Estimate) -> Table:
    s, sr = STYLES["small"], STYLES["small_right"]
    header = ["Surface", "Material", "Net size", "Purchase quantities", "Material", "Labour", "Total"]
    rows: list[list] = [[Paragraph(f"<b>{h}</b>", sr if i >= 4 else s) for i, h in enumerate(header)]]
    for line in estimate.lines:
        colour = line.color_name
        size = f"{line.net:,.1f} {line.measure_unit}"
        if line.deductions > 0:
            size += f"<br/><font color='#6B7A70'>gross {line.gross:,.1f}<br/>-{line.deductions:,.1f} deducted</font>"
        if line.measured_from == "override":
            size += "<br/><font color='#6B7A70'>site-measured</font>"
        quantities = "<br/>".join(
            f"{q.name}: {q.quantity:g} {q.unit}" + (f" <font color='#6B7A70'>({_esc(q.note)})</font>" if q.note else "")
            for q in line.quantities
        )
        rows.append([
            Paragraph(f"{_esc(line.region_label)}<br/><font color='#6B7A70'>{_esc(line.view_name)} · {_esc(line.plane_name)}</font>", s),
            Paragraph(_esc(line.material_name) + (f"<br/><font color='#6B7A70'>{_esc(colour)}</font>" if colour else ""), s),
            Paragraph(size, s),
            Paragraph(quantities, s),
            Paragraph(f"{format_inr(line.material_cost)}<br/><font color='#6B7A70'>@ {format_inr(line.material_rate)}/{line.material_rate_unit}</font>", sr),
            Paragraph(f"{format_inr(line.labour_cost)}<br/><font color='#6B7A70'>@ {format_inr(line.labour_rate)}/{line.labour_rate_unit}</font>", sr),
            Paragraph(f"<b>{format_inr(line.total)}</b>", sr),
        ])
    widths = [w * CONTENT_W for w in (0.17, 0.16, 0.13, 0.22, 0.11, 0.1, 0.11)]
    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TINT),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _site_table(e: Estimate) -> Table:
    s, sr = STYLES["small"], STYLES["small_right"]
    rows = [[Paragraph("<b>Item</b>", s), Paragraph("<b>Quantity</b>", sr), Paragraph("<b>Rate</b>", sr), Paragraph("<b>Amount</b>", sr)]]
    for x in e.site_lines:
        qty = f"{x.quantity:g}%" if x.unit == "%" else f"{x.quantity:,.0f} {x.unit}"
        rate = "of works" if x.unit == "%" else f"{format_inr(x.rate)}/{x.unit}"
        rows.append([Paragraph(f"{_esc(x.name)}<br/><font color='#6B7A70'>{_esc(x.note)}</font>", s), Paragraph(qty, sr),
                     Paragraph(rate, sr), Paragraph(format_inr(x.amount), sr)])
    table = Table(rows, colWidths=[CONTENT_W * w for w in (0.58, 0.14, 0.14, 0.14)])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TINT),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _summary_table(e: Estimate) -> Table:
    s, sr = STYLES["small"], STYLES["small_right"]
    rows = [[Paragraph("<b>Category</b>", s), Paragraph("<b>Material</b>", sr), Paragraph("<b>Labour</b>", sr), Paragraph("<b>Total</b>", sr)]]
    for c in e.categories:
        rows.append([Paragraph(_esc(c.category), s), Paragraph(format_inr(c.material_cost), sr),
                     Paragraph(format_inr(c.labour_cost), sr), Paragraph(format_inr(c.total), sr)])
    rows += [
        [Paragraph("<b>Subtotal</b>", s), Paragraph(format_inr(e.material_total), sr), Paragraph(format_inr(e.labour_total + e.site_total), sr),
         Paragraph(f"<b>{format_inr(e.subtotal)}</b>", sr)],
        [Paragraph(f"Contingency ({e.contingency_pct:g}%)", s), "", "", Paragraph(format_inr(e.contingency), sr)],
        [Paragraph(f"GST ({e.gst_pct:g}%)", s), "", "", Paragraph(format_inr(e.gst), sr)],
        [Paragraph("<b>Estimated total</b> (most likely)", s), "", "", Paragraph(f"<b>{format_inr(e.grand_total)}</b>", sr)],
        [Paragraph("Likely range", s), "", "", Paragraph(f"{format_inr(e.low_total)} - {format_inr(e.high_total)}", sr)],
        [Paragraph(f"Over {e.lifetime_years} years, with repaints, resealing and upkeep ({format_inr(e.lifetime_future)} in future, "
                   "with inflation and GST)", s), "", "", Paragraph(format_inr(e.lifetime_total), sr)],
    ]
    table = Table(rows, colWidths=[CONTENT_W * w for w in (0.46, 0.18, 0.18, 0.18)])
    n = len(rows)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TINT),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("LINEABOVE", (0, n - 6), (-1, n - 6), 0.9, MUTED),
        ("BACKGROUND", (0, n - 3), (-1, n - 3), colors.HexColor("#E3EFE8")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _method_notes(data: ProjectData, estimate: Estimate, catalog: Catalog) -> list[str]:
    notes = []
    for plane in estimate.planes:
        if plane.ft_per_px_y is None:
            notes.append(f"<b>{_esc(plane.view_name)} / {_esc(plane.plane_name)}</b>: no scale (areas entered manually where shown).")
            continue
        cues = ", ".join(_esc(c) for c in plane.cues_used) or "-"
        how = f"borrowed from {_esc(plane.borrowed_from)}" if plane.borrowed_from else f"consensus of {cues}"
        status = "confirmed by the user" if plane.confirmed else "not yet confirmed"
        where = f" at {plane.ref_depth_m:g} m from the camera" if plane.ref_depth_m else ""
        notes.append(f"<b>{_esc(plane.view_name)} / {_esc(plane.plane_name)}</b> scale: {how}{where}; confidence {plane.confidence:.0%}, "
                     f"expected length error ±{plane.measurement_error_pct:g}% ({status}).")
    notes += [
        "Building parts were detected by AI (Gemini for labelled boxes and depth planes, SAM 2.1 for precise outlines) and reviewed by the user.",
        "Each depth plane (house front, side, compound) has its own scale: the weighted median of all reference cues on it "
        "(doors, cars, people, railings, user-measured lengths), with outliers ignored and separate horizontal/vertical scales when available.",
        *([
            "Distances: a depth model (Depth Anything V2) estimates how far each surface is from the camera. Feet-per-pixel grows "
            "with distance, so every reference is normalised by its own distance and every surface is measured at its own distance "
            "(a wall set back behind the balcony is not under-measured, a compound wall near the camera is not over-measured).",
        ] if any(p.ref_depth_m for p in estimate.planes) else []),
        "Areas: polygon area in pixels x horizontal x vertical feet-per-pixel. Windows, doors and parts in front of a surface are deducted, "
        "so nothing is counted twice. Pillar and gate areas include faces not visible in the photo where set.",
        "The long-term figure adds each finish's renewals (repaint, reseal, touch-up at its typical interval) and yearly upkeep "
        "over the period, priced like today's work with yearly inflation; scaffolding for future work is not included.",
        "The likely range combines each material's low/high market rates with the measurement uncertainty of its plane's scale.",
        f"Purchase quantities include wastage and are rounded up to whole packs, bags, boxes or sheets. Paint: {data.settings.paint_coats} top coats "
        "over primer (plus base coat for elastomeric systems). Labour is charged on the net area.",
        f"Rates are for {_esc(estimate.city)}. Contingency of {estimate.contingency_pct:g}% is applied to the subtotal, then GST of "
        f"{estimate.gst_pct:g}% to subtotal + contingency.",
        _esc(catalog.rates_note),
        "Not included: structural repairs, major damp treatment, electrical and plumbing work, permits.",
        "This is an advisory planning estimate for discussion with contractors. It is not a quotation and is not legally binding.",
    ]
    return notes


def _footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Noto", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, 9 * mm, "FacadeAI · advisory estimate, not a quotation")
    canvas.drawRightString(PAGE_W - MARGIN, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()
