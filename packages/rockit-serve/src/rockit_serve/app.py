"""Minimal FastAPI application for rockit-serve."""

from fastapi import FastAPI

app = FastAPI(title="Rockit Signals API", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}
