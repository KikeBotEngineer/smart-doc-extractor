# Reporte de evaluación

2026-11-26 · `LLM_MODE=record` · `gemini-2.5-flash` · 150 documentos

## Resumen por variante

| Variante | Docs | Errores | Clasificación | Exactitud | Alucinación | Calibración `high` | high / medium / low | Llamadas LLM | Tokens entrada | Tokens salida | Latencia ms |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| clean | 50 | 0 | 100.0% | 100.0% | 0.0% | 100.0% | 99.2% / 0.8% / 0.0% | 1 | 364 | 955 | 4,399 |
| scanned | 50 | 0 | 100.0% | 99.1% | 0.0% | 99.2% | 80.1% / 18.4% / 1.6% | 1 | 868 | 1,343 | 10,545 |
| watermark | 50 | 0 | 100.0% | 98.3% | 0.0% | 98.6% | 74.9% / 19.3% / 5.8% | 2 | 1,291 | 1,591 | 12,172 |
| **total** | 150 | 0 | 100.0% | 99.1% | 0.0% | 99.4% | 84.7% / 12.8% / 2.4% | 1 | 841 | 1,296 | 9,038 |

- **Exactitud:** valor normalizado igual al esperado, sobre los campos que tienen valor.
- **Alucinación:** valor publicado donde el esperado es `null`.
- **Calibración:** exactitud de los valores publicados con `confidence: high`.
- Tokens, llamadas y latencia: promedio por documento. Con `LLM_MODE=recorded` la latencia no incluye al LLM.

## Exactitud por campo

| Campo | clean | scanned | watermark |
|---|---:|---:|---:|
| `currency` | 100.0% (30) | 100.0% (30) | 100.0% (30) |
| `due_date` | 100.0% (21) | 100.0% (21) | 100.0% (21) |
| `education[].degree` | 100.0% (29) | 100.0% (29) | 100.0% (29) |
| `education[].graduation_year` | 100.0% (29) | 100.0% (29) | 100.0% (29) |
| `education[].institution` | 100.0% (29) | 100.0% (29) | 100.0% (29) |
| `email` | 100.0% (20) | 100.0% (20) | 100.0% (20) |
| `experience[].company` | 100.0% (49) | 95.9% (49) | 93.9% (49) |
| `experience[].end_date` | 100.0% (37) | 100.0% (37) | 100.0% (37) |
| `experience[].start_date` | 100.0% (49) | 100.0% (49) | 100.0% (49) |
| `experience[].title` | 100.0% (49) | 100.0% (49) | 100.0% (49) |
| `invoice_number` | 100.0% (30) | 100.0% (30) | 100.0% (30) |
| `issue_date` | 100.0% (30) | 100.0% (30) | 100.0% (30) |
| `issuer_name` | 100.0% (30) | 96.7% (30) | 90.0% (30) |
| `issuer_tax_id` | 100.0% (30) | 96.7% (30) | 96.7% (30) |
| `line_items[].amount` | 100.0% (96) | 100.0% (96) | 100.0% (96) |
| `line_items[].description` | 100.0% (96) | 99.0% (96) | 94.8% (96) |
| `line_items[].quantity` | 100.0% (96) | 100.0% (96) | 99.0% (96) |
| `line_items[].unit_price` | 100.0% (96) | 100.0% (96) | 100.0% (96) |
| `location` | 100.0% (17) | 100.0% (17) | 100.0% (17) |
| `name` | 100.0% (20) | 95.0% (20) | 100.0% (20) |
| `phone` | 100.0% (18) | 100.0% (18) | 100.0% (18) |
| `receiver_name` | 100.0% (30) | 83.3% (30) | 83.3% (30) |
| `receiver_tax_id` | 100.0% (21) | 100.0% (21) | 95.2% (21) |
| `skills[]` | 100.0% (106) | 100.0% (106) | 100.0% (106) |
| `subtotal` | 100.0% (30) | 100.0% (30) | 100.0% (30) |
| `summary` | 100.0% (12) | 100.0% (12) | 91.7% (12) |
| `tax` | 100.0% (30) | 100.0% (30) | 100.0% (30) |
| `total` | 100.0% (30) | 100.0% (30) | 100.0% (30) |

## Alucinación por campo

Valores publicados / casos donde el campo no existe en el documento.

| Campo | clean | scanned | watermark |
|---|---:|---:|---:|
| `due_date` | 0/9 | 0/9 | 0/9 |
| `experience[].end_date` | 0/12 | 0/12 | 0/12 |
| `location` | 0/3 | 0/3 | 0/3 |
| `phone` | 0/2 | 0/2 | 0/2 |
| `receiver_tax_id` | 0/9 | 0/9 | 0/9 |
| `summary` | 0/8 | 0/8 | 0/8 |

