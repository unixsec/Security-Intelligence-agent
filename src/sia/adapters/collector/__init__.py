"""Intelligence collector adapters.

Discovery (import any concrete adapter module to register it)::

    from sia.adapters.collector import (  # noqa: F401 — side-effect registration
        rss, rest_api, taxii, misp, otx, github_advisory, virustotal,
        cert_eu, jpcert, cncert, exploit_db, shodan, hackernews, bleeping,
    )
    from sia.adapters.collector.base import collector_registry
"""

from sia.adapters.collector.base import (
    CollectorAdapter,
    RawIntelItem,
    collector_registry,
)

# Eagerly import built-in adapters so operators can just `collector_registry.kinds()`
from sia.adapters.collector import (  # noqa: F401, E402
    bleeping,
    cert_eu,
    cncert,
    exploit_db,
    github_advisory,
    hackernews,
    jpcert,
    misp,
    otx,
    rest_api,
    rss,
    shodan,
    taxii,
    virustotal,
)

__all__ = ["CollectorAdapter", "RawIntelItem", "collector_registry"]
