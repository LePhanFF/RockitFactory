"""Smoke tests for rockit-serve package."""


def test_import():
    import rockit_serve

    assert rockit_serve.__version__ == "0.1.0"


def test_health_endpoint():
    from fastapi.testclient import TestClient

    from rockit_serve.app import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
