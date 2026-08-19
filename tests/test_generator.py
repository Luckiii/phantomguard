from types import SimpleNamespace

from fuzzing.generator import AnthropicCodeGenerator


class FakeMessages:
    def __init__(self, text: str) -> None:
        self._text = text
        self.last_kwargs: dict | None = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self._text)])


class FakeAnthropicClient:
    def __init__(self, text: str) -> None:
        self.messages = FakeMessages(text)


def test_generate_returns_response_text():
    client = FakeAnthropicClient("import requests\n")
    generator = AnthropicCodeGenerator(client=client, model="claude-fable-5")

    result = generator.generate("write a script that fetches a URL")

    assert result == "import requests\n"


def test_generate_passes_prompt_and_model_to_client():
    client = FakeAnthropicClient("import os\n")
    generator = AnthropicCodeGenerator(client=client, model="claude-fable-5")

    generator.generate("write a script")

    assert client.messages.last_kwargs["model"] == "claude-fable-5"
    assert client.messages.last_kwargs["messages"] == [
        {"role": "user", "content": "write a script"}
    ]
