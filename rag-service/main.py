from fastapi import FastAPI

app = FastAPI(title="StrandsOps RAG Service")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}