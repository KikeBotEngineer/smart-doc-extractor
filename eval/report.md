# Reporte de evaluación

2026-11-26 · `LLM_MODE=record` · `gemini-2.5-flash` · 150 documentos

## Resumen por variante

| Variante | Docs | Errores | Clasificación | Exactitud | Alucinación | Calibración `high` | high / medium / low | Llamadas LLM | Tokens entrada | Tokens salida | Latencia ms |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| clean | 50 | 0 | 100.0% | 100.0% | 0.0% | 100.0% | 99.3% / 0.7% / 0.0% | 1 | 365 | 982 | 4,612 |
| scanned | 50 | 0 | 100.0% | 99.2% | 0.0% | 99.3% | 78.8% / 19.8% / 1.5% | 1 | 894 | 1,296 | 10,629 |
| watermark | 50 | 0 | 100.0% | 98.9% | 0.0% | 99.2% | 74.4% / 20.2% / 5.5% | 2 | 1,246 | 1,547 | 21,214 |
| **total** | 150 | 0 | 100.0% | 99.4% | 0.0% | 99.6% | 84.2% / 13.5% / 2.3% | 1 | 835 | 1,275 | 12,152 |

- **Exactitud:** valor normalizado igual al esperado, sobre los campos que tienen valor.
- **Alucinación:** valor publicado donde el esperado es `null`.
- **Calibración:** exactitud de los valores publicados con `confidence: high`.
- Tokens, llamadas y latencia: promedio por documento. Con `LLM_MODE=recorded` la latencia no incluye al LLM.

## Exactitud por campo

| Campo | clean | scanned | watermark |
|---|---:|---:|---:|
| `currency` | 100.0% (30) | 100.0% (30) | 100.0% (30) |
| `due_date` | 100.0% (21) | 100.0% (21) | 100.0% (21) |
| `education[].degree` | 100.0% (31) | 100.0% (31) | 100.0% (31) |
| `education[].graduation_year` | 100.0% (31) | 100.0% (31) | 100.0% (31) |
| `education[].institution` | 100.0% (31) | 100.0% (31) | 100.0% (31) |
| `email` | 100.0% (20) | 100.0% (20) | 100.0% (20) |
| `experience[].company` | 100.0% (49) | 95.9% (49) | 89.8% (49) |
| `experience[].end_date` | 100.0% (36) | 100.0% (36) | 100.0% (36) |
| `experience[].start_date` | 100.0% (49) | 100.0% (49) | 100.0% (49) |
| `experience[].title` | 100.0% (49) | 100.0% (49) | 100.0% (49) |
| `invoice_number` | 100.0% (30) | 100.0% (30) | 100.0% (30) |
| `issue_date` | 100.0% (30) | 100.0% (30) | 100.0% (30) |
| `issuer_name` | 100.0% (30) | 96.7% (30) | 100.0% (30) |
| `issuer_tax_id` | 100.0% (30) | 93.3% (30) | 96.7% (30) |
| `line_items[].amount` | 100.0% (94) | 100.0% (94) | 100.0% (94) |
| `line_items[].description` | 100.0% (94) | 98.9% (94) | 98.9% (94) |
| `line_items[].quantity` | 100.0% (94) | 100.0% (94) | 98.9% (94) |
| `line_items[].unit_price` | 100.0% (94) | 100.0% (94) | 100.0% (94) |
| `location` | 100.0% (19) | 100.0% (19) | 100.0% (19) |
| `name` | 100.0% (20) | 100.0% (20) | 100.0% (20) |
| `phone` | 100.0% (15) | 100.0% (15) | 100.0% (15) |
| `receiver_name` | 100.0% (30) | 96.7% (30) | 93.3% (30) |
| `receiver_tax_id` | 100.0% (23) | 91.3% (23) | 91.3% (23) |
| `skills[]` | 100.0% (118) | 100.0% (118) | 100.0% (118) |
| `subtotal` | 100.0% (30) | 100.0% (30) | 100.0% (30) |
| `summary` | 100.0% (14) | 100.0% (14) | 92.9% (14) |
| `tax` | 100.0% (30) | 100.0% (30) | 100.0% (30) |
| `total` | 100.0% (30) | 100.0% (30) | 100.0% (30) |

