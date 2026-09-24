"""Logging setup — stderr only (stdout reserved for MCP)."""

from __future__ import annotations

import logging
import re
import sys

_BEARER_TOKEN = re.compile(r"(?i)(bearer\s+)[^\s,;]+")
_URL_CREDENTIALS = re.compile(r"(?i)(https?://)[^\s/@:]+(?::[^\s/@]*)?@")
_TOKEN_ASSIGNMENT = re.compile(r"(?i)(polarion_token\s*[=:]\s*)[^\s,;]+")


def redact_sensitive_text(value: str) -> str:
    """Redact common bearer tokens, credential URLs, and token assignments."""
    value = _BEARER_TOKEN.sub(r"\1[REDACTED]", value)
    value = _URL_CREDENTIALS.sub(r"\1[REDACTED]@", value)
    return _TOKEN_ASSIGNMENT.sub(r"\1[REDACTED]", value)


class _SecretRedactingFilter(logging.Filter):
    """Redact before a package log record reaches stderr."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_sensitive_text(record.getMessage())
        record.args = ()
        return True


def setup_logging(*, level: int = logging.INFO) -> logging.Logger:
    """Package logger — single ``StreamHandler(sys.stderr)``, never MCP stdout."""
    logger = logging.getLogger("mcp_server_polarion")

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.addFilter(_SecretRedactingFilter())
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ),
        )
        logger.addHandler(handler)

    logger.setLevel(level)
    logger.propagate = False
    return logger
