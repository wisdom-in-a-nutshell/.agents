#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


AGENTS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENTS_ROOT))

from hooks.control_plane import load_hooks_registry, render_copilot_hooks, render_json  # noqa: E402


DEFAULT_SETTINGS_OVERLAY = AGENTS_ROOT / "config" / "copilot-settings.json"
DEFAULT_HOOKS_REGISTRY = AGENTS_ROOT / "hooks/registry.json"
DEFAULT_COPILOT_HOME = Path.home() / ".copilot"
DEFAULT_SETTINGS_FILE = DEFAULT_COPILOT_HOME / "settings.json"
DEFAULT_USER_CONFIG_FILE = DEFAULT_COPILOT_HOME / "config.json"
DEFAULT_HOOKS_FILE = DEFAULT_COPILOT_HOME / "hooks/agents-control-plane.json"
DEFAULT_LAUNCHER_TARGET = Path.home() / "bin" / "copilot"
DEFAULT_REAL_CLI_PATH = Path("/opt/homebrew/bin/copilot")
DEFAULT_GITHUB_ROOT = Path.home() / "GitHub"
DEFAULT_APP_SUPPORT_DIR = Path.home() / "Library/Application Support/com.github.githubapp"

CONFIG_HEADER = "// User settings belong in settings.json.\n// This file is managed automatically.\n"
MANAGEMENT_COMMANDS = {
    "completion",
    "help",
    "init",
    "login",
    "mcp",
    "plugin",
    "skill",
    "update",
    "version",
}


class CopilotSyncError(RuntimeError):
    pass


def expand_path(raw: str, home: Path) -> Path:
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw)


def output_path(path: Path) -> Path:
    path = path.expanduser()
    return path if path.is_absolute() else Path.cwd() / path


def strip_json_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.lstrip().startswith("//"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def read_json_object(path: Path, *, allow_comments: bool = False) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if allow_comments:
        text = strip_json_comments(text)
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CopilotSyncError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CopilotSyncError(f"JSON root must be an object: {path}")
    return data


def load_overlay(path: Path) -> dict[str, Any]:
    data = read_json_object(path)
    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        raise CopilotSyncError("config/copilot-settings.json settings must be an object")
    trust = data.get("trust", {})
    if not isinstance(trust, dict):
        raise CopilotSyncError("config/copilot-settings.json trust must be an object")
    launcher = data.get("launcher", {})
    if not isinstance(launcher, dict):
        raise CopilotSyncError("config/copilot-settings.json launcher must be an object")
    skills = data.get("skills", {})
    if not isinstance(skills, dict):
        raise CopilotSyncError("config/copilot-settings.json skills must be an object")
    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict):
        raise CopilotSyncError("config/copilot-settings.json hooks must be an object")
    return data


