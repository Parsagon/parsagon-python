#!/usr/bin/env python3

import importlib.metadata
import re
import tomllib
from pathlib import Path

gui_dir = Path(__file__).parent
repo_root = gui_dir.parent
src_dir = repo_root / "src"

default_env_script = """
import os

os.environ["GUI_ENABLED"] = "1"
os.environ["VERSION"] = "{{ VERSION }}"

# Add other environment variables here:
# os.environ["API_BASE"] = "https://parsagon.io"
"""

gui_env_path = src_dir / "gui_env.py"
if not gui_env_path.exists():
    with open(gui_env_path, "w") as f:
        f.write(default_env_script)

with open(gui_env_path, "r") as f:
    env_script = f.read()
assert "GUI_ENABLED" in env_script, "GUI_ENABLED not found in gui_env.py"
assert "VERSION" in env_script, "VERSION not found in gui_env.py"

with open(repo_root / "pyproject.toml", "rb") as f:
    package_data = tomllib.load(f)
version = package_data["project"]["version"]

# Replace
env_script = re.sub(r"^\s*os\.environ\[\"VERSION\"] ?= ?\"[^\n]*\"", f"os.environ[\"VERSION\"] = \"{version}\"", env_script, flags=re.MULTILINE)

with open(gui_env_path, "w") as f:
    f.write(env_script)

# Pass version to bash
print(version.replace(".", "-"))