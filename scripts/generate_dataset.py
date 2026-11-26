"""Genera el dataset sintético de evaluación.

Cada documento queda en <out>/<tipo>_<n>/ con clean.pdf, scanned.pdf, watermark.pdf
y ground_truth.json. Misma semilla, mismo dataset.

    python scripts/generate_dataset.py --invoices 30 --resumes 20
"""

import argparse
import json
import random
import string
import time
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

import pypdfium2 as pdfium
from faker import Faker
from PIL import Image, ImageChops, ImageDraw, ImageFont
from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.doc_types.invoice import Invoice, LineItem
from app.doc_types.resume import Education, Experience, Resume

rl_config.invariant = 1  # sin fechas ni IDs aleatorios en el PDF
DPI = 150
LATEST = date(2025, 6, 1)  # ninguna fecha del dataset pasa de aquí
FIXED_TS = time.gmtime(1735689600)  # 2025-01-01, fecha fija en los PDFs escaneados
STYLES = getSampleStyleSheet()
MONTHS = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]  # fmt: skip
PRODUCTS = [
    "Servicio de consultoría", "Licencia de software anual", "Soporte técnico mensual",
    "Desarrollo de módulo", "Capacitación en sitio", "Hosting administrado",
    "Mantenimiento preventivo", "Auditoría de seguridad", "Diseño de interfaz",
]  # fmt: skip
TITLES = [
    "Desarrollador Backend", "Analista de Datos", "Gerente de Proyectos", "Contador Senior",
    "Diseñador UX", "Ingeniero de Software", "Ejecutivo de Ventas", "Administrador de Sistemas",
]  # fmt: skip
DEGREES = [
    "Licenciatura en Informática", "Ingeniería en Sistemas", "Licenciatura en Contaduría",
    "Maestría en Ciencia de Datos", "Licenciatura en Administración", "Ingeniería Industrial",
]  # fmt: skip
UNIVERSITIES = [
    "Universidad Nacional Autónoma de México", "Instituto Politécnico Nacional",
    "Universidad de Guadalajara", "Tecnológico de Monterrey", "Universidad Autónoma de Nuevo León",
]  # fmt: skip
SKILLS = [
    "Python", "SQL", "Excel avanzado", "Power BI", "Docker", "Kubernetes", "Scrum",
    "Liderazgo", "Inglés avanzado", "Java", "Figma", "Negociación", "AWS", "Git",
]  # fmt: skip


def p(text: str, style: str = "BodyText") -> Paragraph:
    return Paragraph(escape(text), STYLES[style])


def money(x: float) -> str:
    return f"${x:,.2f}"


def fmt_date(d: date, rng: random.Random) -> str:
    return rng.choice(
        [d.strftime("%d/%m/%Y"), d.isoformat(), f"{d.day} de {MONTHS[d.month - 1]} de {d.year}"]
    )


def fmt_year_month(ym: str, rng: random.Random) -> str:
    year, month = ym.split("-")
    name = MONTHS[int(month) - 1]
    return rng.choice([f"{month}/{year}", f"{name[:3]} {year}", f"{name} {year}"])


