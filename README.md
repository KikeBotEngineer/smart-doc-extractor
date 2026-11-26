# smart-doc-extractor

API que recibe un PDF (factura o CV) y devuelve **datos estructurados y auditables**: cada valor trae su fuente, el fragmento del documento que lo respalda y un nivel de confianza, y cada ausencia se explica.

El LLM (Gemini) lee y propone valores. Python decide: busca cada valor en el texto del documento, asigna la confianza y aplica las reglas de negocio. El diseño completo está en [ARQUITECTURA.md](ARQUITECTURA.md).

## Resultados de evaluación

150 documentos sintéticos (30 facturas y 20 CVs, en 3 variantes), `gemini-2.5-flash`. Reporte completo: [eval/report.md](eval/report.md).

| Variante | Clasificación | Exactitud | Alucinación | Calibración `high` | high / medium / low | Llamadas LLM | Latencia |
|---|---:|---:|---:|---:|---|---:|---:|
| `clean`: PDF digital | 100% | 100% | 0% | 100% | 99.3 / 0.7 / 0.0% | 1 | 4.6 s |
| `scanned`: 150 dpi, ruido, rotación | 100% | 99.2% | 0% | 99.3% | 78.8 / 19.8 / 1.5% | 1 | 10.6 s |
| `watermark`: escaneo con marca de agua | 100% | 98.9% | 0% | 99.2% | 74.4 / 20.2 / 5.5% | 2 | 21.2 s |

- **Exactitud:** valor normalizado igual al esperado. **Alucinación:** valor publicado donde el documento no lo tiene. **Calibración:** exactitud de los valores marcados `high`.
- Tokens promedio por documento: 835 de entrada y 1,275 de salida (incluye el razonamiento de 2.5-flash).

Qué muestran los errores:

- **El OCR y el LLM coinciden en el mismo error.** Casi todos los `high` incorrectos son confusiones del OCR (`O`/`0`, `I`/`1`, acentos perdidos) que Gemini copió en vez de leer la imagen. Como la evidencia se busca en ese mismo texto, la confirma. La regla `tax_id_format` marca 3 de los 7 RFC mal leídos; en los otros 4 la confusión cae en la homoclave, donde letras y dígitos son válidos.
- **Los `medium` de las variantes escaneadas son sobre todo acentos**: el modelo de OCR incluido (chino/inglés) no los reconoce. Un modelo de OCR latino los reduciría.
- **Gemini corrige la ortografía al leer imágenes** (`Hernádez` → `Hernández`) aunque el prompt lo prohíbe. Esos valores quedan en `medium` porque no coinciden con el OCR.

## Uso

Requiere Python 3.12 y una API key de Gemini.

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"        # Windows: .venv\Scripts\pip
cp .env.example .env                     # y pon tu GEMINI_API_KEY
.venv/bin/uvicorn app.main:app --reload
```

```bash
curl -F file=@factura.pdf http://localhost:8000/extract
curl -F file=@cv.pdf -F doc_type=resume http://localhost:8000/extract
```

Swagger en `/docs`. `GET /doc-types` lista los tipos con sus campos y reglas.

Respuesta (abreviada):

```json
{
  "doc_type": { "value": "invoice", "method": "keywords", "confidence": "high" },
  "route": "visual",
  "pages": [{ "page": 1, "profile": "scanned" }],
  "fields": {
    "invoice_number": {
      "value": "F-77336",
      "confidence": "high",
      "source": "ocr",
      "evidence": { "page": 1, "snippet": "Factura No.F-77336 Fecha deemision:22/06/2023" },
      "missing_reason": null
    },
    "line_items[0].description": {
      "value": "Capacitación en sitio",
      "confidence": "medium",
      "source": "ocr",
      "evidence": { "page": 1, "snippet": "Capacitacion en sitio 2 $173.80 $347.60" },
      "missing_reason": null
    },
    "due_date": {
      "value": null, "confidence": null, "source": null, "evidence": null,
      "missing_reason": "not_present"
    }
  },
  "validations": [{ "rule": "subtotal_plus_tax_equals_total", "passed": true, "detail": null }],
  "usage": { "llm_calls": 1, "input_tokens": 750, "output_tokens": 946, "latency_ms": 10833 }
}
```

| Código | Cuándo |
|---|---|
| `413` | Más de 10 MB |
| `415` | No es PDF |
| `422` | Más de 20 páginas; PDF cifrado, dañado o sin contenido; tipo no soportado |
| `502` | Gemini falló después del reintento |

## Configuración

| Variable | Default | Uso |
|---|---|---|
| `GEMINI_API_KEY` | — | Requerida en `live` y `record` |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Modelo |
| `LLM_MODE` | `live` | `live`, `recorded` (solo grabaciones, sin red) o `record` (Gemini y graba lo que falte) |
| `MAX_FILE_MB` / `MAX_PAGES` | `10` / `20` | Límites de entrada |

## Desarrollo

```bash
pytest                                        # sin red: usa respuestas grabadas
python scripts/generate_dataset.py            # 150 PDFs en eval/dataset/ (semilla fija)
LLM_MODE=recorded python eval/run_eval.py     # evaluación sin red → eval/report.md
LLM_MODE=record python eval/run_eval.py       # tras cambiar prompts o modelos: regraba
```

Cambiar un prompt o un modelo de datos deja obsoletas las grabaciones; la evaluación lo avisa y `LLM_MODE=record` las regraba (unas 200 llamadas). CI corre lint, pruebas y la evaluación completa sin red, y falla si la exactitud en `clean` baja de 99%.

## Despliegue

```bash
docker build -t smart-doc-extractor .
docker run -p 8080:8080 -e GEMINI_API_KEY=... smart-doc-extractor
```

En Cloud Run se despliega privado y con la key desde Secret Manager (`--set-secrets GEMINI_API_KEY=<secreto>:latest`). El servicio no guarda documentos ni resultados.

## Límites conocidos

- OCR en CPU: unos 4 s por página escaneada.
- La recuperación dirigida envía el documento completo, no solo la zona del campo.
- Las grabaciones de la evaluación se hicieron en Windows; en Linux el OCR puede diferir un poco, lo que mueve ligeramente las métricas de las variantes escaneadas (el umbral de CI es solo sobre `clean`).
