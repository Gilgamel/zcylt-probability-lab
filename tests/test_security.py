"""Tests for fail-closed destructive-action authentication."""

from services import security


def test_delete_password_fails_closed_when_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(security, "_configured_delete_password", lambda: "")
    assert not security.delete_password_is_configured()
    assert not security.verify_delete_password("")
    assert not security.verify_delete_password("anything")


def test_delete_password_accepts_only_exact_match(monkeypatch) -> None:
    monkeypatch.setattr(
        security, "_configured_delete_password", lambda: "correct horse battery staple"
    )
    assert security.delete_password_is_configured()
    assert security.verify_delete_password("correct horse battery staple")
    assert not security.verify_delete_password("Correct horse battery staple")
    assert not security.verify_delete_password("correct horse battery staple ")