## Errores (31; se muestran hasta 40)

| Documento | Variante | Campo | Esperado | Obtenido | Confianza |
|---|---|---|---|---|---|
| invoice_003 | watermark | `issuer_name` | "Corporacin Ruiz-Carranza" | "Corporación Ruiz-Carranza" | medium |
| invoice_004 | scanned | `receiver_name` | "Manzanares-Galván" | "Manzanares-Galvan" | high |
| invoice_004 | watermark | `line_items[0].description` | "Capacitación en sitio" | "Capacitacion en sitio" | high |
| invoice_004 | watermark | `receiver_name` | "Manzanares-Galván" | "Manzanares-Galvan" | high |
| invoice_005 | watermark | `receiver_tax_id` | "ZII150610UBR" | "ZI1150610UBR" | high |
| invoice_006 | scanned | `receiver_name` | "Díaz-Palacios S. R.L. de C.V." | "Díaz-Palacios S. R. L. de C. V." | medium |
| invoice_006 | watermark | `receiver_name` | "Díaz-Palacios S. R.L. de C.V." | "Díaz-Palacios S. R. L. de C.V." | medium |
| invoice_009 | scanned | `receiver_name` | "Aparicio S. R.L. de C.V." | "Aparicio S.R.L. de C.V." | high |
| invoice_009 | watermark | `receiver_name` | "Aparicio S. R.L. de C.V." | "Aparicio S.R.L. de C.V." | high |
| invoice_012 | watermark | `line_items[0].description` | "Auditoría de seguridad" | "Auditoria de seguridad" | high |
| invoice_012 | watermark | `line_items[2].description` | "Servicio de consultoría" | "Servicio de consultoria" | high |
| invoice_016 | watermark | `line_items[0].description` | "Auditoría de seguridad" | "Auditoria de seguridad" | high |
| invoice_018 | scanned | `issuer_tax_id` | "BEO700607I6E" | "BE070060716E" | high |
| invoice_018 | scanned | `receiver_name` | "Zedillo y Meraz S. R.L. de C.V." | "Zedillo y Meraz S. R. L. de C.V." | high |
| invoice_018 | watermark | `issuer_name` | "Carrión y Asociados" | "Carrion y Asociados" | high |
| invoice_018 | watermark | `issuer_tax_id` | "BEO700607I6E" | "BE070060716E" | high |
| invoice_018 | watermark | `receiver_name` | "Zedillo y Meraz S. R.L. de C.V." | "Zedillo y Meraz S. R. L. de C.V." | medium |
| invoice_019 | watermark | `line_items[0].quantity` | 8.0 | null | — |
| invoice_022 | scanned | `receiver_name` | "Osorio y Carrero S. R.L. de C.V." | "Osorio y Carrero S.R.L. de C.V." | high |
| invoice_022 | watermark | `receiver_name` | "Osorio y Carrero S. R.L. de C.V." | "Osorio y Carrero S.R.L. de C.V." | high |
| invoice_024 | watermark | `issuer_name` | "Corporacin Mateo y Prado" | "Corporación Mateo y Prado" | medium |
| invoice_025 | watermark | `line_items[1].description` | "Auditoría de seguridad" | "Auditoria de seguridad" | high |
| invoice_027 | scanned | `issuer_name` | "Corporacin Arreola y Sanches" | "Corporación Arreola y Sanches" | medium |
| invoice_029 | scanned | `line_items[0].description` | "Auditoría de seguridad" | "Auditoria de seguridad" | high |
| resume_002 | scanned | `name` | "Gabino Martín Quintana" | "Gabino Martin Quintana" | high |
| resume_004 | scanned | `experience[0].company` | "Corporacin Carreón-Rodarte" | "Corporación Carreón-Rodarte" | medium |
| resume_009 | watermark | `experience[0].company` | "Corporacin Mascareñas-Cardenas" | "Corporación Mascareñas-Cardenas" | medium |
| resume_009 | watermark | `summary` | "Profesional con 17 años de trayectoria; último puesto: Administrador de Sistemas en Corporacin Mascareñas-Cardenas, con dominio de SQL, Docker y Python." | "Profesional con 17 años de trayectoria; último puesto: Administrador de Sistemas en Corporación Mascareñas-Cardenas, con dominio de SQL, Docker y Python." | medium |
| resume_010 | watermark | `experience[1].company` | "Lomeli y Sarabia S. R.L. de C.V." | "Lomeli y Sarabia S.R.L. de C.V." | high |
| resume_012 | scanned | `experience[1].company` | "Piña S. R.L. de C.V." | "Piña S. R. L. de C.V." | medium |
| resume_012 | watermark | `experience[1].company` | "Piña S. R.L. de C.V." | "Piña S. R. L. de C. V." | low |