def ym(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def fake_rfc(rng: random.Random) -> str:
    """RFC de persona moral: 3 letras, fecha AAMMDD y homoclave. No usa `Faker.rfc`, que
    calcula la fecha a partir de hoy y cambiaría el dataset de un día a otro."""
    founded = date(1960, 1, 1) + timedelta(days=rng.randint(0, 365 * 60))
    letters = "".join(rng.choices(string.ascii_uppercase, k=3))
    homoclave = "".join(rng.choices(string.ascii_uppercase + string.digits, k=3))
    return f"{letters}{founded:%y%m%d}{homoclave}"


def fake_invoice(fake: Faker, rng: random.Random) -> Invoice:
    items = []
    for _ in range(rng.randint(1, 6)):
        qty, price = rng.randint(1, 10), round(rng.uniform(50, 5000), 2)
        items.append(
            LineItem(
                description=rng.choice(PRODUCTS),
                quantity=qty,
                unit_price=price,
                amount=round(qty * price, 2),
            )
        )
    subtotal = round(sum(i.amount for i in items), 2)
    tax = round(subtotal * 0.16, 2)
    # sin Faker.date_between: usa randint en Windows y uniform en Linux, y da otra fecha
    first = date(2023, 1, 1)
    issued = first + timedelta(days=rng.randint(0, (LATEST - timedelta(days=60) - first).days))
    return Invoice(
        issuer_name=fake.company(),
        issuer_tax_id=fake_rfc(rng),
        receiver_name=fake.company(),
        receiver_tax_id=fake_rfc(rng) if rng.random() > 0.2 else None,
        invoice_number=f"{rng.choice('ABCF')}-{rng.randint(100, 99999)}",
        issue_date=issued,
        due_date=issued + timedelta(days=rng.choice([15, 30, 45])) if rng.random() > 0.3 else None,
        currency=rng.choice(["MXN", "USD"]),
        line_items=items,
        subtotal=subtotal,
        tax=tax,
        total=round(subtotal + tax, 2),
    )


def render_invoice(inv: Invoice, path: Path, rng: random.Random) -> None:
    story = [p(inv.issuer_name, "Title"), p(f"RFC: {inv.issuer_tax_id}"), Spacer(1, 12)]
    story += [
        p(f"Factura No. {inv.invoice_number}", "Heading2"),
        p(f"Fecha de emisión: {fmt_date(inv.issue_date, rng)}"),
    ]
    if inv.due_date:
        story.append(p(f"Fecha de vencimiento: {fmt_date(inv.due_date, rng)}"))
    story += [p(f"Moneda: {inv.currency}"), Spacer(1, 12), p("Cliente", "Heading3")]
    story.append(p(inv.receiver_name))
    if inv.receiver_tax_id:
        story.append(p(f"RFC: {inv.receiver_tax_id}"))
    rows = [["Descripción", "Cantidad", "Precio unitario", "Importe"]]
    rows += [
        [i.description, f"{i.quantity:g}", money(i.unit_price), money(i.amount)]
        for i in inv.line_items
    ]
    rows += [
        ["", "", "Subtotal", money(inv.subtotal)],
        ["", "", "IVA 16%", money(inv.tax)],
        ["", "", "TOTAL", money(inv.total)],
    ]
    table = Table(rows, colWidths=[220, 70, 100, 100])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -4), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (2, -1), (-1, -1), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ]
        )
    )
    story += [Spacer(1, 18), table]
    SimpleDocTemplate(str(path), pagesize=letter).build(story)


def fake_resume(fake: Faker, rng: random.Random) -> Resume:
    experience = []
    start = date(rng.randint(2008, 2016), rng.randint(1, 12), 1)
    first_year = start.year
    jobs = rng.randint(1, 4)
    for k in range(jobs):
        end = start + timedelta(days=rng.randint(300, 1500))
        current = end >= LATEST or (k == jobs - 1 and rng.random() < 0.5)
        experience.append(
            Experience(
                company=fake.company(),
                title=rng.choice(TITLES),
                start_date=ym(start),
                end_date=None if current else ym(end),
            )
        )
        if current:
            break
        start = end + timedelta(days=rng.randint(15, 120))
    years = max(1, (LATEST if current else end).year - first_year)
    experience.reverse()  # los CVs listan lo más reciente primero
    education = [
        Education(
            institution=rng.choice(UNIVERSITIES),
            degree=degree,
            graduation_year=first_year - rng.randint(0, 2),
        )
        for degree in rng.sample(DEGREES, rng.randint(1, 2))
    ]
    skills = rng.sample(SKILLS, rng.randint(3, 8))
    return Resume(
        name=fake.name(),
        email=fake.free_email(),
        phone=fake.phone_number() if rng.random() > 0.2 else None,
        location=f"{fake.city()}, {fake.state()}" if rng.random() > 0.2 else None,
        summary=fake_summary(experience[0], years, skills, rng) if rng.random() > 0.3 else None,
        experience=experience,
        education=education,
        skills=skills,
    )


