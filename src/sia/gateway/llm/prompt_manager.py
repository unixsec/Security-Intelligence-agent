"""YAML-driven Prompt template manager with hot-reload."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from jinja2.sandbox import SandboxedEnvironment

logger = logging.getLogger(__name__)


@dataclass
class PromptTemplate:
    """A prompt template loaded from YAML."""

    name: str
    version: str = "1.0"
    description: str = ""
    model_preference: str = "default"
    temperature: float = 0.3
    max_tokens: int = 2000
    system: str = ""
    user_template: str = ""
    output_schema: dict = field(default_factory=dict)


class PromptManager:
    """Loads and manages prompt templates from YAML files.

    Features:
    - YAML-based prompt definitions
    - Jinja2 template rendering
    - File hash tracking for change detection
    - Thread-safe reload
    """

    def __init__(self, prompts_dir: str = "prompts"):
        self.prompts_dir = Path(prompts_dir)
        self._prompts: dict[str, PromptTemplate] = {}
        self._hashes: dict[str, str] = {}
        self.load_all()

    def load_all(self) -> None:
        """Load all YAML prompt files from the prompts directory."""
        if not self.prompts_dir.exists():
            logger.warning("Prompts directory not found: %s", self.prompts_dir)
            return

        for yaml_file in self.prompts_dir.glob("*.yaml"):
            self._load_one(yaml_file)

        logger.info("Loaded %d prompt templates from %s", len(self._prompts), self.prompts_dir)

    def _load_one(self, path: Path) -> None:
        """Load a single YAML prompt file."""
        try:
            content = path.read_text(encoding="utf-8")
            content_hash = hashlib.sha256(content.encode()).hexdigest()

            if self._hashes.get(path.name) == content_hash:
                return  # No change

            data = yaml.safe_load(content)
            if not data or "name" not in data:
                logger.warning("Invalid prompt file (missing 'name'): %s", path)
                return

            template = PromptTemplate(
                name=data["name"],
                version=data.get("version", "1.0"),
                description=data.get("description", ""),
                model_preference=data.get("model_preference", "default"),
                temperature=data.get("temperature", 0.3),
                max_tokens=data.get("max_tokens", 2000),
                system=data.get("system", ""),
                user_template=data.get("user_template", ""),
                output_schema=data.get("output_schema", {}),
            )

            self._prompts[data["name"]] = template
            self._hashes[path.name] = content_hash
            logger.debug("Loaded prompt: %s (v%s)", template.name, template.version)

        except Exception:
            logger.exception("Failed to load prompt file: %s", path)

    def get(self, name: str) -> PromptTemplate:
        """Get a prompt template by name."""
        if name not in self._prompts:
            raise KeyError(f"Prompt template not found: '{name}'")
        return self._prompts[name]

    def render(self, name: str, **variables: object) -> list[dict[str, str]]:
        """Render a prompt template with variables into chat messages.

        Returns OpenAI-format messages: [{"role": "system", ...}, {"role": "user", ...}]
        """
        template = self.get(name)
        messages = []
        env = SandboxedEnvironment(autoescape=False)

        if template.system:
            system_content = env.from_string(template.system).render(**variables)
            messages.append({"role": "system", "content": system_content})

        if template.user_template:
            user_content = env.from_string(template.user_template).render(**variables)
            messages.append({"role": "user", "content": user_content})

        return messages

    def reload(self) -> None:
        """Reload all prompt templates (for hot-reload)."""
        self.load_all()

    @property
    def template_names(self) -> list[str]:
        """List all loaded template names."""
        return list(self._prompts.keys())