## Alucinación por campo

Valores publicados / casos donde el campo no existe en el documento.

| Campo | clean | scanned | watermark |
|---|---:|---:|---:|
| `due_date` | 0/9 | 0/9 | 0/9 |
| `experience[].end_date` | 0/13 | 0/13 | 0/13 |
| `location` | 0/1 | 0/1 | 0/1 |
| `phone` | 0/5 | 0/5 | 0/5 |
| `receiver_tax_id` | 0/7 | 0/7 | 0/7 |
| `summary` | 0/6 | 0/6 | 0/6 |

## Errores (22; se muestran hasta 40)

| Documento | Variante | Campo | Esperado | Obtenido | Confianza |
|---|---|---|---|---|---|
| invoice_008 | scanned | `receiver_name` | "Ojeda y Jimínez e Hijos" | "Ojeda y Jiménez e Hijos" | medium |
| invoice_008 | watermark | `receiver_name` | "Ojeda y Jimínez e Hijos" | "Ojeda y Jiménez e Hijos" | medium |
| invoice_010 | watermark | `line_items[2].quantity` | 7.0 | null | — |
| invoice_011 | scanned | `receiver_tax_id` | "KKO181120O1J" | "KKO18112001J" | high |
| invoice_011 | watermark | `receiver_tax_id` | "KKO181120O1J" | "KKO18112001J" | high |
| invoice_012 | scanned | `issuer_name` | "Gaona-Chavarría S. R.L. de C.V." | "Gaona-Chavarría S. R. L. de C.V." | medium |
| invoice_013 | scanned | `issuer_tax_id` | "GAI770110Q79" | "GA1770110Q79" | high |
| invoice_013 | scanned | `receiver_tax_id` | "FRY170628I6B" | "FRY17062816B" | high |
| invoice_013 | watermark | `receiver_tax_id` | "FRY170628I6B" | "FRY17062816B" | high |
| invoice_015 | scanned | `line_items[2].description` | "Auditoría de seguridad" | "Auditoria de seguridad" | high |
| invoice_015 | watermark | `line_items[2].description` | "Auditoría de seguridad" | "Auditoria de seguridad" | high |
| invoice_018 | scanned | `issuer_tax_id` | "MPO641224YYU" | "MP0641224YYU" | high |
| invoice_018 | watermark | `issuer_tax_id` | "MPO641224YYU" | "MP0641224YYU" | high |
| invoice_022 | watermark | `receiver_name` | "Corporacin Ruelas y Gallegos" | "Corporación Ruelas y Gallegos" | medium |
| resume_006 | watermark | `experience[3].company` | "Castellanos-Macías S. R.L. de C.V." | "Castellanos-Macias S.R.L. de C.V." | high |
| resume_011 | scanned | `experience[0].company` | "Rodrígez-Almaraz" | "Rodríguez-Almaraz" | medium |
| resume_011 | watermark | `experience[0].company` | "Rodrígez-Almaraz" | "Rodriguez-Almaraz" | medium |
| resume_012 | watermark | `experience[0].company` | "Marrero S. R.L. de C.V." | "Marrero S. R. L. de C. V." | high |
| resume_012 | watermark | `summary` | "Profesional con 12 años de trayectoria; último puesto: Analista de Datos en Marrero S. R.L. de C.V., con dominio de Kubernetes, Liderazgo y Git." | "Profesional con 12 años de trayectoria; último puesto: Analista de Datos en Marrero S. R. L. de C. V., con dominio de Kubernetes, Liderazgo y Git." | medium |
| resume_013 | scanned | `experience[1].company` | "Montenegro S. R.L. de C.V." | "Montenegro S.R.L. de C.V." | high |
| resume_016 | watermark | `experience[0].company` | "Corporacin Duarte y Madrid" | "Corporación Duarte y Madrid" | medium |
| resume_018 | watermark | `experience[0].company` | "Laboratorios Bonilla, Cortez y Grijalva" | "Laboratorios Bonila, Cortez y Grijalva" | high |
