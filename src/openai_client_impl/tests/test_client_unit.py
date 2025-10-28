from __future__ import annotations
import types
import pytest

from openai_client_impl.client import OpenAIClientImpl
from openai_client_impl.errors import MissingOpenAIKeyError

class _FakeResp:
    def __init__(self, payload): self._p = payload
    def model_dump(self): return self._p

class _FakeChat:
    def create(self, model, messages): return _FakeResp({"ok": True, "model": model, "messages": messages})

class _FakeEmb:
    def create(self, model, input): return _FakeResp({"embedding": [0.1], "model": model, "input": input})

class _FakeSDK:
    def __init__(self, api_key):
        self.api_key = api_key
        self.chat = types.SimpleNamespace(completions=_FakeChat())
        self.embeddings = _FakeEmb()

def test_missing_key(monkeypatch):
    impl = OpenAIClientImpl()
    import openai_client_impl.client as mod
    monkeypatch.setattr(mod, "get_openai_key", lambda subject: None)
    with pytest.raises(MissingOpenAIKeyError):
        impl.chat(subject="u", messages=[{"role":"user","content":"hi"}])

def test_chat_and_embed(monkeypatch):
    impl = OpenAIClientImpl()
    import openai_client_impl.client as mod
    monkeypatch.setattr(mod, "get_openai_key", lambda subject: "sk-test")
    monkeypatch.setattr(mod, "OpenAI", lambda api_key: _FakeSDK(api_key))

    out1 = impl.chat(subject="u", messages=[{"role":"user","content":"hey"}], model="m1")
    assert out1["ok"] is True and out1["model"] == "m1"

    out2 = impl.embed(subject="u", inputs=["hello"], model="e1")
    assert "embedding" in out2 and out2["model"] == "e1"