def fake_summary(latest: Experience, years: int, skills: list[str], rng: random.Random) -> str:
    """Resumen coherente con el CV: puesto más reciente, años de experiencia y habilidades."""
    span = f"{years} año" if years == 1 else f"{years} años"
    top = f"{', '.join(skills[:2])} y {skills[2]}"
    return rng.choice(
        [
            f"{latest.title} con {span} de experiencia. Especialista en {top}.",
            f"Profesional con {span} de trayectoria; último puesto: {latest.title} "
            f"en {latest.company}, con dominio de {top}.",
            f"{latest.title} enfocado en resultados, con {span} de experiencia "
            f"y conocimientos sólidos de {top}.",
        ]
    )


def render_resume(cv: Resume, path: Path, rng: random.Random) -> None:
    story = [p(cv.name, "Title"), p(cv.email)]
    story += [p(x) for x in (cv.phone, cv.location) if x]
    if cv.summary:
        story += [p("Perfil", "Heading2"), p(cv.summary)]
    story.append(p("Experiencia", "Heading2"))
    for e in cv.experience:
        end = fmt_year_month(e.end_date, rng) if e.end_date else "Actual"
        story += [
            p(f"{e.title} — {e.company}", "Heading4"),
            p(f"{fmt_year_month(e.start_date, rng)} – {end}"),
        ]
    story.append(p("Educación", "Heading2"))
    story += [p(f"{e.degree}, {e.institution} ({e.graduation_year})") for e in cv.education]
    story += [p("Habilidades", "Heading2"), p(", ".join(cv.skills))]
    SimpleDocTemplate(str(path), pagesize=letter).build(story)


def rasterize(pdf_path: Path) -> list[Image.Image]:
    pdf = pdfium.PdfDocument(pdf_path)
    try:
        return [page.render(scale=DPI / 72).to_pil().convert("L") for page in pdf]
    finally:
        pdf.close()


def degrade(img: Image.Image, rng: random.Random) -> Image.Image:
    """Simula un escaneo: rotación leve y ruido."""
    img = img.rotate(rng.uniform(-1.5, 1.5), resample=Image.Resampling.BICUBIC, fillcolor=255)
    noise = Image.frombytes("L", img.size, rng.randbytes(img.width * img.height))
    return Image.blend(img, noise, 0.12)


def add_watermark(img: Image.Image) -> Image.Image:
    mark = Image.new("L", img.size, 255)
    font = ImageFont.load_default(size=img.width // 8)
    ImageDraw.Draw(mark).text(
        (img.width / 2, img.height / 2), "CONFIDENCIAL", fill=170, font=font, anchor="mm"
    )
    mark = mark.rotate(45, resample=Image.Resampling.BICUBIC, fillcolor=255)
    return ImageChops.darker(img, mark)


def save_pdf(pages: list[Image.Image], path: Path) -> None:
    pages[0].save(
        path,
        "PDF",
        resolution=DPI,
        save_all=True,
        append_images=pages[1:],
        creationDate=FIXED_TS,
        modDate=FIXED_TS,
    )


def generate(out: Path, invoices: int, resumes: int, seed: int = 42) -> None:
    fake = Faker("es_MX")
    jobs = [("invoice", n, fake_invoice, render_invoice) for n in range(invoices)]
    jobs += [("resume", n, fake_resume, render_resume) for n in range(resumes)]
    for kind, n, make, render in jobs:
        # cada documento con su propia semilla: no depende de cuántos se generen antes
        key = f"{seed}-{kind}-{n}"
        fake.seed_instance(key)
        rng = random.Random(key)
        doc_dir = out / f"{kind}_{n:03d}"
        doc_dir.mkdir(parents=True, exist_ok=True)
        doc = make(fake, rng)
        render(doc, doc_dir / "clean.pdf", rng)
        pages = rasterize(doc_dir / "clean.pdf")
        save_pdf([degrade(pg, rng) for pg in pages], doc_dir / "scanned.pdf")
        save_pdf([degrade(add_watermark(pg), rng) for pg in pages], doc_dir / "watermark.pdf")
        truth = {"doc_type": kind, "fields": doc.model_dump(mode="json")}
        (doc_dir / "ground_truth.json").write_text(
            json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("eval/dataset"))
    parser.add_argument("--invoices", type=int, default=30)
    parser.add_argument("--resumes", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    generate(args.out, args.invoices, args.resumes, args.seed)


if __name__ == "__main__":
    main()
