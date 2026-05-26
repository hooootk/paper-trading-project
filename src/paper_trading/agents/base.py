"""Base agent with shared LLM interaction layer."""

import json
import re
import time

from paper_trading.config import get_azure_client, settings


class BaseAgent:
    """Common LLM interaction layer for all agents."""

    def __init__(self, name: str, system_prompt: str, temperature: float = 0.1):
        self.name = name
        self.system_prompt = system_prompt
        self.temperature = temperature

    def call_llm(self, user_prompt: str, retries: int = 5) -> dict | None:
        """Call Azure OpenAI with system + user prompt, return parsed JSON."""
        client = get_azure_client()
        for attempt in range(retries):
            try:
                response = client.chat.completions.create(
                    model=settings.azure_openai_deployment,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=self.temperature,
                    response_format={"type": "json_object"},
                )
                return json.loads(response.choices[0].message.content)

            except json.JSONDecodeError:
                print(f"    [{self.name}] JSON parse error, attempt {attempt+1}/{retries}")
            except Exception as e:
                err_str = str(e)
                match = re.search(r"retry after (\d+)", err_str, re.IGNORECASE)
                wait = 2**attempt * 5
                if match:
                    wait = float(match.group(1)) + 3
                    print(f"    [{self.name}] Rate limited, waiting {wait:.0f}s ...")
                elif "429" in err_str:
                    wait = 60 * (attempt + 1)
                    print(f"    [{self.name}] 429, waiting {wait}s ...")
                else:
                    print(f"    [{self.name}] API error: {e}, retry in {wait}s ...")
                time.sleep(wait)
        return None
