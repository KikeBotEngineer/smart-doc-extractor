"""CV: modelo de extracción y palabras clave de clasificación."""

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
