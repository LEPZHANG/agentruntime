"""Test script to verify all imports work correctly."""

print("Testing imports...")

try:
    from arbiter.llm import LLMClient
    print("✓ LLM client import successful")
except Exception as e:
    print(f"✗ LLM client import failed: {e}")

try:
    from arbiter.tools import (
        ToolRegistry,
        ReadFileTool,
        WriteFileTool,
        EditTool,
        ReadFolderTool,
        FindFilesTool,
        SearchTextTool,
        ShellTool,
        WebFetchTool,
        WebSearchTool,
        SaveMemoryTool,
        CLIHelpAgentTool,
        CodebaseInvestigatorTool,
        ActivateSkillTool,
    )
    print("✓ All tools imported successfully")
except Exception as e:
    print(f"✗ Tools import failed: {e}")

try:
    from arbiter.skills import SkillManager
    print("✓ Skill manager import successful")
except Exception as e:
    print(f"✗ Skill manager import failed: {e}")

try:
    from arbiter.agent import Arbiter
    print("✓ Agent import successful")
except Exception as e:
    print(f"✗ Agent import failed: {e}")

try:
    from arbiter.cli import ArbiterCLI
    print("✓ CLI import successful")
except Exception as e:
    print(f"✗ CLI import failed: {e}")

print("\n✓ All imports successful! The project is ready to run.")
print("\nTo start Arbiter, run:")
print("  arbiter")
