"""Deprecated alias — see :mod:`arbiter.host.schema`.

The ``export_harness_*`` functions are kept as aliases for the new
``export_host_*`` exporters until 0.5.0.
"""

from arbiter.host.schema import *  # noqa: F401,F403
from arbiter.host.schema import (
    __all__ as _host_all,
    export_host_acp_json_schema as _export_host_acp_json_schema,
    export_host_event_json_schema as _export_host_event_json_schema,
)

export_harness_event_json_schema = _export_host_event_json_schema
export_harness_acp_json_schema = _export_host_acp_json_schema

__all__ = list(_host_all) + [
    "export_harness_event_json_schema",
    "export_harness_acp_json_schema",
]
