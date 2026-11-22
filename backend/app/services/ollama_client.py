"""One place for talking to Ollama: configurable timeout, bounded retries."""

import logging
import time

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


def _is_transient(error: Exception) -> bool:
    if isinstance(error, (requests.ConnectionError, requests.Timeout)):
        return True

    if isinstance(error, requests.HTTPError):
        status = getattr(error.response, "status_code", 0) or 0
        return status >= 500

    return False


def post_json(url: str, payload: dict) -> dict:
    """POST to Ollama and return the JSON body.

    Connection errors, timeouts and 5xx responses are retried up to
    ``settings.ollama_retries`` times with a short backoff. Client errors
    (4xx) fail immediately: repeating them cannot help.
    """

    attempts = 1 + max(0, settings.ollama_retries)

    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=settings.ollama_timeout_seconds,
            )
            response.raise_for_status()
            return response.json()

        except requests.RequestException as error:
            if attempt == attempts or not _is_transient(error):
                raise

            delay = settings.ollama_retry_backoff_seconds * attempt
            logger.warning(
                "Ollama call failed (%s); retrying in %.1fs (%d/%d)",
                error.__class__.__name__,
                delay,
                attempt,
                attempts - 1,
            )
            time.sleep(delay)
