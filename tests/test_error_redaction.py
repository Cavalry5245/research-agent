import pytest


@pytest.mark.parametrize(
    ("message", "endpoint"),
    [
        (
            "provider=https%3A%2F%2Fencoded.synthetic.invalid%2Fv1 request failed",
            "encoded.synthetic.invalid",
        ),
        ("provider=api.synthetic.invalid/v1 request failed", "api.synthetic.invalid"),
        ("provider=localhost:8080/v1 request failed", "localhost:8080"),
        ("provider=192.0.2.10:9000/v1 request failed", "192.0.2.10:9000"),
    ],
)
def test_redact_error_removes_likely_api_endpoints(message, endpoint):
    from app.services.error_redaction import redact_error

    redacted = redact_error(message)

    assert endpoint not in redacted
    assert "[REDACTED_URL]" in redacted
    assert "provider=" in redacted
    assert "request failed" in redacted


def test_redact_error_preserves_non_host_context():
    from app.services.error_redaction import redact_error

    redacted = redact_error(
        "status=503 vector open failed for paper.json; retry remains possible"
    )

    assert redacted == (
        "status=503 vector open failed for paper.json; retry remains possible"
    )
