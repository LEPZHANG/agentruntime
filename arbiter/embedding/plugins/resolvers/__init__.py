"""Plugin resolvers — loader-path manifest-to-entry conversion.

The resolvers walk a :class:`~arbiter.plugins.models.LoadedPlugin`'s
declared/auto-discovered directories and produce
:class:`~arbiter.plugins.models.PluginSkillEntry` /
:class:`~arbiter.plugins.models.PluginAgentDefinition` lists ready for
registration. They live outside the runtime hot path: the only callers
are ``cli/subcommands.py`` (``/plugins`` commands and agent boot
``_load_and_register_plugins``) plus the resolver test suites.

Validators (``validate_no_external_collisions``) deliberately stay in
``arbiter.plugins.skills`` / ``arbiter.plugins.agents`` because
``SkillManager.register_plugin_skills`` and
``AgentManager.register_plugin_agents`` invoke them on every plugin
registration, which sits on the agent-init runtime path.
"""

from .agents import resolve_plugin_agents
from .skills import resolve_plugin_entries

__all__ = [
    "resolve_plugin_agents",
    "resolve_plugin_entries",
]
