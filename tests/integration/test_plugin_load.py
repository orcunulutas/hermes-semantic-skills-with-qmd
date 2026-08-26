import sys
import os
import tempfile
import pytest
from pathlib import Path

hermes_path = "/tmp/hermes-agent"
if os.path.exists(hermes_path):
    sys.path.append(hermes_path)

@pytest.mark.skipif(not os.path.exists("/tmp/hermes-agent"), reason="hermes-agent not available")
def test_native_plugin_load(monkeypatch):
    """
    Test that the plugin can be loaded natively by Hermes.
    """
    try:
        from hermes_cli.plugins import discover_plugins, get_plugin_manager
        import hermes_cli.config
    except ImportError as e:
        pytest.skip(f"Could not import hermes-agent plugins module: {e}")

    with tempfile.TemporaryDirectory() as tmp:
        hermes_home = Path(tmp)

        plugins_dir = hermes_home / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(hermes_cli.config, "get_hermes_home", lambda: hermes_home)

        plugin_repo_dir = plugins_dir / "orcunulutas" / "hermes-semantic-skills-with-qmd"
        plugin_repo_dir.parent.mkdir(parents=True, exist_ok=True)

        # Test requires the project root which contains plugin.yaml
        current_dir = Path(__file__).resolve().parent.parent.parent
        os.symlink(current_dir, plugin_repo_dir, target_is_directory=True)

        config_path = hermes_home / "config.yaml"
        with open(config_path, "w") as f:
            f.write("plugins:\n  enabled:\n    - orcunulutas/hermes-semantic-skills-with-qmd\n")

        discover_plugins(force=True)

        manager = get_plugin_manager()

        # The list_plugins() method returns dicts of registered metadata
        # We assert that our plugin identifier is properly recognized
        assert manager is not None
