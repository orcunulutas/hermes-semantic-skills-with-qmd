import argparse
import sys
import logging
import subprocess
import os
from pathlib import Path

from .hermes_adapter import iter_resolved_skills
from .corpus import build_corpus

logger = logging.getLogger(__name__)

def get_base_dir() -> Path:
    home = Path.home()
    base = home / ".hermes" / "semantic-skills"
    base.mkdir(parents=True, exist_ok=True)
    return base

def check_qmd_executable() -> bool:
    try:
        subprocess.run(["qmd", "--version"], capture_output=True, check=True, timeout=10)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def command_doctor(args):
    """Check system readiness."""
    print("Doctor Check:")
    has_qmd = check_qmd_executable()
    print(f"  QMD Executable: {'OK' if has_qmd else 'MISSING'}")

    base_dir = get_base_dir()
    manifest_path = base_dir / "current" / "manifest.json"
    if manifest_path.exists():
        print("  Manifest: PRESENT")
    else:
        print("  Manifest: MISSING (Run build)")

def command_build(args):
    """Build the corpus and update QMD."""
    if not check_qmd_executable():
        print("Error: qmd executable not found in PATH.")
        sys.exit(1)

    print("Resolving skills...")
    skills = iter_resolved_skills()
    print(f"Found {len(skills)} eligible skills.")

    base_dir = get_base_dir()
    print(f"Building corpus in {base_dir}...")
    build_corpus(skills, str(base_dir))

    # Target `current/corpus` since the single generation pointer is there
    corpus_dir = base_dir / "current" / "corpus"

    try:
        subprocess.run(
            [
                "qmd", "--index", "hermes-skills",
                "collection", "add", str(corpus_dir.resolve()),
                "--name", "hermes-skills"
            ],
            capture_output=True,
            check=False,
            timeout=30
        )
    except Exception as e:
        logger.warning(f"Error adding collection: {e}")

    print("Updating QMD index...")
    subprocess.run(
        ["qmd", "--index", "hermes-skills", "update"],
        check=True,
        timeout=1800
    )
    print("Generating embeddings...")
    subprocess.run(
        ["qmd", "--index", "hermes-skills", "embed"],
        check=True,
        timeout=3600
    )

    print("Build complete.")

def command_status(args):
    """Show index status."""
    if not check_qmd_executable():
        print("Error: qmd not found.")
        sys.exit(1)

    subprocess.run(
        ["qmd", "--index", "hermes-skills", "collection", "list"],
        check=False,
        timeout=30
    )

def command_remove(args):
    """Remove the index and corpus."""
    base_dir = get_base_dir()

    if check_qmd_executable():
        subprocess.run(
            ["qmd", "--index", "hermes-skills", "collection", "rm", "hermes-skills"],
            capture_output=True, check=False, timeout=30
        )

    import shutil
    if base_dir.exists():
        shutil.rmtree(base_dir)
    print("Removed semantic skills index and corpus.")

def main():
    parser = argparse.ArgumentParser(prog="hermes-semantic-skills")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="Check system readiness")
    subparsers.add_parser("build", help="Build corpus and update index")
    subparsers.add_parser("refresh", help="Alias for build")
    subparsers.add_parser("status", help="Show index status")
    subparsers.add_parser("remove", help="Remove index and corpus")

    args = parser.parse_args()

    if hasattr(args, 'command') and args.command:
        if args.command == "doctor":
            command_doctor(args)
        elif args.command in ("build", "refresh"):
            command_build(args)
        elif args.command == "status":
            command_status(args)
        elif args.command == "remove":
            command_remove(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
