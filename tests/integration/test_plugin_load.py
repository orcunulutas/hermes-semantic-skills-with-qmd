import sys
import os
import tempfile
import pytest
import subprocess
from pathlib import Path

hermes_path = "/tmp/hermes-agent"
if os.path.exists(hermes_path):
    sys.path.append(hermes_path)

@pytest.mark.skipif(not os.path.exists("/tmp/hermes-agent"), reason="hermes-agent not available")
def test_native_plugin_load(monkeypatch):
    """
    Test that the plugin can be loaded natively by Hermes PluginManager
    and successfully registers its tool.
    """
    try:
        from hermes_cli.plugins import get_plugin_manager
        import hermes_cli.config
        import tools.registry
    except ImportError as e:
        pytest.skip(f"Could not import hermes-agent plugins module: {e}")

    with tempfile.TemporaryDirectory() as tmp:
        hermes_home = Path(tmp)

        plugins_dir = hermes_home / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(hermes_cli.config, "get_hermes_home", lambda: hermes_home)

        plugin_repo_dir = plugins_dir / "orcunulutas" / "hermes-semantic-skills-with-qmd"
        plugin_repo_dir.parent.mkdir(parents=True, exist_ok=True)

        current_dir = Path(__file__).resolve().parent.parent.parent
        os.symlink(current_dir, plugin_repo_dir, target_is_directory=True)

        config_path = hermes_home / "config.yaml"
        with open(config_path, "w") as f:
            f.write("plugins:\n  enabled:\n    - orcunulutas/hermes-semantic-skills-with-qmd\n")

        monkeypatch.setenv("HERMES_HOME", str(hermes_home))
        monkeypatch.syspath_prepend(str(current_dir))

        manager = get_plugin_manager()
        manager.discover_and_load()

        # Verify it was discovered and enabled
        assert "orcunulutas/hermes-semantic-skills-with-qmd" in manager._plugins

        plugin = manager._plugins.get("orcunulutas/hermes-semantic-skills-with-qmd")
        assert plugin.enabled is True
        assert plugin.error is None

        # Verify the tool was registered into the Hermes tool registry
        # The registry is at tools.registry.registry
        all_tools_names = tools.registry.registry.get_all_tool_names()
        assert "skill_search" in all_tools_names

def test_plugin_doctor_cli(monkeypatch):
    if not os.path.exists("/tmp/hermes-agent"):
        pytest.skip("hermes-agent not available")

    with tempfile.TemporaryDirectory() as tmp:
        hermes_home = Path(tmp)
        monkeypatch.setenv("HERMES_HOME", str(hermes_home))

        plugins_dir = hermes_home / "plugins"
        plugin_repo_dir = plugins_dir / "orcunulutas" / "hermes-semantic-skills-with-qmd"
        plugin_repo_dir.parent.mkdir(parents=True, exist_ok=True)
        current_dir = Path(__file__).resolve().parent.parent.parent
        os.symlink(current_dir, plugin_repo_dir, target_is_directory=True)

        monkeypatch.setenv("PYTHONPATH", str(current_dir))

        cli_script = "/tmp/hermes-agent/hermes_cli/main.py"
        if os.path.exists(cli_script):
            try:
                import rich
            except ImportError:
                pytest.skip("CLI dependencies not available in this test environment.")
            res = subprocess.run([sys.executable, cli_script, "plugins", "doctor", str(plugin_repo_dir), "--ci"], capture_output=True, text=True, cwd="/tmp/hermes-agent")
            assert "No module named" not in res.stderr
            assert res.returncode == 0
            assert "1 tool(s)" in res.stdout
