"""Shared import bootstrap for plugin hook scripts."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def add_plugin_scripts_to_path() -> Path:
    plugin_root = Path(os.environ.get("PLUGIN_ROOT", Path(__file__).resolve().parents[1]))
    scripts_dir = plugin_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return plugin_root
