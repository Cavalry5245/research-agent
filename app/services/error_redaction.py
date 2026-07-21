from __future__ import annotations

import re
from collections.abc import Mapping

_REDACTED = "[REDACTED]"
_KEY_SEPARATOR_RE = re.compile(r"[^a-z0-9]+")
_SENSITIVE_KEY_SUFFIXES = (
    "authorization",
    "api_key",
    "access_token",
    "client_secret",
    "token",
    "key",
)
_KEY_SEPARATOR_PATTERN = r"[_. -]+"
_TEXT_KEY = (
    rf"(?P<key>(?:[A-Za-z][A-Za-z0-9_. -]*?{_KEY_SEPARATOR_PATTERN})?"
    rf"(?:authorization|api{_KEY_SEPARATOR_PATTERN}key|"
    rf"access{_KEY_SEPARATOR_PATTERN}token|"
    rf"client{_KEY_SEPARATOR_PATTERN}secret|token|key))"
)
_QUOTED_VALUE_RE = re.compile(
    rf"(?P<prefix>(?<![\w.-])(?P<key_quote>[\"']?){_TEXT_KEY}"
    rf"(?P=key_quote)\s*[:=]\s*(?P<value_quote>[\"']))"
    rf"(?P<value>.*?)(?P=value_quote)",
    re.IGNORECASE,
)
_AUTHORIZATION_VALUE_RE = re.compile(
    rf"(?P<prefix>(?<![\w.-])(?P<key_quote>[\"']?){_TEXT_KEY}"
    rf"(?P=key_quote)\s*[:=]\s*)(?![\"'\[])"
    rf"(?P<value>[^\s,;&}}\]]+(?:\s+[^\s,;&}}\]]+)?)",
    re.IGNORECASE,
)
_AUTHORIZATION_SCHEME_RE = re.compile(
    r"(?P<prefix>(?<![\w.-])authorization\s+[A-Za-z][A-Za-z0-9_-]*\s+)"
    r"(?P<value>[^\s,;&}\]]+)",
    re.IGNORECASE,
)
_UNQUOTED_VALUE_RE = re.compile(
    rf"(?P<prefix>(?<![\w.-])(?P<key_quote>[\"']?){_TEXT_KEY}"
    rf"(?P=key_quote)\s*[:=]\s*)(?![\"'\[])(?P<value>[^\s,;&}}\]]+)",
    re.IGNORECASE,
)
_SK_TOKEN_RE = re.compile(r"sk-[A-Za-z0-9_-]+", re.IGNORECASE)

_URL_TERMINATOR = r"[^\s,;'\"<>]+"
_ENCODED_HTTP_URL_RE = re.compile(
    rf"(?<![A-Za-z0-9])https?%3a%2f%2f{_URL_TERMINATOR}", re.IGNORECASE
)
_HTTP_URL_RE = re.compile(rf"https?://{_URL_TERMINATOR}", re.IGNORECASE)
_LOCALHOST_ENDPOINT_RE = re.compile(
    rf"(?<![\w.-])localhost:[0-9]{{1,5}}(?:/{_URL_TERMINATOR})?",
    re.IGNORECASE,
)
_IPV4_ENDPOINT_RE = re.compile(
    rf"(?<![\w.])(?:[0-9]{{1,3}}\.){{3}}[0-9]{{1,3}}:"
    rf"[0-9]{{1,5}}(?:/{_URL_TERMINATOR})?"
)
_DOMAIN_PATH_ENDPOINT_RE = re.compile(
    rf"(?<![@\w.-])(?:[A-Za-z0-9](?:[A-Za-z0-9-]{{0,61}}"
    rf"[A-Za-z0-9])?\.)+[A-Za-z]{{2,63}}(?::[0-9]{{1,5}})?/"
    rf"{_URL_TERMINATOR}",
    re.IGNORECASE,
)


def _normalize_sensitive_key(key: str) -> str:
    return _KEY_SEPARATOR_RE.sub("_", key.lower()).strip("_")


def _is_sensitive_key(key: str) -> bool:
    normalized = _normalize_sensitive_key(key)
    return any(
        normalized == suffix or normalized.endswith(f"_{suffix}")
        for suffix in _SENSITIVE_KEY_SUFFIXES
    )


def _sanitize_sensitive_data(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            key: (
                _REDACTED
                if isinstance(key, str) and _is_sensitive_key(key)
                else _sanitize_sensitive_data(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_sensitive_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_sensitive_data(item) for item in value)
    return value


def _error_text(message: object) -> str:
    sanitized = _sanitize_sensitive_data(message)
    if isinstance(message, BaseException):
        status = getattr(message, "status_code", None)
        status_text = "" if status is None else f" status={status}"
        return f"{type(message).__name__}{status_text}: {sanitized}"
    if isinstance(message, (Mapping, list, tuple)):
        return repr(sanitized)
    return str(sanitized)


def _redact_endpoints(message: str) -> str:
    redacted = _ENCODED_HTTP_URL_RE.sub("[REDACTED_URL]", message)
    redacted = _HTTP_URL_RE.sub("[REDACTED_URL]", redacted)
    redacted = _LOCALHOST_ENDPOINT_RE.sub("[REDACTED_URL]", redacted)
    redacted = _IPV4_ENDPOINT_RE.sub("[REDACTED_URL]", redacted)
    return _DOMAIN_PATH_ENDPOINT_RE.sub("[REDACTED_URL]", redacted)


def redact_error(message: object) -> str:
    """Return safe error text while retaining class, status, and ordinary context."""

    def redact_quoted(match: re.Match[str]) -> str:
        if not _is_sensitive_key(match.group("key")):
            return match.group(0)
        return f"{match.group('prefix')}{_REDACTED}{match.group('value_quote')}"

    def redact_authorization(match: re.Match[str]) -> str:
        if not _normalize_sensitive_key(match.group("key")).endswith("authorization"):
            return match.group(0)
        return f"{match.group('prefix')}{_REDACTED}"

    def redact_unquoted(match: re.Match[str]) -> str:
        if not _is_sensitive_key(match.group("key")):
            return match.group(0)
        return f"{match.group('prefix')}{_REDACTED}"

    redacted = _QUOTED_VALUE_RE.sub(redact_quoted, _error_text(message))
    redacted = _AUTHORIZATION_VALUE_RE.sub(redact_authorization, redacted)
    redacted = _AUTHORIZATION_SCHEME_RE.sub(rf"\g<prefix>{_REDACTED}", redacted)
    redacted = _UNQUOTED_VALUE_RE.sub(redact_unquoted, redacted)
    redacted = _SK_TOKEN_RE.sub(_REDACTED, redacted)
    return _redact_endpoints(redacted)
