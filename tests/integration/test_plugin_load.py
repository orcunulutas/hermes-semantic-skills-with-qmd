import sys
import os
import pytest

hermes_path = "/tmp/hermes-agent"
if os.path.exists(hermes_path):
    sys.path.append(hermes_path)

@pytest.mark.skipif(not os.path.exists("/tmp/hermes-agent"), reason="hermes-agent not available")
def test_native_plugin_load():
    """
    Test that the plugin can be loaded natively by Hermes PluginContext.
    """
    import __init__ as root_init

    class DummyContext:
        def register_tool(self, **kwargs):
            self.kwargs = kwargs

    ctx = DummyContext()

    # Simulate Hermes discovering and calling register
    root_init.register(ctx)

    assert hasattr(ctx, "kwargs")
    assert ctx.kwargs["name"] == "skill_search"
    assert ctx.kwargs["toolset"] == "semantic_skills"
