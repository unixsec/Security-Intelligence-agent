"""SIA Adapter Layer — unified extension points for external integrations.

This package hosts the **adapter pattern** for SIA's three major extension
surfaces:

    sia.adapters.collector  — pull intel from external feeds/APIs
    sia.adapters.push       — deliver reports/alerts to users
    sia.adapters.llm        — talk to LLM providers (local or cloud)

Each surface has:
  * A `BaseAdapter` / `Protocol` defining the minimum contract
  * A module-level `Registry` that maps a string `kind` → adapter class
  * Concrete adapter implementations in sub-packages

Registration flow::

    @collector_registry.register("rss")
    class RSSCollector(CollectorAdapter): ...

Discovery flow (at app boot)::

    import sia.adapters.collector.rss       # noqa — side-effect registration
    adapter = collector_registry.build("rss", config)

Benefits vs the old hard-coded FETCHER_REGISTRY / pusher/channels.py:
  * Pluggable: a new intel source or push channel is a new file; no core
    editing.
  * Testable: the registry accepts fakes; test modules don't need real
    network calls.
  * Uniform telemetry: BaseAdapter can hook metrics/logging in one place.
"""

from sia.adapters.base import AdapterConfig, AdapterError, BaseAdapter, Registry

__all__ = ["AdapterConfig", "AdapterError", "BaseAdapter", "Registry"]
