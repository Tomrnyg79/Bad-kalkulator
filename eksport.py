"""
Eksportfunksjoner for PDF og Excel.
"""

import io
import datetime

from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

from priser import FIRMA, MVA_SATS


def fmt(tall):
    """Formater tall med norsk tusenskille."""
    return f"{tall:,.0f}".replace(",", " ")


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def generer_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # --- Firmaheader ---
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 8, FIRMA["navn"], new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.cell(
        0, 4,
        f"Org.nr: {FIRMA['orgnr']}  |  Tlf: {FIRMA['telefon']}",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.cell(
        0, 4,
        f"{FIRMA['adresse']}  |  {FIRMA['epost']}",
        new_x="LMARGIN", new_y="NEXT",
    )

    pdf.ln(3)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # --- Tittel ---
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "KALKYLE", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 12)
    tjeneste = data.get("tjeneste", "Flisarbeider")
    pdf.cell(0, 6, f"{tjeneste} - Badrehabilitering", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # --- Prosjektinfo ---
    info_felter = [
        ("Prosjekt:", data.get("adresse", "")),
        ("Dato:", datetime.date.today().strftime("%d.%m.%Y")),
        ("Gulvareal:", f"{data.get('gulvareal', 0):.2f} m\u00b2"),
        ("Veggareal:", f"{data.get('veggareal', 0):.2f} m\u00b2"),
    ]
    for etikett, verdi in info_felter:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(28, 6, etikett)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, verdi, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(8)

    # --- Tabell ---
    kol_b = [80, 23, 18, 32, 37]  # totalbredde = 190
    overskrifter = ["Beskrivelse", "Mengde", "Enhet", "Enh.pris", "Sum"]

    # Overskriftsrad
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(50, 50, 50)
    pdf.set_text_color(255, 255, 255)
    for i, h in enumerate(overskrifter):
        pdf.cell(kol_b[i], 7, h, border=1, fill=True, align="C")
    pdf.ln()

    # Datarader
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)

    skravur = False
    for post in data.get("poster", []):
        if post["mengde"] <= 0:
            continue
        if skravur:
            pdf.set_fill_color(245, 245, 245)
        else:
            pdf.set_fill_color(255, 255, 255)

        pdf.cell(kol_b[0], 6, post["navn"], border=1, fill=True)
        pdf.cell(kol_b[1], 6, f"{post['mengde']:.2f}", border=1, fill=True, align="R")
        pdf.cell(kol_b[2], 6, post["enhet"], border=1, fill=True, align="C")
        pdf.cell(kol_b[3], 6, fmt(post["pris"]), border=1, fill=True, align="R")
        pdf.cell(kol_b[4], 6, fmt(post["total"]), border=1, fill=True, align="R")
        pdf.ln()
        skravur = not skravur

    # Epoxyfug
    epoxy_pris = data.get("epoxy_pris", 0)
    if epoxy_pris > 0:
        if skravur:
            pdf.set_fill_color(245, 245, 245)
        else:
            pdf.set_fill_color(255, 255, 255)
        pdf.cell(kol_b[0], 6, "Epoxyfug", border=1, fill=True)
        pdf.cell(kol_b[1], 6, "1", border=1, fill=True, align="R")
        pdf.cell(kol_b[2], 6, "stk", border=1, fill=True, align="C")
        pdf.cell(kol_b[3], 6, fmt(epoxy_pris), border=1, fill=True, align="R")
        pdf.cell(kol_b[4], 6, fmt(epoxy_pris), border=1, fill=True, align="R")
        pdf.ln()

    pdf.ln(5)

    # --- Totaler ---
    tom_bredde = sum(kol_b[:3])
    etikett_b = kol_b[3]
    verdi_b = kol_b[4]

    subtotal = data.get("subtotal", 0)
    mva = data.get("mva", 0)
    total_inkl = data.get("total_inkl", 0)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(tom_bredde, 6, "")
    pdf.cell(etikett_b, 6, "Sum eks. mva:", align="R")
    pdf.cell(verdi_b, 6, f"{fmt(subtotal)} kr", align="R")
    pdf.ln()

    pdf.cell(tom_bredde, 6, "")
    pdf.cell(etikett_b, 6, "MVA 25%:", align="R")
    pdf.cell(verdi_b, 6, f"{fmt(mva)} kr", align="R")
    pdf.ln()

    pdf.set_draw_color(0, 0, 0)
    pdf.line(10 + tom_bredde, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(1)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(tom_bredde, 8, "")
    pdf.cell(etikett_b, 8, "Total inkl. mva:", align="R")
    pdf.cell(verdi_b, 8, f"{fmt(total_inkl)} kr", align="R")

    return bytes(pdf.output())


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------

def generer_excel(data):
    wb = Workbook()
    ws = wb.active
    ws.title = "Kalkyle"

    # Stiler
    header_font = Font(name="Calibri", bold=True, size=14)
    title_font = Font(name="Calibri", bold=True, size=16)
    normal_font = Font(name="Calibri", size=11)
    bold_font = Font(name="Calibri", bold=True, size=11)
    total_font = Font(name="Calibri", bold=True, size=13)
    th_font = Font(name="Calibri", bold=True, color="FFFFFF", size=10)
    th_fill = PatternFill(start_color="333333", end_color="333333", fill_type="solid")
    tynn = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    ws.column_dimensions["A"].width = 35
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 10
    ws.column_dimensions["D"].width = 15
    ws.column_dimensions["E"].width = 18

    rad = 1

    # Firmaheader
    ws.cell(row=rad, column=1, value=FIRMA["navn"]).font = header_font
    rad += 1
    ws.cell(row=rad, column=1, value=f"Org.nr: {FIRMA['orgnr']}  |  Tlf: {FIRMA['telefon']}").font = normal_font
    rad += 1
    ws.cell(row=rad, column=1, value=f"{FIRMA['adresse']}  |  {FIRMA['epost']}").font = normal_font
    rad += 2

    # Tittel
    ws.cell(row=rad, column=1, value="KALKYLE").font = title_font
    rad += 1
    tjeneste = data.get("tjeneste", "Flisarbeider")
    ws.cell(row=rad, column=1, value=f"{tjeneste} - Badrehabilitering").font = normal_font
    rad += 2

    # Prosjektinfo
    felter = [
        ("Prosjekt:", data.get("adresse", "")),
        ("Dato:", datetime.date.today().strftime("%d.%m.%Y")),
        ("Gulvareal:", f"{data.get('gulvareal', 0):.2f} m\u00b2"),
        ("Veggareal:", f"{data.get('veggareal', 0):.2f} m\u00b2"),
    ]
    for etikett, verdi in felter:
        ws.cell(row=rad, column=1, value=etikett).font = bold_font
        ws.cell(row=rad, column=2, value=verdi).font = normal_font
        rad += 1
    rad += 1

    # Tabelloverskrift
    for kol, h in enumerate(["Beskrivelse", "Mengde", "Enhet", "Enhetspris", "Sum"], 1):
        c = ws.cell(row=rad, column=kol, value=h)
        c.font = th_font
        c.fill = th_fill
        c.border = tynn
        c.alignment = Alignment(horizontal="center")
    rad += 1

    # Datarader
    for post in data.get("poster", []):
        if post["mengde"] <= 0:
            continue
        ws.cell(row=rad, column=1, value=post["navn"]).border = tynn

        c = ws.cell(row=rad, column=2, value=post["mengde"])
        c.border = tynn
        c.number_format = "0.00"
        c.alignment = Alignment(horizontal="right")

        ws.cell(row=rad, column=3, value=post["enhet"]).border = tynn

        c = ws.cell(row=rad, column=4, value=post["pris"])
        c.border = tynn
        c.number_format = "#,##0"
        c.alignment = Alignment(horizontal="right")

        c = ws.cell(row=rad, column=5, value=post["total"])
        c.border = tynn
        c.number_format = "#,##0"
        c.alignment = Alignment(horizontal="right")

        rad += 1

    # Epoxyfug
    epoxy_pris = data.get("epoxy_pris", 0)
    if epoxy_pris > 0:
        ws.cell(row=rad, column=1, value="Epoxyfug").border = tynn
        c = ws.cell(row=rad, column=2, value=1)
        c.border = tynn
        c.alignment = Alignment(horizontal="right")
        ws.cell(row=rad, column=3, value="stk").border = tynn
        c = ws.cell(row=rad, column=4, value=epoxy_pris)
        c.border = tynn
        c.number_format = "#,##0"
        c.alignment = Alignment(horizontal="right")
        c = ws.cell(row=rad, column=5, value=epoxy_pris)
        c.border = tynn
        c.number_format = "#,##0"
        c.alignment = Alignment(horizontal="right")
        rad += 1

    rad += 1

    # Totaler
    subtotal = data.get("subtotal", 0)
    mva = data.get("mva", 0)
    total_inkl = data.get("total_inkl", 0)

    ws.cell(row=rad, column=4, value="Sum eks. mva:").font = bold_font
    c = ws.cell(row=rad, column=5, value=subtotal)
    c.font = bold_font
    c.number_format = "#,##0"
    c.alignment = Alignment(horizontal="right")
    rad += 1

    ws.cell(row=rad, column=4, value="MVA 25%:").font = normal_font
    c = ws.cell(row=rad, column=5, value=mva)
    c.font = normal_font
    c.number_format = "#,##0"
    c.alignment = Alignment(horizontal="right")
    rad += 1

    ws.cell(row=rad, column=4, value="Total inkl. mva:").font = total_font
    c = ws.cell(row=rad, column=5, value=total_inkl)
    c.font = total_font
    c.number_format = "#,##0"
    c.alignment = Alignment(horizontal="right")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