def merge_settings(existing: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    desired = dict(existing)
    for key, value in overlay.get("settings", {}).items():
        if isinstance(value, (str, bool, int, float)) or value is None:
            desired[key] = value
        else:
            raise CopilotSyncError(f"managed Copilot setting must be scalar: {key}")
    return desired


def normalized_path_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in raw:
        if not isinstance(value, str) or not value.strip():
            continue
        expanded = str(Path(value).expanduser().resolve())
        if expanded in seen:
            continue
        seen.add(expanded)
        result.append(expanded)
    return result


def merge_trusted_folders(*sources: Any) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for source in sources:
        for expanded in normalized_path_list(source):
            if expanded in seen:
                continue
            seen.add(expanded)
            merged.append(expanded)
    return merged


def discover_trusted_folders(overlay: dict[str, Any], github_root: Path, home: Path) -> list[str]:
    trust = overlay.get("trust", {})
    trusted: list[Path] = []

    if trust.get("githubRoot", False):
        trusted.append(github_root)
    if trust.get("directChildren", False) and github_root.is_dir():
        trusted.extend(path for path in sorted(github_root.iterdir()) if path.is_dir())

    extras = trust.get("extraFolders", [])
    if not isinstance(extras, list):
        raise CopilotSyncError("trust.extraFolders must be an array")
    for raw in extras:
        if not isinstance(raw, str) or not raw.strip():
            raise CopilotSyncError(f"invalid trust.extraFolders entry: {raw!r}")
        trusted.append(expand_path(raw.strip(), home))

    seen: set[str] = set()
    result: list[str] = []
    for path in trusted:
        resolved = path.expanduser().resolve()
        if not resolved.exists():
            continue
        value = str(resolved)
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def merge_settings_trust(
    existing_settings: dict[str, Any],
    existing_user_config: dict[str, Any],
    trusted_folders: list[str],
) -> dict[str, Any]:
    desired = dict(existing_settings)
    desired["trustedFolders"] = merge_trusted_folders(
        existing_settings.get("trustedFolders", []),
        existing_user_config.get("trustedFolders", []),
        trusted_folders,
    )
    return desired


def merge_user_config(existing: dict[str, Any]) -> dict[str, Any]:
    desired = dict(existing)
    desired.pop("trustedFolders", None)
    return desired


def write_json(path: Path, data: dict[str, Any], *, apply: bool, header: str = "") -> None:
    rendered = header + json.dumps(data, indent=2, sort_keys=False) + "\n"
    existing = path.read_text(encoding="utf-8") if path.exists() else None
    if existing == rendered:
        print(f"UNCHANGED {path}")
        return
    print(f"SYNC {path}")
    if not apply:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")


def render_launcher_content(real_cli_path: Path, default_args: list[str], management_commands: list[str]) -> str:
    quoted_defaults = " ".join(json.dumps(arg) for arg in default_args)
    command_cases = "|".join(sorted(management_commands))
    return f"""#!/usr/bin/env bash
set -euo pipefail

real_cli="${{COPILOT_REAL_CLI_PATH:-{real_cli_path}}}"
if [[ ! -x "$real_cli" ]]; then
  printf 'ERROR: managed Copilot launcher cannot find executable: %s\\n' "$real_cli" >&2
  exit 127
fi

if [[ "${{COPILOT_DISABLE_MANAGED_DEFAULTS:-}}" == "1" ]]; then
  exec "$real_cli" "$@"
fi

management=0
for arg in "$@"; do
  case "$arg" in
    -h|--help|-v|--version)
      management=1
      break
      ;;
    --)
      break
      ;;
    -*)
      continue
      ;;
    {command_cases})
      management=1
      break
      ;;
    *)
      break
      ;;
  esac
done

if (( management == 1 )); then
  exec "$real_cli" "$@"
fi

exec "$real_cli" {quoted_defaults} "$@"
"""


def render_launcher(
    target: Path,
    real_cli_path: Path,
    overlay: dict[str, Any],
    *,
    apply: bool,
) -> None:
    launcher = overlay.get("launcher", {})
    if not launcher.get("enabled", True):
        print(f"SKIP {target} (launcher disabled)")
        return
    default_args = launcher.get("defaultArgs", [])
    if not isinstance(default_args, list) or not all(isinstance(arg, str) for arg in default_args):
        raise CopilotSyncError("launcher.defaultArgs must be an array of strings")
    management_commands = launcher.get("managementCommands", sorted(MANAGEMENT_COMMANDS))
    if not isinstance(management_commands, list) or not all(isinstance(arg, str) for arg in management_commands):
        raise CopilotSyncError("launcher.managementCommands must be an array of strings")
    content = render_launcher_content(real_cli_path, default_args, management_commands)
    existing = target.read_text(encoding="utf-8") if target.exists() and target.is_file() else None
    if existing == content:
        print(f"UNCHANGED {target}")
        return
    print(f"SYNC {target} (managed Copilot launcher)")
    if not apply:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        target.unlink()
    target.write_text(content, encoding="utf-8")
    target.chmod(0o755)


def render_hooks_file(
    hooks_file: Path,
    hooks_registry_file: Path,
    overlay: dict[str, Any],
    *,
    apply: bool,
) -> None:
    hooks = overlay.get("hooks", {})
    if not hooks.get("managedCopilotHooks", False):
        print(f"SKIP {hooks_file} (managed Copilot hooks disabled)")
        return
    registry = load_hooks_registry(hooks_registry_file)
    desired = render_copilot_hooks(registry)
    rendered = render_json(desired)
    existing = hooks_file.read_text(encoding="utf-8") if hooks_file.exists() else None
    if existing == rendered:
        print(f"UNCHANGED {hooks_file}")
        return
    print(f"SYNC {hooks_file} (managed Copilot hooks)")
    if not apply:
        return
    hooks_file.parent.mkdir(parents=True, exist_ok=True)
    hooks_file.write_text(rendered, encoding="utf-8")


def sync(
    overlay_file: Path,
    hooks_registry_file: Path,
    settings_file: Path,
    user_config_file: Path,
    hooks_file: Path,
    launcher_target: Path,
    real_cli_path: Path,
    github_root: Path,
    *,
    apply: bool,
) -> None:
    overlay = load_overlay(overlay_file)
    home = settings_file.expanduser().resolve().parents[0].parent

    settings = read_json_object(settings_file, allow_comments=True)
    user_config = read_json_object(user_config_file, allow_comments=True)
    trusted_folders = discover_trusted_folders(overlay, github_root, home)
    desired_settings = merge_settings(settings, overlay)
    desired_settings = merge_settings_trust(
        desired_settings,
        user_config,
        trusted_folders,
    )
    write_json(settings_file, desired_settings, apply=apply)

    desired_user_config = merge_user_config(user_config)
    write_json(user_config_file, desired_user_config, apply=apply, header=CONFIG_HEADER)

    render_hooks_file(hooks_file, hooks_registry_file, overlay, apply=apply)
    render_launcher(launcher_target, real_cli_path, overlay, apply=apply)


def fail(message: str) -> None:
    raise CopilotSyncError(message)


def json_contains_forbidden(value: Any, forbidden: list[str]) -> bool:
    rendered = json.dumps(value, sort_keys=True, default=str)
    return any(item in rendered for item in forbidden)


def run_cli_json(real_cli_path: Path, args: list[str]) -> Any:
    result = subprocess.run(
        [str(real_cli_path), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        fail(
            f"Copilot CLI command failed: {real_cli_path} {' '.join(args)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(f"Copilot CLI did not return JSON for {' '.join(args)}: {exc}")


def app_skill_names(app_support_dir: Path) -> list[str]:
    app_skills = app_support_dir / "app-skills"
    if not app_skills.is_dir():
        return []
    return sorted(path.name for path in app_skills.iterdir() if (path / "SKILL.md").is_file())


def direct_skill_copies(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(root.glob("*/SKILL.md"))


def repo_github_skill_copies(github_root: Path) -> list[Path]:
    if not github_root.is_dir():
        return []
    skill_files: list[Path] = []
    for repo in sorted(path for path in github_root.iterdir() if path.is_dir()):
        skill_files.extend(direct_skill_copies(repo / ".github/skills"))
    return sorted(skill_files)


def check(
    overlay_file: Path,
    hooks_registry_file: Path,
    settings_file: Path,
    user_config_file: Path,
    hooks_file: Path,
    launcher_target: Path,
    real_cli_path: Path,
    github_root: Path,
    app_support_dir: Path,
    *,
    skip_cli_probe: bool,
) -> None:
    overlay = load_overlay(overlay_file)
    actual_settings = read_json_object(settings_file, allow_comments=True)
    user_config = read_json_object(user_config_file, allow_comments=True)
    expected_settings = merge_settings(actual_settings, overlay)
    for key, expected_value in overlay.get("settings", {}).items():
        if actual_settings.get(key) != expected_value:
            fail(f"Copilot setting drift: {settings_file} {key}={actual_settings.get(key)!r}, expected {expected_value!r}")

    forbidden = overlay.get("hooks", {}).get("forbiddenCommandSubstrings", [])
    if not isinstance(forbidden, list) or not all(isinstance(item, str) for item in forbidden):
        fail("hooks.forbiddenCommandSubstrings must be an array of strings")
    if json_contains_forbidden(actual_settings.get("hooks", {}), forbidden):
        fail(f"forbidden Copilot hook command is still present in {settings_file}")

    home = settings_file.expanduser().resolve().parents[0].parent
    expected_trusted = set(discover_trusted_folders(overlay, github_root, home))
    actual_trusted_raw = actual_settings.get("trustedFolders", [])
    if not isinstance(actual_trusted_raw, list):
        fail(f"trustedFolders must be an array in {settings_file}")
    actual_trusted = {str(Path(path).expanduser().resolve()) for path in actual_trusted_raw if isinstance(path, str)}
    missing_trusted = sorted(expected_trusted - actual_trusted)
    if missing_trusted:
        fail(f"Copilot settings trustedFolders missing {len(missing_trusted)} entries, first missing: {missing_trusted[0]}")
    duplicate_config_trust = sorted(
        expected_trusted
        & set(normalized_path_list(user_config.get("trustedFolders", [])))
    )
    if duplicate_config_trust:
        fail(f"managed Copilot trustedFolders still duplicated in {user_config_file}: {duplicate_config_trust[0]}")
    if json_contains_forbidden(user_config.get("hooks", {}), forbidden):
        fail(f"forbidden Copilot hook command is still present in {user_config_file}")

    if overlay.get("hooks", {}).get("managedCopilotHooks", False):
        expected_hooks = render_json(render_copilot_hooks(load_hooks_registry(hooks_registry_file)))
        if not hooks_file.is_file():
            fail(f"missing managed Copilot hooks file: {hooks_file}")
        if hooks_file.read_text(encoding="utf-8") != expected_hooks:
            fail(f"managed Copilot hooks file is out of sync: {hooks_file}")

    launcher = overlay.get("launcher", {})
    if launcher.get("enabled", True):
        expected_launcher = render_launcher_content(
            real_cli_path,
            launcher.get("defaultArgs", []),
            launcher.get("managementCommands", sorted(MANAGEMENT_COMMANDS)),
        )
        if not launcher_target.is_file():
            fail(f"missing managed Copilot launcher: {launcher_target}")
        if launcher_target.read_text(encoding="utf-8") != expected_launcher:
            fail(f"managed Copilot launcher is out of sync: {launcher_target}")
        if not os.access(launcher_target, os.X_OK):
            fail(f"managed Copilot launcher is not executable: {launcher_target}")

    copilot_skill_dir = settings_file.parent / "skills"
    if overlay.get("skills", {}).get("copilotSkillDirectoryPolicy") == "empty":
        skill_files = direct_skill_copies(copilot_skill_dir)
        if skill_files:
            fail(f"unexpected direct Copilot skill copies under {copilot_skill_dir}: {skill_files[0]}")
    if overlay.get("skills", {}).get("projectGithubSkillDirectoryPolicy") == "empty":
        skill_files = repo_github_skill_copies(github_root)
        if skill_files:
            fail(f"unexpected project Copilot skill copies under .github/skills: {skill_files[0]}")

    if not real_cli_path.is_file() or not os.access(real_cli_path, os.X_OK):
        fail(f"missing executable Copilot CLI: {real_cli_path}")
    if not skip_cli_probe:
        skills = run_cli_json(real_cli_path, ["skill", "list", "--json"])
        if not isinstance(skills, list):
            fail("Copilot CLI skill list JSON must be an array")
        app_skills_path = str((app_support_dir / "app-skills").resolve())
        for item in skills:
            if isinstance(item, dict) and str(item.get("path", "")).startswith(app_skills_path):
                fail(f"Copilot CLI is loading app-bundled skill as CLI skill: {item.get('name')}")
        mcp = run_cli_json(real_cli_path, ["mcp", "list", "--json"])
        if not isinstance(mcp, dict):
            fail("Copilot CLI MCP list JSON must be an object")

    observed_app_skills = app_skill_names(app_support_dir)
    if overlay.get("skills", {}).get("appSkillsPolicy") == "allow-known-only":
        expected = overlay.get("skills", {}).get("expectedAppBundledSkills", [])
        if not isinstance(expected, list) or not all(isinstance(item, str) for item in expected):
            fail("skills.expectedAppBundledSkills must be an array of strings")
        unexpected = sorted(set(observed_app_skills) - set(expected))
        if unexpected:
            fail(f"unexpected Copilot app bundled skills: {', '.join(unexpected)}")
    if observed_app_skills:
        print("OBSERVE Copilot app bundled skills: " + ", ".join(observed_app_skills))
    print("Copilot control plane OK")
    _ = expected_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync or validate managed GitHub Copilot CLI settings, trust, launcher, and skill-noise policy."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Apply managed Copilot state.")
    mode.add_argument("--check", action="store_true", help="Validate managed Copilot state.")
    mode.add_argument("--dry-run", action="store_true", help="Show managed writes without applying.")
    parser.add_argument("--settings-overlay", default=str(DEFAULT_SETTINGS_OVERLAY), help="Canonical Copilot settings overlay.")
    parser.add_argument("--hooks-registry", default=str(DEFAULT_HOOKS_REGISTRY), help="Canonical lifecycle hooks registry.")
    parser.add_argument("--settings-file", default=str(DEFAULT_SETTINGS_FILE), help="Target ~/.copilot/settings.json.")
    parser.add_argument("--user-config-file", default=str(DEFAULT_USER_CONFIG_FILE), help="Target ~/.copilot/config.json.")
    parser.add_argument("--hooks-file", default=str(DEFAULT_HOOKS_FILE), help="Target managed Copilot user hooks file.")
    parser.add_argument("--launcher-target", default=str(DEFAULT_LAUNCHER_TARGET), help="Managed terminal launcher target.")
    parser.add_argument("--real-cli-path", default=str(DEFAULT_REAL_CLI_PATH), help="Real Copilot CLI executable.")
    parser.add_argument("--github-root", default=str(DEFAULT_GITHUB_ROOT), help="GitHub workspace root to trust.")
    parser.add_argument("--app-support-dir", default=str(DEFAULT_APP_SUPPORT_DIR), help="GitHub Copilot app support directory.")
    parser.add_argument("--skip-cli-probe", action="store_true", help="Skip live copilot skill/mcp CLI probes during --check.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    overlay_file = output_path(Path(args.settings_overlay))
    hooks_registry_file = output_path(Path(args.hooks_registry))
    settings_file = output_path(Path(args.settings_file))
    user_config_file = output_path(Path(args.user_config_file))
    hooks_file = output_path(Path(args.hooks_file))
    launcher_target = output_path(Path(args.launcher_target))
    real_cli_path = output_path(Path(args.real_cli_path))
    github_root = output_path(Path(args.github_root)).resolve()
    app_support_dir = output_path(Path(args.app_support_dir)).resolve()

    try:
        if args.check:
            check(
                overlay_file,
                hooks_registry_file,
                settings_file,
                user_config_file,
                hooks_file,
                launcher_target,
                real_cli_path,
                github_root,
                app_support_dir,
                skip_cli_probe=args.skip_cli_probe,
            )
        else:
            sync(
                overlay_file,
                hooks_registry_file,
                settings_file,
                user_config_file,
                hooks_file,
                launcher_target,
                real_cli_path,
                github_root,
                apply=args.apply,
            )
    except CopilotSyncError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
