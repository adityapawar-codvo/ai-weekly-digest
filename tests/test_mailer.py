"""Verifies the mailer builds a Brevo-shaped payload and respects DRY_RUN, without
making a real network call."""

from core import config
from agents import mailer


class _FakeResponse:
    def __init__(self, status_code=201, body=None):
        self.status_code = status_code
        self._body = body or {"messageId": "fake-id"}
        self.text = str(self._body)

    def json(self):
        return self._body


def test_dry_run_overrides_recipients(monkeypatch):
    monkeypatch.setattr(config, "DRY_RUN", True)
    monkeypatch.setattr(config, "MAINTAINER_EMAIL", "maintainer@example.com")
    monkeypatch.setattr(config, "SENDER_EMAIL", "sender@example.com")
    monkeypatch.setattr(config, "SENDER_NAME", "Digest")
    monkeypatch.setattr(config, "BREVO_API_KEY", "fake-key")

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _FakeResponse()

    monkeypatch.setattr(mailer.requests, "post", fake_post)

    email = {"subject": "Subj", "html": "<p>hi</p>", "text": "hi"}
    mailer.send(email, ["someone-else@example.com", "another@example.com"], bcc=True)

    assert captured["url"] == mailer.BREVO_URL
    assert captured["headers"]["api-key"] == "fake-key"
    body = captured["json"]
    assert body["sender"] == {"name": "Digest", "email": "sender@example.com"}
    assert body["to"] == [{"email": "maintainer@example.com"}]
    assert "bcc" not in body  # DRY_RUN forces a single recipient, no bcc
    assert body["htmlContent"] == "<p>hi</p>"
    assert body["textContent"] == "hi"


def test_bcc_used_for_multi_recipient_send(monkeypatch):
    monkeypatch.setattr(config, "DRY_RUN", False)
    monkeypatch.setattr(config, "SENDER_EMAIL", "sender@example.com")
    monkeypatch.setattr(config, "SENDER_NAME", "Digest")
    monkeypatch.setattr(config, "BREVO_API_KEY", "fake-key")

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return _FakeResponse()

    monkeypatch.setattr(mailer.requests, "post", fake_post)

    email = {"subject": "Subj", "html": "<p>hi</p>", "text": "hi"}
    mailer.send(email, ["a@example.com", "b@example.com"], bcc=True)

    body = captured["json"]
    assert body["to"] == [{"email": "sender@example.com"}]
    assert body["bcc"] == [{"email": "a@example.com"}, {"email": "b@example.com"}]
