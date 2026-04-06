from worker import webhooks


def test_send_webhook_posts_for_public_url(monkeypatch):
    posted = {}

    def fake_post(url, json, timeout):
        posted["url"] = url
        posted["json"] = json
        posted["timeout"] = timeout

    monkeypatch.setattr(webhooks.requests, "post", fake_post)
    monkeypatch.setattr(webhooks, "validate_public_http_url", lambda url, _field_name: url)

    webhooks.send_webhook("https://example.com/callback", {"status": "ok"}, "job_123")

    assert posted["url"] == "https://example.com/callback"
    assert posted["json"]["status"] == "ok"


def test_send_webhook_swallows_invalid_url(monkeypatch):
    monkeypatch.setattr(
        webhooks,
        "validate_public_http_url",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("blocked")),
    )
    webhooks.send_webhook("http://127.0.0.1/callback", {"status": "ok"}, "job_123")
