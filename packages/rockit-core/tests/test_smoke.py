"""Smoke tests for rockit-core package."""


def test_import():
    import rockit_core

    assert rockit_core.__version__ == "0.1.0"
