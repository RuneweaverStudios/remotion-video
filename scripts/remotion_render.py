#!/usr/bin/env python3
"""
Run Remotion render or still from the configured project path.
Usage:
  python3 remotion_render.py render <entry> <composition-id> <output> [--props '{}'] [--json]
  python3 remotion_render.py still <entry> <composition-id> <output> [--frame 0] [--props '{}'] [--json]
  python3 remotion_render.py status

Options:
  --json    Output structured JSON (consistent for machine consumption)

Config: config.json in skill root with "projectPath" (required for render/still).
"""

import json
import os
import subprocess
import sys

def find_skill_root():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(script_dir)

def load_config():
    root = find_skill_root()
    path = os.path.join(root, "config.json")
    if not os.path.isfile(path):
        return None, "config.json not found"
    with open(path) as f:
        return json.load(f), None

def get_project_dir(config):
    raw = config.get("projectPath") or ""
    if not raw.strip():
        return None
    root = find_skill_root()
    if not os.path.isabs(raw):
        # Resolve relative to workspace root (skills/remotion-video -> workspace)
        workspace = os.path.normpath(os.path.join(root, "..", ".."))
        raw = os.path.join(workspace, raw.lstrip("/").lstrip("\\"))
    return os.path.abspath(raw)

def main():
    config, err = load_config()
    if err:
        print(json.dumps({"ok": False, "error": err}), file=sys.stderr)
        sys.exit(1)

    project_dir = get_project_dir(config)
    if not project_dir or not os.path.isdir(project_dir):
        raw_path = config.get("projectPath", "")
        if not raw_path or not raw_path.strip():
            error_msg = (
                "projectPath is empty in config.json. "
                "To set up: 1) Open config.json in the remotion-video skill directory, "
                "2) Set 'projectPath' to the absolute path of your Remotion project "
                "(e.g., '/Users/you/my-remotion-project'), "
                "3) Ensure the directory contains a valid Remotion project with package.json."
            )
        else:
            error_msg = f"projectPath directory not found: {raw_path}. Verify the path exists and is accessible."
        print(json.dumps({"ok": False, "error": error_msg, "projectPath": raw_path}), file=sys.stderr)
        sys.exit(1)

    node_path = (config.get("nodePath") or "").strip()
    env = os.environ.copy()
    if node_path:
        env["PATH"] = os.path.dirname(node_path) + os.pathsep + env.get("PATH", "")

    argv = sys.argv[1:]

    # Parse --json flag for structured output
    json_output = "--json" in argv
    if json_output:
        argv = [a for a in argv if a != "--json"]

    if not argv or argv[0] == "status":
        print(json.dumps({"ok": True, "projectPath": project_dir, "config": {k: v for k, v in config.items() if k != "lambda" or v}}))
        return

    if argv[0] not in ("render", "still"):
        print(json.dumps({"ok": False, "error": "usage: render|still|status ..."}), file=sys.stderr)
        sys.exit(1)

    cmd = ["npx", "remotion", argv[0]]
    # Collect positional: entry, composition-id, output
    pos = []
    extra = []
    i = 1
    while i < len(argv):
        if argv[i] in ("--props", "--frame", "--codec", "--image-format", "--scale", "--quality") and i + 1 < len(argv):
            extra.extend([argv[i], argv[i + 1]])
            i += 2
        elif argv[i].startswith("-"):
            extra.append(argv[i])
            i += 1
        else:
            pos.append(argv[i])
            i += 1

    if argv[0] == "render" and len(pos) < 3:
        print(json.dumps({"ok": False, "error": "render requires <entry> <composition-id> <output>"}), file=sys.stderr)
        sys.exit(1)
    if argv[0] == "still" and len(pos) < 3:
        print(json.dumps({"ok": False, "error": "still requires <entry> <composition-id> <output>"}), file=sys.stderr)
        sys.exit(1)

    cmd.extend(pos)
    cmd.extend(extra)

    try:
        r = subprocess.run(cmd, cwd=project_dir, env=env, capture_output=True, text=True, timeout=3600)
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        if r.returncode != 0:
            result = {"ok": False, "returncode": r.returncode, "stdout": out, "stderr": err}
            print(json.dumps(result), file=sys.stderr)
            sys.exit(r.returncode)
        result = {"ok": True, "output": pos[2] if len(pos) >= 3 else None, "stdout": out, "stderr": err}
        if json_output:
            print(json.dumps(result))
        else:
            # Human-readable output when --json is not specified
            print(json.dumps(result))
    except subprocess.TimeoutExpired:
        print(json.dumps({"ok": False, "error": "render timed out (3600s)"}), file=sys.stderr)
        sys.exit(124)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
