"""Deprecated alias — see :mod:`arbiter.host.models`.

``HarnessEvent`` is kept as an alias for the new :data:`HostEvent` to
unblock the existing ``from arbiter.harness.models import HarnessEvent``
import path until 0.5.0.
"""

from arbiter.host.models import *  # noqa: F401,F403
from arbiter.host.models import HostEvent as _HostEvent, __all__ as _host_all

HarnessEvent = _HostEvent

__all__ = list(_host_all) + ["HarnessEvent"]
