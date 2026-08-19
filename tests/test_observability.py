"""Optional observability configuration contracts."""
from agent_core.config import langfuse_is_configured


def test_langfuse_requires_both_credentials():
    assert not langfuse_is_configured({})
    assert not langfuse_is_configured({"LANGFUSE_PUBLIC_KEY": "pk"})
    assert langfuse_is_configured({
        "LANGFUSE_PUBLIC_KEY": "pk",
        "LANGFUSE_SECRET_KEY": "sk",
    })


def test_langfuse_can_be_explicitly_disabled_with_credentials():
    assert not langfuse_is_configured({
        "LANGFUSE_TRACING_ENABLED": "false",
        "LANGFUSE_PUBLIC_KEY": "pk",
        "LANGFUSE_SECRET_KEY": "sk",
    })
