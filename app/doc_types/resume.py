"""CV: modelo de extracción, palabras clave de clasificación y reglas."""

import re
from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field

YearMonth = Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="AAAA-MM")]


class Experience(BaseModel):
    company: str | None = Field(None, description="Empresa")
    title: str | None = Field(None, description="Puesto")
    start_date: YearMonth | None = Field(None, description="Inicio, AAAA-MM")
    end_date: YearMonth | None = Field(
        None, description="Fin, AAAA-MM; null si es el puesto actual o no aparece"
    )


class Education(BaseModel):
    institution: str | None = Field(None, description="Institución")
    degree: str | None = Field(None, description="Título o grado")
    graduation_year: int | None = Field(None, description="Año de egreso")


class Resume(BaseModel):
    name: str | None = Field(None, description="Nombre completo")
    email: str | None = Field(None, description="Correo electrónico")
    phone: str | None = Field(None, description="Teléfono")
    location: str | None = Field(None, description="Ciudad o ubicación")
    summary: str | None = Field(None, description="Resumen o perfil profesional")
    experience: list[Experience] = Field(default_factory=list, description="Experiencia laboral")
    education: list[Education] = Field(default_factory=list, description="Educación")
    skills: list[str] = Field(default_factory=list, description="Habilidades")


LABEL = "CV (currículum)"
MODEL = Resume
IDENTIFIERS = {"email", "phone"}
LABELS: dict[str, tuple[str, ...]] = {}  # sin montos ni fechas de nivel superior
KEYWORDS = (
    "curriculum",
    "experiencia",
    "educación",
    "habilidades",
    "perfil",
    "experience",
    "education",
    "skills",
)


# Reglas: devuelven (passed, detail) o None si faltan los datos para evaluarlas.
Result = tuple[bool, str | None] | None
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def email_format(cv: Resume) -> Result:
    if cv.email is None:
        return None
    ok = EMAIL.fullmatch(cv.email.strip()) is not None
    return ok, None if ok else cv.email


def experience_dates_ordered(cv: Resume) -> Result:
    pairs = [(n, e) for n, e in enumerate(cv.experience) if e.start_date and e.end_date]
    if not pairs:
        return None
    bad = [f"experience[{n}]" for n, e in pairs if e.start_date > e.end_date]  # AAAA-MM ordena
    return not bad, ", ".join(bad) or None


def no_future_dates(cv: Resume, today: date | None = None) -> Result:
    today = today or date.today()
    month = f"{today:%Y-%m}"
    dates = {
        f"experience[{n}].{k}": v
        for n, e in enumerate(cv.experience)
        for k, v in (("start_date", e.start_date), ("end_date", e.end_date))
        if v
    }
    years = {
        f"education[{n}].graduation_year": e.graduation_year
        for n, e in enumerate(cv.education)
        if e.graduation_year is not None
    }
    if not dates and not years:
        return None
    bad = [k for k, v in dates.items() if v > month]
    bad += [k for k, v in years.items() if v > today.year]
    return not bad, ", ".join(bad) or None


RULES = (email_format, experience_dates_ordered, no_future_dates)
