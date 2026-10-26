"""Donation certificate PDF generation (FR29)."""
from io import BytesIO

from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

RED = colors.HexColor("#c1121f")
BLACK = colors.HexColor("#1a1a1a")


def certificate_number(record):
    return f"BBMS-{record.donation_date.year}-{record.pk:05d}"


def user_can_download(user, record):
    if not user.is_authenticated:
        return False
    return user.role in ("STAFF", "ADMIN") or record.donor.user_id == user.pk


def build_certificate_pdf(record):
    """Return the bytes of a one-page A4 certificate for a DonationRecord."""
    donor = record.donor
    user = donor.user
    name = user.get_full_name() or user.username
    number = certificate_number(record)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    cx = width / 2

    pdf.setStrokeColor(RED)
    pdf.setLineWidth(4)
    pdf.rect(30, 30, width - 60, height - 60)
    pdf.setLineWidth(1)
    pdf.rect(40, 40, width - 80, height - 80)

    pdf.setFillColor(RED)
    pdf.setFont("Helvetica-Bold", 30)
    pdf.drawCentredString(cx, height - 150, "Certificate of Appreciation")
    pdf.setFillColor(BLACK)
    pdf.setFont("Helvetica", 16)
    pdf.drawCentredString(cx, height - 180, "Blood Bank Management System")
    pdf.setStrokeColor(RED)
    pdf.line(cx - 120, height - 195, cx + 120, height - 195)

    pdf.setFont("Helvetica", 14)
    pdf.drawCentredString(cx, height - 250, "This certificate is proudly presented to")
    pdf.setFillColor(RED)
    pdf.setFont("Helvetica-Bold", 26)
    pdf.drawCentredString(cx, height - 295, name)

    pdf.setFillColor(BLACK)
    rows = [
        ("Blood group", donor.blood_group),
        ("Donation date", record.donation_date.strftime("%d %B %Y")),
        ("Blood bank location", record.blood_bank_location),
        ("Units donated", str(record.units)),
    ]
    y = height - 370
    for label, value in rows:
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawRightString(cx - 10, y, f"{label}:")
        pdf.setFont("Helvetica", 13)
        pdf.drawString(cx + 10, y, value)
        y -= 28

    pdf.setFont("Helvetica-Oblique", 13)
    pdf.drawCentredString(cx, y - 40, "Thank you for your generous gift of blood.")
    pdf.drawCentredString(cx, y - 60, "Your donation helps save lives.")

    pdf.setFont("Helvetica", 11)
    pdf.drawString(70, 80, f"Certificate No: {number}")
    pdf.drawRightString(width - 70, 80, f"Issued: {timezone.localdate().strftime('%d %B %Y')}")

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def certificate_response(record):
    response = HttpResponse(build_certificate_pdf(record), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="BBMS-certificate-{certificate_number(record)}.pdf"'
    return response
