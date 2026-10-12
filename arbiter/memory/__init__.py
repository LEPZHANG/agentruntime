"""Memory management subpackage for Arbiter.

Note: the :class:`MemoryStore` Protocol lives in
:mod:`arbiter.capabilities.memory` and is re-exported from
:mod:`arbiter.capabilities` only — pulling it through
``arbiter.memory`` here would force ``import arbiter.memory`` to load
the rest of ``arbiter.capabilities`` (which after Issue #17 includes
the MCP registry concretes that drag the MCP SDK). Keeping memory
import-light is asserted by ``tests/test_memory_decoupling.py``.
"""

from .manager import MemoryManager
from .retriever import MemoryRetriever
from .crystallizer import MemoryCrystallizer, SkillCrystallizer
from .storage import SQLiteMemoryStore
from .guards import MemoryGuard, SensitiveMemoryError
from .render import MemoryPromptRenderer
from .models import (
    CrystallizationProposal,
    MemoryRecord,
    MemoryReviewItem,
    SaveMemoryRequest,
    SessionSummaryRecord,
    RecallCandidate,
)

__all__ = [
    "MemoryManager",
    "MemoryRetriever",
    "MemoryCrystallizer",
    "SkillCrystallizer",
    "SQLiteMemoryStore",
    "MemoryGuard",
    "SensitiveMemoryError",
    "MemoryPromptRenderer",
    "MemoryRecord",
    "MemoryReviewItem",
    "CrystallizationProposal",
    "SaveMemoryRequest",
    "SessionSummaryRecord",
    "RecallCandidate",
]
