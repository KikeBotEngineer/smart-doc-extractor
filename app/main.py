from fastapi import FastAPI

app = FastAPI(title="smart-doc-extractor")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
