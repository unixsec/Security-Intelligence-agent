"""YAML-driven Prompt template manager with hot-reload (FN-3).

Why
---
Previously ``reload()`` only re-hashed files when explicitly invoked. Process-
level reload from the API was a no-op for the per-consumer instance, so a
prompt edit required a redeploy (or pod restart) to take effect.

Now
---
``PromptManager.__init__`` schedules a background asyncio task that polls the
``prompts/`` directory for ``mtime`` changes every ~2 seconds (cheap, portable,
no native fsnotify dependency). On change, the affected file is re-loaded
incrementally — same hash-based dedup as before, so unchanged files cost
nothing.

Design notes
~~~~~~~~~~~~
* Uses **mtime polling**, not ``watchdog`` ``Observer``. ``Observer`` runs a
  thread, which is fine, but binding it to the current event loop's lifecycle
  is fiddly and the inotify backend has bitten us before on K8s emptyDir
  mounts. A 2-second mtime scan over ~10 small YAMLs is < 1ms per tick.
* The watch task is started lazily on first ``async`` call site so plain unit
  tests that build a manager without an event loop still work.
* ``stop_watcher()`` is called from ``main.lifespan`` shutdown.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from jinja2.sandbox import SandboxedEnvironment

logger = logging.getLogger(__name__)

# Mtime poll interval. 2s is a good balance between freshness and noise; the
# scan is O(num_yaml_files) so it stays cheap.
_WATCH_INTERVAL_SEC = 2.0


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
    - Jinja2 template rendering (sandboxed)
    - File hash tracking for change detection
    - **Background mtime watcher for hot-reload** (FN-3)
    """

    def __init__(self, prompts_dir: str = "prompts", *, watch: bool = True):
        self.prompts_dir = Path(prompts_dir)
        self._prompts: dict[str, PromptTemplate] = {}
        self._hashes: dict[str, str] = {}
        self._mtimes: dict[str, float] = {}
        self._watch_enabled = watch
        self._watch_task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None
        self.load_all()
        if watch:
            self._maybe_start_watcher()

    # ─── Loading ──────────────────────────────────────────────────────────

    def load_all(self) -> None:
        """Load all YAML prompt files from the prompts directory."""
        if not self.prompts_dir.exists():
            logger.warning("Prompts directory not found: %s", self.prompts_dir)
            return

        for yaml_file in self.prompts_dir.glob("*.yaml"):
            self._load_one(yaml_file)

        logger.info("Loaded %d prompt templates from %s", len(self._prompts), self.prompts_dir)

    def _load_one(self, path: Path) -> None:
        """Load a single YAML prompt file (idempotent on unchanged content)."""
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
            try:
                self._mtimes[path.name] = path.stat().st_mtime
            except OSError:
                pass
            logger.info("Loaded prompt: %s (v%s)", template.name, template.version)

        except Exception:
            logger.exception("Failed to load prompt file: %s", path)

    # ─── Lookup / render ──────────────────────────────────────────────────

    def get(self, name: str) -> PromptTemplate:
        """Get a prompt template by name."""
        if name not in self._prompts:
            raise KeyError(f"Prompt template not found: '{name}'")
        return self._prompts[name]

    def render(self, name: str, **variables: object) -> list[dict[str, str]]:
        """Render a prompt template with variables into chat messages."""
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
        """Reload all prompt templates (manual hook)."""
        self.load_all()

    @property
    def template_names(self) -> list[str]:
        """List all loaded template names."""
        return list(self._prompts.keys())

    # ─── Hot-reload watcher (FN-3) ────────────────────────────────────────

    def _maybe_start_watcher(self) -> None:
        """Schedule the watch loop if there's a running event loop.

        Called from ``__init__``. If we are not yet inside a loop (e.g.
        synchronous test setup), the watcher will not start — callers can
        call ``start_watcher()`` later from an async context.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # No running loop — start later via start_watcher()
        self.start_watcher(loop)

    def start_watcher(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        if self._watch_task is not None and not self._watch_task.done():
            return
        loop = loop or asyncio.get_event_loop()
        self._stop_event = asyncio.Event()
        self._watch_task = loop.create_task(self._watch_loop(), name="prompt_watcher")
        logger.info("Prompt hot-reload watcher started for %s", self.prompts_dir)

    async def _watch_loop(self) -> None:
        try:
            while not (self._stop_event and self._stop_event.is_set()):
                await asyncio.sleep(_WATCH_INTERVAL_SEC)
                self._scan_changes()
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("Prompt watcher crashed; hot-reload disabled")

    def _scan_changes(self) -> None:
        """One pass: detect changed / new / removed prompt files."""
        if not self.prompts_dir.exists():
            return
        seen: set[str] = set()
        for path in self.prompts_dir.glob("*.yaml"):
            seen.add(path.name)
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if self._mtimes.get(path.name) == mtime:
                continue
            # Reload (hash check inside avoids spurious reloads on touch).
            self._load_one(path)

        # File deletion → drop entries that no longer exist on disk.
        removed = [n for n in self._mtimes if n not in seen]
        for fname in removed:
            self._mtimes.pop(fname, None)
            self._hashes.pop(fname, None)
            for tname, tmpl in list(self._prompts.items()):
                # we don't remember which file produced which template, so
                # only drop entries by filename match heuristic
                if tmpl.name == Path(fname).stem:
                    self._prompts.pop(tname, None)
                    logger.info("Prompt removed: %s", tname)

    def stop_watcher(self) -> None:
        if self._stop_event:
            self._stop_event.set()
        if self._watch_task and not self._watch_task.done():
            self._watch_task.cancel()
        self._watch_task = None
        self._stop_event = None
