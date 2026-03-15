"""Minimal FastAPI application for rockit-serve."""

from fastapi import FastAPI

from rockit_serve.routers.agents import router as agents_router

app = FastAPI(title="Rockit Signals API", version="0.1.0")

app.include_router(agents_router)


@app.get("/health")
def health():
    return {"status": "ok"}
