FROM python:3.12-slim

# opencv (dependencia de RapidOCR) necesita libGL y glib
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY pyproject.toml ./
COPY app ./app
COPY prompts ./prompts
# editable: el código lee prompts/ junto a app/
RUN pip install --no-cache-dir -e .

RUN useradd --system --create-home appuser
USER appuser

ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
