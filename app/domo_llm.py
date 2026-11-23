import json
import logging
from typing import Any, List, Optional
import httpx
from langchain_core.language_models.llms import LLM
from .config import settings

logger = logging.getLogger("manufacturing_cost_agent.domo_llm")


class DomoTextLLM(LLM):
    """
    Custom LangChain LLM wrapper for Domo AI Services Text Generation API.
    Sends prompt payloads via HTTPX to Domo's /api/ai/v1/text/generation endpoint
    using the secure backend-only X-DOMO-Developer-Token header.
    """

    temperature: float = 0.1
    max_tokens: int = 1500
    system: Optional[str] = None
    timeout: float = 12.0

    @property
    def _llm_type(self) -> str:
        return "domo-text-generation"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> str:
        """Executes a synchronous completion call to Domo Text Generation API."""
        if not settings.is_domo_configured:
            error_msg = (
                "Domo AI credentials are not configured in backend/.env. "
                "Please configure DOMO_SUBDOMAIN and DOMO_TOKEN."
            )
            logger.error("Domo AI invocation blocked: credentials unconfigured.")
            raise RuntimeError(error_msg)

        url = settings.domo_api_url
        headers = {
            "Content-Type": "application/json",
            "X-DOMO-Developer-Token": settings.domo_token,
        }

        payload: dict[str, Any] = {
            "input": prompt,
            "temperature": self.temperature,
            "maxTokens": self.max_tokens,
        }

        # If a specific model is designated, send it; otherwise allow Domo to use its default
        if settings.domo_model and settings.domo_model != "YOUR_ENABLED_DOMO_MODEL_ID":
            payload["model"] = settings.domo_model.strip()

        if self.system:
            payload["system"] = self.system

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload, headers=headers)

                if response.status_code in (401, 403):
                    error_msg = (
                        f"Domo AI authentication failed (HTTP {response.status_code}). "
                        "Please verify DOMO_TOKEN and model access permissions in Domo."
                    )
                    logger.error("Domo AI authentication failed (HTTP %s).", response.status_code)
                    raise RuntimeError(error_msg)

                response.raise_for_status()
                data = response.json()

                # Log model usage if provided by Domo API
                usage = data.get("modelProviderUsage") or data.get("usage")
                if usage:
                    logger.info("Domo AI token usage: %s", usage)

                output = data.get("output", "")
                if not output and "choices" in data and len(data["choices"]) > 0:
                    output = data["choices"][0].get("text", "") or data["choices"][0].get("message", {}).get("content", "")

                for stop_token in stop or []:
                    output = output.split(stop_token)[0]

                return output.strip()

        except httpx.TimeoutException as exc:
            logger.error("Domo AI request timed out after %s seconds.", self.timeout)
            raise TimeoutError(f"Domo AI request timed out after {self.timeout}s.") from exc
        except httpx.HTTPStatusError as exc:
            logger.error("Domo AI API HTTP error: %s (Body: %s)", exc.response.status_code, exc.response.text)
            raise RuntimeError(f"Domo AI API returned status {exc.response.status_code}.") from exc
        except Exception as exc:
            logger.error("Unexpected error contacting Domo AI API: %s: %s", type(exc).__name__, exc)
            raise
