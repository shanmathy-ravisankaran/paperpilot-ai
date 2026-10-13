from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import Settings

logger = logging.getLogger(__name__)


class LlmError(RuntimeError):
    """A safe, provider-neutral inference failure."""
class LlmTimeoutError(LlmError): pass
class LlmUnavailableError(LlmError): pass


@dataclass(frozen=True)
class LlmClient:
    settings: Settings

    def complete(self, prompt: str, json_schema: dict[str, Any] | None = None) -> str:
        if self.settings.llm_provider == "ollama":
            return self._ollama(prompt, json_schema)
        if self.settings.llm_provider == "openai":
            return self._openai(prompt)
        raise LlmError("LLM_PROVIDER must be 'ollama' or 'openai'.")

    def _post(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urlopen(request, timeout=self.settings.llm_timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except TimeoutError as exc:
            raise LlmTimeoutError("The local model timed out. Try fewer papers or retry after Ollama is idle.") from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise LlmTimeoutError("The local model timed out. Try fewer papers or retry after Ollama is idle.") from exc
            raise LlmUnavailableError("Ollama is unavailable. Start Ollama and confirm the configured model is installed.") from exc
        except HTTPError as exc:
            raise LlmUnavailableError("The configured language model rejected the request. Confirm the model is installed and available.") from exc
        except json.JSONDecodeError as exc:
            raise LlmError("The configured language model returned an invalid transport response.") from exc

    def _ollama(self, prompt: str, json_schema: dict[str, Any] | None = None) -> str:
        payload = {"model": self.settings.ollama_model, "prompt": prompt, "stream": False,
                   "format": json_schema or "json", "options": {"temperature": 0}}
        data = self._post(f"{self.settings.ollama_base_url.rstrip('/')}/api/generate", payload, {"Content-Type": "application/json"})
        if not isinstance(data.get("response"), str):
            raise LlmError("The local model returned no text.")
        return data["response"]

    def _openai(self, prompt: str) -> str:
        if not self.settings.openai_api_key:
            raise LlmError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")
        data = self._post("https://api.openai.com/v1/responses", {"model": self.settings.openai_model, "input": prompt, "temperature": 0}, {"Content-Type": "application/json", "Authorization": f"Bearer {self.settings.openai_api_key}"})
        text = data.get("output_text")
        if not isinstance(text, str):
            raise LlmError("The configured model returned no text.")
        return text
