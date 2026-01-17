"""OpenRouter API provider (HTTP-based)."""

import json
import os
import re
import urllib.error
import urllib.request

from .base import BaseProvider
from ..exceptions import ProviderError


class OpenRouterProvider(BaseProvider):
    """Provider for OpenRouter API (free models)."""

    name = "openrouter"
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    MODELS_URL = "https://openrouter.ai/api/v1/models"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key

    @property
    def api_key(self) -> str | None:
        """Get API key from init param or environment."""
        return self._api_key or os.getenv("OPENROUTER_API_KEY")

    def is_available(self) -> bool:
        """Check if API key is set."""
        return self.api_key is not None

    def call(
        self,
        model: str,
        prompt: str,
        json_output: bool = False,
        yolo: bool = False,  # Ignored for API
    ) -> str:
        """Call OpenRouter API."""
        if not self.is_available():
            raise ProviderError(self.name, "OPENROUTER_API_KEY not set")

        # Enforce free model
        if not model.endswith(":free"):
            raise ProviderError(
                self.name,
                f"OpenRouter model must end with ':free'. Got: {model}"
            )

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if json_output:
            payload["response_format"] = {"type": "json_object"}

        req = urllib.request.Request(
            self.API_URL,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                data = json.loads(resp.read().decode())

                # Validate response structure
                if "error" in data:
                    raise ProviderError(self.name, data["error"].get("message", str(data["error"])))

                choices = data.get("choices")
                if not choices or not isinstance(choices, list):
                    raise ProviderError(self.name, "Invalid response: missing 'choices'")

                message = choices[0].get("message", {})
                content = message.get("content")
                if content is None:
                    raise ProviderError(self.name, "Invalid response: missing 'content'")

                return content
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            raise ProviderError(self.name, f"HTTP {e.code}: {error_body}")
        except urllib.error.URLError as e:
            raise ProviderError(self.name, f"Connection error: {e.reason}")

    @classmethod
    def get_free_models(cls, api_key: str | None = None) -> list[str]:
        """Fetch free models from OpenRouter API."""
        key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not key:
            return []

        try:
            req = urllib.request.Request(
                cls.MODELS_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                return [m["id"] for m in data.get("data", []) if m["id"].endswith(":free")]
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, KeyError, TypeError):
            # Expected failures: network issues, bad response format
            return []
        except Exception as e:
            # Unexpected error - log it but don't crash
            import sys
            print(f"Warning: Failed to fetch OpenRouter models: {e}", file=sys.stderr)
            return []

    @classmethod
    def shorten_name(cls, full_name: str) -> str:
        """Shorten an OpenRouter model name by removing common suffixes and versions."""
        name = full_name
        # Remove common suffixes
        for suffix in ["-instruct", "-it", "-pro", "-air", "-exp", "-mini",
                       "-small", "-nano", "-flash", "-plus", "-chat", "-base",
                       "-preview", "-edition", "-venice-edition"]:
            name = name.replace(suffix, "")
        # Remove version patterns
        name = re.sub(r'-v\d+', '', name)  # -v2, -v3
        name = re.sub(r'-\d+(\.\d+)?b?$', '', name)  # -24b, -3.1, -70b
        name = re.sub(r'-\d+\.\d+-', '-', name)  # -3.1- in middle
        name = re.sub(r'-\d+b-', '-', name)  # -24b- in middle
        return name.strip('-') or full_name

    @classmethod
    def generate_aliases(cls, models: list[str], existing: dict) -> dict:
        """Generate short aliases for OpenRouter models, handling conflicts."""
        from ..constants import RESERVED_COMMANDS

        aliases = {}
        if not models:
            return aliases

        # First pass: collect candidates
        candidates = {}  # short_name -> [models]
        full_names = {}  # model -> full_name

        for model in models:
            if "/" not in model:
                continue
            full_name = model.split("/")[1].replace(":free", "")
            full_names[model] = full_name
            short_name = cls.shorten_name(full_name)
            candidates.setdefault(short_name, []).append(model)

        # Second pass: assign aliases
        for short_name, model_list in candidates.items():
            if len(model_list) == 1:
                model = model_list[0]
                full_name = full_names[model]
                if short_name not in existing and short_name not in RESERVED_COMMANDS:
                    aliases[short_name] = ("openrouter", model)
                elif full_name not in existing and full_name not in RESERVED_COMMANDS:
                    aliases[full_name] = ("openrouter", model)
            else:
                # Conflict - use full names
                for model in model_list:
                    full_name = full_names[model]
                    if full_name not in existing and full_name not in RESERVED_COMMANDS:
                        aliases[full_name] = ("openrouter", model)

        return aliases
