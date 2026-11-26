# Reporte de evaluación

2026-11-26 · `LLM_MODE=record` · `gemini-2.5-flash` · 150 documentos

## Resumen por variante

| Variante | Docs | Errores | Clasificación | Exactitud | Alucinación | Calibración `high` | high / medium / low | Llamadas LLM | Tokens entrada | Tokens salida | Latencia ms |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| clean | 50 | 0 | 100.0% | 100.0% | 0.0% | 100.0% | 97.7% / 2.3% / 0.0% | 1 | 383 | 927 | 4,617 |
| scanned | 50 | 0 | 100.0% | 98.7% | 0.0% | 99.0% | 78.0% / 20.2% / 1.8% | 1 | 917 | 1,317 | 10,892 |
| watermark | 50 | 0 | 100.0% | 98.5% | 0.0% | 98.7% | 73.3% / 20.7% / 5.9% | 2 | 1,311 | 1,768 | 14,240 |
| **total** | 150 | 0 | 100.0% | 99.1% | 0.0% | 99.3% | 83.0% / 14.4% / 2.6% | 1 | 870 | 1,337 | 9,916 |

- **Exactitud:** valor normalizado igual al esperado, sobre los campos que tienen valor.
- **Alucinación:** valor publicado donde el esperado es `null`.
- **Calibración:** exactitud de los valores publicados con `confidence: high`.
- Tokens, llamadas y latencia: promedio por documento. Con `LLM_MODE=recorded` la latencia no incluye al LLM.

## Exactitud por campo

| Campo | clean | scanned | watermark |
|---|---:|---:|---:|
| `currency` | 100.0% (30) | 100.0% (30) | 100.0% (30) |
| `due_date` | 100.0% (18) | 100.0% (18) | 100.0% (18) |
| `education[].degree` | 100.0% (32) | 100.0% (32) | 96.9% (32) |
| `education[].graduation_year` | 100.0% (32) | 100.0% (32) | 100.0% (32) |
| `education[].institution` | 100.0% (32) | 100.0% (32) | 100.0% (32) |
| `email` | 100.0% (20) | 100.0% (20) | 100.0% (20) |
| `experience[].company` | 100.0% (42) | 88.1% (42) | 85.7% (42) |
| `experience[].end_date` | 100.0% (30) | 100.0% (30) | 100.0% (30) |
| `experience[].start_date` | 100.0% (42) | 100.0% (42) | 100.0% (42) |
| `experience[].title` | 100.0% (42) | 100.0% (42) | 100.0% (42) |
| `invoice_number` | 100.0% (30) | 100.0% (30) | 100.0% (30) |
| `issue_date` | 100.0% (30) | 100.0% (30) | 100.0% (30) |
| `issuer_name` | 100.0% (30) | 93.3% (30) | 93.3% (30) |
| `issuer_tax_id` | 100.0% (30) | 100.0% (30) | 96.7% (30) |
| `line_items[].amount` | 100.0% (116) | 100.0% (116) | 100.0% (116) |
| `line_items[].description` | 100.0% (116) | 98.3% (116) | 99.1% (116) |
| `line_items[].quantity` | 100.0% (116) | 100.0% (116) | 99.1% (116) |
| `line_items[].unit_price` | 100.0% (116) | 100.0% (116) | 100.0% (116) |
| `location` | 100.0% (17) | 94.1% (17) | 94.1% (17) |
| `name` | 100.0% (20) | 100.0% (20) | 100.0% (20) |
| `phone` | 100.0% (18) | 100.0% (18) | 100.0% (18) |
| `receiver_name` | 100.0% (30) | 100.0% (30) | 96.7% (30) |
| `receiver_tax_id` | 100.0% (26) | 76.9% (26) | 92.3% (26) |
| `skills[]` | 100.0% (115) | 100.0% (115) | 98.3% (115) |
| `subtotal` | 100.0% (30) | 100.0% (30) | 100.0% (30) |
| `summary` | 100.0% (15) | 100.0% (15) | 93.3% (15) |
| `tax` | 100.0% (30) | 100.0% (30) | 100.0% (30) |
| `total` | 100.0% (30) | 100.0% (30) | 100.0% (30) |

## Alucinación por campo

Valores publicados / casos donde el campo no existe en el documento.

| Campo | clean | scanned | watermark |
|---|---:|---:|---:|
| `due_date` | 0/12 | 0/12 | 0/12 |
| `experience[].end_date` | 0/12 | 0/12 | 0/12 |
| `location` | 0/3 | 0/3 | 0/3 |
| `phone` | 0/2 | 0/2 | 0/2 |
| `receiver_tax_id` | 0/4 | 0/4 | 0/4 |
| `summary` | 0/5 | 0/5 | 0/5 |

## Errores (35; se muestran hasta 40)

