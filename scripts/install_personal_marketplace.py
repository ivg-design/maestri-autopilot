#!/usr/bin/env python3
"""Install Maestri Autopilot into the personal Codex plugin marketplace."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

PLUGIN_NAME = "maestri-autopilot"
MARKETPLACE_NAME = "personal"
EXCLUDED_DIRS = {".git", "__pycache__", ".pytest_cache", ".maestri", ".venv", "venv"}
EXCLUDED_FILES = {".DS_Store"}
PLUGIN_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "name": MARKETPLACE_NAME,
            "interface": {"displayName": "Personal"},
            "plugins": [],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    payload.setdefault("name", MARKETPLACE_NAME)
    payload.setdefault("interface", {"displayName": "Personal"})
    payload.setdefault("plugins", [])
    if not isinstance(payload["plugins"], list):
        raise ValueError(f"{path} field 'plugins' must be a list.")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def marketplace_entry() -> dict[str, Any]:
    return {
        "name": PLUGIN_NAME,
        "source": {
            "source": "local",
            "path": f"./plugins/{PLUGIN_NAME}",
        },
        "policy": {
            "installation": "AVAILABLE",
            "authentication": "ON_INSTALL",
        },
        "category": "Productivity",
    }


def update_marketplace(path: Path) -> None:
    payload = load_json(path)
    plugins = payload["plugins"]
    entry = marketplace_entry()
    for index, existing in enumerate(plugins):
        if isinstance(existing, dict) and existing.get("name") == PLUGIN_NAME:
            plugins[index] = entry
            break
    else:
        plugins.append(entry)
    write_json(path, payload)


def ignore(_: str, names: list[str]) -> set[str]:
    return {name for name in names if name in EXCLUDED_DIRS or name in EXCLUDED_FILES}


def assert_plugin_root(path: Path) -> None:
    manifest = path / ".codex-plugin" / "plugin.json"
    if not manifest.is_file():
        raise FileNotFoundError(f"missing plugin manifest: {manifest}")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if payload.get("name") != PLUGIN_NAME:
        raise ValueError(f"{manifest} is not the {PLUGIN_NAME} manifest.")
    version = payload.get("version")
    if not isinstance(version, str) or not PLUGIN_VERSION_RE.match(version):
        raise ValueError(
            f"{manifest} version must be plain semver without build metadata; "
            "Codex hook cache paths are resolved without '+' build suffixes."
        )


def copy_plugin(source: Path, target: Path, force: bool) -> None:
    assert_plugin_root(source)
    if target.exists():
        if not (target / ".codex-plugin" / "plugin.json").is_file() and not force:
            raise FileExistsError(f"{target} exists but does not look like a plugin. Re-run with --force to replace it.")
        shutil.rmtree(target)

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"{PLUGIN_NAME}-install-", dir=str(target.parent)) as tmp:
        staging = Path(tmp) / PLUGIN_NAME
        shutil.copytree(source, staging, ignore=ignore)
        assert_plugin_root(staging)
        staging.replace(target)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=repo_root_from_script(), help="Plugin source root.")
    parser.add_argument("--home", type=Path, default=Path.home(), help="Home directory for marketplace installation.")
    parser.add_argument("--force", action="store_true", help="Replace an existing non-plugin target directory.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned paths without modifying files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = args.source.expanduser().resolve()
    home = args.home.expanduser().resolve()
    target = home / "plugins" / PLUGIN_NAME
    marketplace = home / ".agents" / "plugins" / "marketplace.json"

    assert_plugin_root(source)

    if args.dry_run:
        print(f"source: {source}")
        print(f"target: {target}")
        print(f"marketplace: {marketplace}")
        print("no files changed")
        return 0

    copy_plugin(source, target, args.force)
    update_marketplace(marketplace)

    print(f"Installed {PLUGIN_NAME} plugin source: {target}")
    print(f"Updated Codex personal marketplace: {marketplace}")
    print("Restart Codex, open /plugins, select the Personal marketplace, and install Maestri Autopilot.")
    print("After installing, review and trust plugin hooks with /hooks before relying on autonomous continuation.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI installer should print one clear error.
        print(f"install_personal_marketplace.py: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
