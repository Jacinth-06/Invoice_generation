"""
generate_invoice.py
--------------------
Generates a GST-style "TAX INVOICE" PDF (logo + company header, Bill To / Ship
To, itemised table with HSN/Qty/Rate/CGST/SGST, totals, amount-in-words,
bank details and signature box) matching the common Indian tax-invoice
layout.

Usage:
    python generate_invoice.py
    -> reads the `sample_data` dict below and writes invoice.pdf

To reuse: just build your own `data` dict (see `sample_data` for the shape)
and call `create_invoice(data, "output.pdf")`.
"""

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from num2words import num2words


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def amount_in_words(amount: float) -> str:
    """Convert a rupee amount (with optional paise) to words, Indian style."""
    rupees = int(amount)
    paise = round((amount - rupees) * 100)
    words = num2words(rupees, lang="en_IN").replace(",", "").title()
    text = f"Rupees {words} Only"
    if paise:
        paise_words = num2words(paise, lang="en_IN").replace(",", "").title()
        text = f"Rupees {words} and {paise_words} Paise Only"
    return text


def wrap_text(text, font_name, font_size, max_width, c):
    """Greedy word-wrap a string to fit within max_width (points)."""
    words = text.split()
    lines, current = [], ""
    for w in words:
        trial = (current + " " + w).strip()
        if c.stringWidth(trial, font_name, font_size) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines or [""]


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def create_invoice(data: dict, output_path: str = "invoice.pdf"):
    c = canvas.Canvas(output_path, pagesize=A4)
    PAGE_W, PAGE_H = A4

    M = 15 * mm                       # outer margin
    LEFT = M
    RIGHT = PAGE_W - M
    WIDTH = RIGHT - LEFT

    # ---- column layout for the item table (each entry: width in mm) -----
    col_widths_mm = [
        ("sl", 10), ("desc", 70), ("hsn", 15), ("qty", 12),
        ("rate", 20), ("cgst", 15), ("sgst", 15), ("amount", 23),
    ]
    # left/right/center x-position (points) for every column, computed from
    # cumulative widths so they always add up exactly to WIDTH
    col_x, col_right, col_center = {}, {}, {}
    _cursor = 0.0
    for name, w in col_widths_mm:
        col_x[name] = LEFT + _cursor * mm
        _cursor += w
        col_right[name] = LEFT + _cursor * mm
        col_center[name] = (col_x[name] + col_right[name]) / 2
    col_end = RIGHT  # == col_right["amount"]

    # =======================================================================
    # Pre-compute item rows & totals so we know the table height up front
    # =======================================================================
    items = data["items"]
    desc_width = col_right["desc"] - col_x["desc"] - 2 * mm

    item_rows = []   # list of (item_dict, wrapped_lines, row_height)
    subtotal = 0.0
    cgst_total = 0.0
    sgst_total = 0.0

    for it in items:
        qty = it["qty"]
        rate = it["rate"]
        line_amount = qty * rate
        cgst_amt = line_amount * it.get("cgst_pct", 0) / 100
        sgst_amt = line_amount * it.get("sgst_pct", 0) / 100
        subtotal += line_amount
        cgst_total += cgst_amt
        sgst_total += sgst_amt

        lines = []
        lines += wrap_text(it["name"], "Helvetica-Bold", 9, desc_width, c)
        if it.get("description"):
            lines += wrap_text(it["description"], "Helvetica", 8, desc_width, c)

        row_h = max(10 * mm, 4 * mm + len(lines) * 3.6 * mm)
        item_rows.append((it, lines, row_h, line_amount))

    grand_total = subtotal + cgst_total + sgst_total

    table_header_h = 9 * mm
    table_body_h = sum(r[2] for r in item_rows)

    # =======================================================================
    # Vertical layout plan (top -> bottom)
    # =======================================================================
    header_h = 38 * mm
    invoice_meta_h = 12 * mm
    bill_ship_h = 32 * mm
    totals_h = 30 * mm
    notes_sign_h = 38 * mm

    total_h = (header_h + invoice_meta_h + bill_ship_h +
               table_header_h + table_body_h + totals_h + notes_sign_h)

    top = PAGE_H - M
    bottom = top - total_h
    if bottom < M:
        # Content taller than one page: in that case, paginate items
        # (kept simple here; extend with a loop over pages for very long
        # invoices).
        bottom = M

    # Outer border
    c.setLineWidth(1)
    c.rect(LEFT, bottom, WIDTH, top - bottom)

    y = top

    # ---- 1. HEADER: logo box | company info | TAX INVOICE ---------------
    c.line(LEFT, y - header_h, RIGHT, y - header_h)

    logo_box_w = 28 * mm
    c.line(LEFT + logo_box_w, y - header_h, LEFT + logo_box_w, y)

    company = data["company"]
    if company.get("logo_path"):
        try:
            c.drawImage(company["logo_path"], LEFT + 2 * mm, y - header_h + 4 * mm,
                         width=logo_box_w - 4 * mm, height=header_h - 8 * mm,
                         preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
    else:
        c.setFont("Helvetica-Oblique", 7)
        c.drawCentredString(LEFT + logo_box_w / 2, y - header_h / 2, "LOGO")

    tax_invoice_w = 45 * mm
    c.line(RIGHT - tax_invoice_w, y - header_h, RIGHT - tax_invoice_w, y)

    info_x = LEFT + logo_box_w + 3 * mm
    info_y = y - 7 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(info_x, info_y, company["name"])
    c.setFont("Helvetica", 8.5)
    for line in company.get("address_lines", []):
        info_y -= 4.3 * mm
        c.drawString(info_x, info_y, line)
    if company.get("phone"):
        info_y -= 4.3 * mm
        c.drawString(info_x, info_y, f"Contact No: {company['phone']}.")
    if company.get("email"):
        info_y -= 4.3 * mm
        c.drawString(info_x, info_y, f"Email: {company['email']}.")
    if company.get("gstin"):
        info_y -= 4.3 * mm
        c.drawString(info_x, info_y, f"GSTIN: {company['gstin']}.")

    c.setFont("Helvetica-Bold", 17)
    c.drawCentredString(RIGHT - tax_invoice_w / 2, y - header_h / 2 - 2, "TAX INVOICE")

    y -= header_h

    # ---- 2. Invoice No / Date row ----------------------------------------
    c.line(LEFT, y - invoice_meta_h, RIGHT, y - invoice_meta_h)
    c.setFont("Helvetica", 9.5)
    c.drawString(LEFT + 2 * mm, y - 5 * mm, f"INVOICE NO   : {data['invoice_no']}")
    c.drawString(LEFT + 2 * mm, y - 9.5 * mm, f"Invoice Date : {data['invoice_date']}")
    y -= invoice_meta_h

    # ---- 3. Bill To / Ship To ---------------------------------------------
    half_w = WIDTH / 2
    c.line(LEFT, y - bill_ship_h, RIGHT, y - bill_ship_h)
    c.line(LEFT + half_w, y - bill_ship_h, LEFT + half_w, y)

    def draw_party(label, party, x):
        py = y - 5 * mm
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(x + 2 * mm, py, label)
        py -= 5 * mm
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(x + 2 * mm, py, party["name"])
        c.setFont("Helvetica", 9)
        for line in party.get("address_lines", []):
            py -= 4.3 * mm
            c.drawString(x + 2 * mm, py, line)
        if party.get("gstin"):
            py -= 4.3 * mm
            c.drawString(x + 2 * mm, py, f"GSTIN {party['gstin']}")

    draw_party("Bill To", data["bill_to"], LEFT)
    draw_party("Ship To", data.get("ship_to", data["bill_to"]), LEFT + half_w)
    y -= bill_ship_h

    # ---- 4. Item table header ----------------------------------------------
    c.setFillColor(colors.whitesmoke)
    c.rect(LEFT, y - table_header_h, WIDTH, table_header_h, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.rect(LEFT, y - table_header_h, WIDTH, table_header_h, fill=0, stroke=1)

    headers = [
        ("sl", "SL\nNO"), ("desc", "Item & Description"), ("hsn", "HSN"),
        ("qty", "Qty"), ("rate", "Rate"), ("cgst", "CGST"),
        ("sgst", "SGST"), ("amount", "Amount"),
    ]
    c.setFont("Helvetica-Bold", 9)
    for key, label in headers:
        lines = label.split("\n")
        ty = y - 3.5 * mm if len(lines) == 1 else y - 2.8 * mm
        for ln in lines:
            if key == "sl":
                c.drawString(col_x[key] + 2 * mm, ty, ln)
            elif key == "desc":
                c.drawString(col_x[key] + 2 * mm, ty, ln)
            else:
                c.drawCentredString(col_center[key], ty, ln)
            ty -= 3.3 * mm

    # column separators across header + body
    for key in ["desc", "hsn", "qty", "rate", "cgst", "sgst", "amount"]:
        c.line(col_x[key], y - table_header_h - table_body_h, col_x[key], y)

    y -= table_header_h

    # ---- 5. Item rows --------------------------------------------------------
    c.setFont("Helvetica", 9)
    for idx, (it, lines, row_h, line_amount) in enumerate(item_rows, start=1):
        row_top = y
        row_bottom = y - row_h
        c.line(LEFT, row_bottom, RIGHT, row_bottom)

        c.setFont("Helvetica", 9)
        c.drawString(LEFT + 2 * mm, row_top - 5 * mm, str(idx))

        ty = row_top - 4.2 * mm
        for li, ln in enumerate(lines):
            c.setFont("Helvetica-Bold" if li == 0 else "Helvetica", 9 if li == 0 else 8)
            c.drawString(col_x["desc"], ty, ln)
            ty -= 3.6 * mm

        mid_y = row_top - row_h / 2 + 1.2 * mm
        c.setFont("Helvetica", 9)
        c.drawCentredString(col_center["hsn"], mid_y, str(it.get("hsn", "")))
        c.drawCentredString(col_center["qty"], mid_y, str(it["qty"]))
        c.drawRightString(col_right["rate"] - 2 * mm, mid_y, f"{it['rate']:,.2f}")
        c.drawCentredString(col_center["cgst"], mid_y, f"{it.get('cgst_pct', 0)}%")
        c.drawCentredString(col_center["sgst"], mid_y, f"{it.get('sgst_pct', 0)}%")
        c.drawRightString(col_right["amount"] - 2 * mm, mid_y, f"{line_amount:,.2f}")

        y = row_bottom

    # ---- 6. Totals block -----------------------------------------------------
    totals_right_w = 65 * mm
    totals_left_w = WIDTH - totals_right_w
    c.line(LEFT + totals_left_w, y - totals_h, LEFT + totals_left_w, y)
    c.line(LEFT, y - totals_h, RIGHT, y - totals_h)

    # left: items count + amount in words
    ly = y - 5 * mm
    c.setFont("Helvetica", 9.5)
    c.drawString(LEFT + 2 * mm, ly, f"Items in Total  {len(items)}")
    ly -= 8 * mm
    c.setFont("Helvetica", 9.5)
    c.drawString(LEFT + 2 * mm, ly, "Total In Words")
    ly -= 4.6 * mm
    c.setFont("Helvetica-BoldOblique", 9.5)
    for ln in wrap_text(amount_in_words(grand_total), "Helvetica-BoldOblique", 9.5,
                         totals_left_w - 4 * mm, c):
        c.drawString(LEFT + 2 * mm, ly, ln)
        ly -= 4.2 * mm

    # right: subtotal / cgst / sgst / total
    label_x = LEFT + totals_left_w + 2 * mm
    val_x = RIGHT - 2 * mm
    ry = y - 5 * mm
    c.setFont("Helvetica", 9.5)
    for label, val in [
        ("Sub Total", subtotal),
        (f"CGST ({items[0].get('cgst_pct', 0)}%)" if items else "CGST", cgst_total),
        (f"SGST ({items[0].get('sgst_pct', 0)}%)" if items else "SGST", sgst_total),
    ]:
        c.drawString(label_x, ry, label)
        c.drawRightString(val_x, ry, f"{val:,.2f}")
        ry -= 6.5 * mm
    c.line(label_x - 2 * mm, ry + 3 * mm, val_x, ry + 3 * mm)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(label_x, ry, "Total")
    c.drawRightString(val_x, ry, f"Rs. {grand_total:,.2f}")

    y -= totals_h

    # ---- 7. Notes / Bank details (left)  |  Signature box (right) -----------
    sig_w = 60 * mm
    notes_w = WIDTH - sig_w
    c.line(LEFT + notes_w, y - notes_sign_h, LEFT + notes_w, y)
    c.line(LEFT, y - notes_sign_h, RIGHT, y - notes_sign_h)

    ny = y - 5 * mm
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(LEFT + 2 * mm, ny, "Notes")
    ny -= 4.3 * mm
    c.setFont("Helvetica", 9)
    for ln in data.get("notes", []):
        c.drawString(LEFT + 2 * mm, ny, ln)
        ny -= 4.3 * mm

    if data.get("bank"):
        ny -= 3 * mm
        bank = data["bank"]
        c.setFont("Helvetica", 8.5)
        rows = [
            ("Acc Name", bank.get("acc_name", "")),
            ("Acc No", bank.get("acc_no", "")),
            ("Account type", bank.get("acc_type", "")),
            ("Bank", bank.get("bank_name", "")),
            ("Acc Branch", bank.get("branch", "")),
            ("IFSC Code", bank.get("ifsc", "")),
        ]
        for label, val in rows:
            c.drawString(LEFT + 2 * mm, ny, f"{label:<13}: {val}")
            ny -= 4 * mm

    c.setFont("Helvetica", 9.5)
    c.drawCentredString(LEFT + notes_w + sig_w / 2, y - notes_sign_h + 5 * mm,
                         "Authorized Signature")

    c.showPage()
    c.save()
    return output_path


# ---------------------------------------------------------------------------
# Sample data — replace with your own invoice details
# ---------------------------------------------------------------------------

sample_data = {
    "company": {
        "name": "YOUR COMPANY NAME",
        "address_lines": [
            "Street Address Line 1,",
            "Area / Locality,",
            "City - PINCODE, State .",
        ],
        "phone": "9999999999",
        "email": "yourcompany@example.com",
        "gstin": "33XXXXX0000X1ZX",
        "logo_path": None,  # path to a PNG/JPG logo, or None
    },
    "invoice_no": "1001",
    "invoice_date": "19-06-2026",
    "bill_to": {
        "name": "CLIENT ORGANISATION",
        "address_lines": ["Address line 1", "Address line 2", "City-PINCODE"],
        "gstin": "33XXXXX0000X1ZX",
    },
    "ship_to": {
        "name": "CLIENT ORGANISATION",
        "address_lines": ["Address line 1", "Address line 2", "City-PINCODE"],
        "gstin": "33XXXXX0000X1ZX",
    },
    "items": [
        {
            "name": "Sample Items",
            "description": "Your description",
            "hsn": "8504",
            "qty": 1,
            "rate": 4500.00,
            "cgst_pct": 9,
            "sgst_pct": 9,
        },
        # add more line items here
    ],
    "notes": ["Thanks for your business."],
    "bank": {
        "acc_name": "Your Company Name",
        "acc_no": "000000000000",
        "acc_type": "Current Account",
        "bank_name": "BANK NAME",
        "branch": "BRANCH, CITY",
        "ifsc": "BANK0000000",
    },
}


if __name__ == "__main__":
    path = create_invoice(sample_data, "invoice.pdf")
    print(f"Saved: {path}")
