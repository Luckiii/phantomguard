from __future__ import annotations

from typing import Protocol

import anthropic


class CodeGenerator(Protocol):
    def generate(self, prompt: str) -> str: ...


class AnthropicCodeGenerator:
    def __init__(self, client: object | None = None, model: str = "claude-fable-5") -> None:
        self._client = client or anthropic.Anthropic()
        self.model = model

    def generate(self, prompt: str) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
