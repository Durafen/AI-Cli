"""GLM API provider (Zhipu AI / Z.ai) - HTTP-based."""

import json
import os
import urllib.error
import urllib.request

from .base import BaseProvider
from ..exceptions import ProviderError


class GLMProvider(BaseProvider):
    """Provider for Zhipu AI GLM API."""

    name = "glm"
    API_URL = "https://open.bigmodel.cn/api/coding/paas/v4/chat/completions"

    # Known models supported by GLM API
    KNOWN_MODELS = [
        "glm-5",
        "glm-4.7",
        "glm-4.6",
        "glm-4.5",
        "glm-4.5-air",
        "glm-4.5-x",
        "glm-4.5-airx",
        "glm-4.5-flash",
        "glm-4-32b-0414-128k",
    ]

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key

    @property
    def api_key(self) -> str | None:
        """Get API key from init param or environment."""
        return self._api_key or os.getenv("ZHIPU_API_KEY") or os.getenv("GLM_API_KEY")

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
        """Call GLM API."""
        if not self.is_available():
            raise ProviderError(
                self.name,
                "ZHIPU_API_KEY or GLM_API_KEY not set"
            )

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
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
                    raise ProviderError(
                        self.name,
                        data["error"].get("message", str(data["error"]))
                    )

                choices = data.get("choices")
                if not choices or not isinstance(choices, list):
                    raise ProviderError(self.name, "Invalid response: missing 'choices'")

                message = choices[0].get("message", {})
                content = message.get("content")
                if content is None:
                    raise ProviderError(self.name, "Invalid response: missing 'content'")

                return content
        except urllib.error.HTTPError as e:
            try:
                error_body = e.read().decode() if hasattr(e, 'read') else str(e)
            except Exception:
                error_body = str(e)
            raise ProviderError(self.name, f"HTTP {e.code}: {error_body}")
        except urllib.error.URLError as e:
            raise ProviderError(self.name, f"Connection error: {e.reason}")
