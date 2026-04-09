from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from .common import (
    ControlPlaneError,
    claude_root,
    install_rendered_file,
    load_json_file,
    main_guard,
    render_json,
    show_diff,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render the canonical global Claude settings file into ~/.claude/settings.json."
    )
    parser.add_argument("--apply", dest="apply", action="store_true", help="Apply changes")
    parser.add_argument(
        "--dry-run",
        dest="apply",
        action="store_false",
        help="Show diffs only (default)",
    )
    parser.set_defaults(apply=False)
    parser.add_argument(
        "--global-settings",
        default=str(Path.home() / ".claude" / "settings.json"),
        help="Override ~/.claude/settings.json target",
    )
    parser.add_argument(
        "--canonical-settings",
        default=str(claude_root() / "config" / "settings.json"),
        help="Override canonical settings source",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    global_settings = Path(args.global_settings).expanduser().resolve()
    canonical_settings = Path(args.canonical_settings).expanduser().resolve()

    if not Path(args.global_settings).is_absolute():
        raise ControlPlaneError("--global-settings must be an absolute path")
    if not Path(args.canonical_settings).is_absolute():
        raise ControlPlaneError("--canonical-settings must be an absolute path")
    if not canonical_settings.is_file():
        raise ControlPlaneError(f"Missing canonical settings file: {canonical_settings}")

    data = load_json_file(canonical_settings, label="canonical settings file")
    if not isinstance(data, dict):
        raise ControlPlaneError(f"settings root must be an object: {canonical_settings}")

    with tempfile.TemporaryDirectory() as temp_dir:
        rendered_settings = Path(temp_dir) / "settings.json"
        rendered_settings.write_text(render_json(data), encoding="utf-8")

        print("=== Global Claude Settings ===")
        show_diff(global_settings, rendered_settings)

        if args.apply:
            install_rendered_file(rendered_settings, global_settings, log=print)

    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(main))
