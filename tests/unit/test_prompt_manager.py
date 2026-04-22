"""Tests for the prompt manager."""

import pytest

from sia.gateway.llm.prompt_manager import PromptManager, PromptTemplate


class TestPromptTemplate:
    def test_defaults(self):
        t = PromptTemplate(name="test")
        assert t.version == "1.0"
        assert t.temperature == 0.3
        assert t.max_tokens == 2000


class TestPromptManager:
    @pytest.fixture
    def prompts_dir(self, tmp_path):
        p = tmp_path / "prompts"
        p.mkdir()

        (p / "test_prompt.yaml").write_text("""
name: test_prompt
version: "1.0"
description: "A test prompt"
temperature: 0.5
max_tokens: 1000
system: "You are a {{ role }} assistant."
user_template: "Analyze this: {{ content }}"
""")

        (p / "no_system.yaml").write_text("""
name: no_system
user_template: "Just this: {{ text }}"
""")

        return str(p)

    def test_load_all(self, prompts_dir):
        pm = PromptManager(prompts_dir)
        assert "test_prompt" in pm.template_names
        assert "no_system" in pm.template_names

    def test_get_template(self, prompts_dir):
        pm = PromptManager(prompts_dir)
        t = pm.get("test_prompt")
        assert t.name == "test_prompt"
        assert t.temperature == 0.5
        assert t.max_tokens == 1000

    def test_get_missing_raises(self, prompts_dir):
        pm = PromptManager(prompts_dir)
        with pytest.raises(KeyError, match="not found"):
            pm.get("nonexistent")

    def test_render_with_system(self, prompts_dir):
        pm = PromptManager(prompts_dir)
        messages = pm.render("test_prompt", role="security", content="CVE-2025-0001")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "security" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert "CVE-2025-0001" in messages[1]["content"]

    def test_render_without_system(self, prompts_dir):
        pm = PromptManager(prompts_dir)
        messages = pm.render("no_system", text="hello")
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "hello" in messages[0]["content"]

    def test_reload_detects_changes(self, prompts_dir):
        pm = PromptManager(prompts_dir)
        t = pm.get("test_prompt")
        assert t.temperature == 0.5

        # Modify the file
        import pathlib
        f = pathlib.Path(prompts_dir) / "test_prompt.yaml"
        f.write_text("""
name: test_prompt
version: "1.1"
temperature: 0.9
user_template: "Updated: {{ content }}"
""")
        pm.reload()
        t = pm.get("test_prompt")
        assert t.temperature == 0.9
        assert t.version == "1.1"

    def test_empty_dir(self, tmp_path):
        pm = PromptManager(str(tmp_path / "nonexistent"))
        assert pm.template_names == []