| Documento | Variante | Campo | Esperado | Obtenido | Confianza |
|---|---|---|---|---|---|
| invoice_003 | watermark | `line_items[1].quantity` | 1.0 | null | — |
| invoice_004 | scanned | `issuer_name` | "Club Ojeda-Jimínez" | "Club Ojeda-Jiménez" | medium |
| invoice_004 | watermark | `issuer_name` | "Club Ojeda-Jimínez" | "Club Ojeda-Jiménez" | medium |
| invoice_005 | scanned | `receiver_tax_id` | "RRI120417RPN" | "RR1120417RPN" | high |
| invoice_007 | watermark | `issuer_tax_id` | "OAX320605GWB" | "0AX320605GWB" | high |
| invoice_011 | scanned | `receiver_tax_id` | "GRO3612228RB" | "GR03612228RB" | high |
| invoice_012 | scanned | `receiver_tax_id` | "GMB760531AO0" | "GMB760531A00" | high |
| invoice_012 | watermark | `receiver_tax_id` | "GMB760531AO0" | "GMB760531A00" | high |
| invoice_016 | scanned | `issuer_name` | "Corporacin Barrientos-Guevara" | "Corporación Barrientos-Guevara" | medium |
| invoice_016 | scanned | `receiver_tax_id` | "DEI01031076Z" | "DE101031076Z" | high |
| invoice_026 | scanned | `receiver_tax_id` | "UHI761108S4I" | "UHI761108S41" | high |
| invoice_026 | watermark | `receiver_name` | "Proyectos Lebrón y Soliz" | "Proyectos Lebron y Soliz" | high |
| invoice_026 | watermark | `receiver_tax_id` | "UHI761108S4I" | "UHI761108S41" | high |
| invoice_027 | scanned | `line_items[0].description` | "Auditoría de seguridad" | "Auditoria de seguridad" | high |
| invoice_027 | scanned | `receiver_tax_id` | "NBG740425QO1" | "NBG740425Q01" | high |
| invoice_027 | watermark | `issuer_name` | "Corporacin Maya, Toledo y Blanco" | "Corporación Maya, Toledo y Blanco" | medium |
| invoice_029 | scanned | `line_items[1].description` | "Auditoría de seguridad" | "Auditoria de seguridad" | high |
| invoice_029 | watermark | `line_items[1].description` | "Auditoría de seguridad" | "Auditoria de seguridad" | high |
| resume_000 | scanned | `experience[0].company` | "Hernádez, Bonilla y Rodrígez" | "Hernández, Bonilla y Rodríguez" | medium |
| resume_000 | scanned | `location` | "San Barbara de la Montaña, Chihuahua" | "San Bárbara de la Montaña, Chihuahua" | medium |
| resume_000 | watermark | `experience[0].company` | "Hernádez, Bonilla y Rodrígez" | "Hernández, Bonilla y Rodríguez" | medium |
| resume_004 | watermark | `experience[0].company` | "Corporacin Heredia, Godoy y Casárez" | "Corporación Heredia, Godoy y Casárez" | medium |
| resume_005 | watermark | `education[0].degree` | "Maestría en Ciencia de Datos" | "Maestria en Ciencia de Datos" | high |
| resume_005 | watermark | `experience[2].company` | "Laboratorios Castro, Salas y Candelaria" | "Laboratorios Castro,Salas y Candelaria" | high |
| resume_005 | watermark | `location` | "San Estela los bajos, Oaxaca" | "San Estela losbajos,Oaxaca" | high |
| resume_005 | watermark | `skills[2]` | "Power BI" | "Power Bl" | high |
| resume_005 | watermark | `skills[4]` | "Inglés avanzado" | "Ingles avanzado" | high |
| resume_005 | watermark | `summary` | "Ingeniero de Software con 10 años de experiencia. Especialista en SQL, Figma y Power BI." | "Ingeniero de Software con 10 anos de experiencia. Especialista en SQL, Figma y Power Bl." | high |
| resume_006 | scanned | `experience[0].company` | "Magaña, Varela y Balderas" | "Magana, Varela y Balderas" | high |
| resume_009 | scanned | `experience[0].company` | "Rodrígez-Montero" | "Rodríguez-Montero" | medium |
| resume_009 | watermark | `experience[0].company` | "Rodrígez-Montero" | "Rodríguez-Montero" | medium |
| resume_015 | scanned | `experience[1].company` | "Gaona-Espinal S. R.L. de C.V." | "Gaona-Espinal S. R. L. de C. V." | high |
| resume_015 | scanned | `experience[2].company` | "Llamas y Godínez S. R.L. de C.V." | "Llamas y Godínez S. R. L. de C. V." | medium |
| resume_015 | watermark | `experience[1].company` | "Gaona-Espinal S. R.L. de C.V." | "Gaona-Espinal S.R.L. de C.V." | high |
| resume_015 | watermark | `experience[2].company` | "Llamas y Godínez S. R.L. de C.V." | "Llamas y Godínez S.R.L. de C.V." | medium |
