#!/usr/bin/env python3

import argparse
import json
import select
import os
import subprocess
import sys
import tempfile
from pathlib import Path


RUNTIME_REQUESTS = [
    ("model/list", {}),
    ("mcpServerStatus/list", {}),
    ("skills/list", {}),
    ("app/list", {}),
    ("experimentalFeature/list", {}),
]


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def extract_methods(schema_path):
    data = json.loads(Path(schema_path).read_text())
    methods = []
    for variant in data.get("oneOf", []):
        props = variant.get("properties", {})
        method = props.get("method", {})
        values = method.get("enum", [])
        methods.extend(values)
    return methods


def start_server():
    return subprocess.Popen(
        ["codex", "app-server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )


def send_json(server, payload):
    assert server.stdin is not None
    server.stdin.write(json.dumps(payload) + "\n")
    server.stdin.flush()


def read_json(server, timeout_sec=2.0):
    assert server.stdout is not None
    ready, _, _ = select.select([server.stdout], [], [], timeout_sec)
    if not ready:
        return None
    line = server.stdout.readline()
    if not line:
        raise RuntimeError("app-server closed stdout unexpectedly")
    return json.loads(line)


def runtime_probe():
    server = start_server()
    try:
        send_json(
            server,
            {
                "method": "initialize",
                "id": 0,
                "params": {"clientInfo": {"name": "codex_app_server_probe", "version": "0.1.0"}},
            },
        )
        init_result = None
        for _ in range(3):
            message = read_json(server)
            if message is None:
                break
            if message.get("id") == 0 and "result" in message:
                init_result = message
                break
        if init_result is None:
            raise RuntimeError("initialize did not return a result before timeout")

        send_json(server, {"method": "initialized", "params": {}})

        responses = {"initialize": init_result}
        timeouts = []
        request_id = 1
        for method, params in RUNTIME_REQUESTS:
            send_json(server, {"method": method, "id": request_id, "params": params})
            response = read_json(server)
            if response is None:
                timeouts.append(method)
            else:
                responses[method] = response
            request_id += 1
        if timeouts:
            responses["_timeouts"] = timeouts
        return responses
    finally:
        try:
            server.terminate()
            server.wait(timeout=2)
        except Exception:
            server.kill()


def summarize_runtime(responses):
    summary = {
        "userAgent": responses["initialize"]["result"]["userAgent"],
        "models": [],
        "mcpServers": [],
        "skillsByCwd": [],
        "appsCount": 0,
        "experimentalFeatures": [],
    }

    model_data = responses.get("model/list", {}).get("result", {}).get("data", [])
    for model in model_data:
        summary["models"].append(
            {
                "id": model.get("id"),
                "displayName": model.get("displayName"),
                "defaultReasoningEffort": model.get("defaultReasoningEffort"),
                "isDefault": model.get("isDefault"),
            }
        )

    mcp_data = responses.get("mcpServerStatus/list", {}).get("result", {}).get("data", [])
    for server in mcp_data:
        summary["mcpServers"].append(
            {
                "name": server.get("name"),
                "authStatus": server.get("authStatus"),
                "toolNames": sorted(server.get("tools", {}).keys()),
            }
        )

    skills_data = responses.get("skills/list", {}).get("result", {}).get("data", [])
    for entry in skills_data:
        summary["skillsByCwd"].append(
            {
                "cwd": entry.get("cwd"),
                "skills": [skill.get("name") for skill in entry.get("skills", [])],
            }
        )

    apps_data = responses.get("app/list", {}).get("result", {}).get("data", [])
    summary["appsCount"] = len(apps_data)

    feature_data = responses.get("experimentalFeature/list", {}).get("result", {}).get("data", [])
    for feature in feature_data:
        name = feature.get("name")
        if name is not None:
            summary["experimentalFeatures"].append(name)

    summary["timeouts"] = responses.get("_timeouts", [])

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Probe the locally installed Codex App Server for schema and runtime-discoverable details."
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument(
        "--skip-runtime",
        action="store_true",
        help="Only generate and inspect local schema/types without launching a live app-server session.",
    )
    parser.add_argument(
        "--experimental",
        action="store_true",
        help="Include experimental methods and fields in generated schema output.",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="codex-app-server-probe-") as tmpdir:
        schema_dir = Path(tmpdir) / "schema"
        ts_dir = Path(tmpdir) / "ts"
        schema_dir.mkdir()
        ts_dir.mkdir()

        schema_cmd = ["codex", "app-server", "generate-json-schema", "--out", str(schema_dir)]
        ts_cmd = ["codex", "app-server", "generate-ts", "--out", str(ts_dir)]
        if args.experimental:
            schema_cmd.append("--experimental")
            ts_cmd.append("--experimental")

        run(schema_cmd)
        run(ts_cmd)

        client_methods = extract_methods(schema_dir / "ClientRequest.json")
        server_methods = extract_methods(schema_dir / "ServerRequest.json")

        output = {
            "schemaDir": str(schema_dir),
            "tsDir": str(ts_dir),
            "clientRequestMethods": sorted(client_methods),
            "serverRequestMethods": sorted(server_methods),
        }

        if not args.skip_runtime:
            responses = runtime_probe()
            output["runtime"] = summarize_runtime(responses)

        if args.json:
            json.dump(output, sys.stdout, indent=2)
            sys.stdout.write("\n")
            return

        print("Codex App Server local probe")
        print(f"schema dir: {output['schemaDir']}")
        print(f"ts dir: {output['tsDir']}")
        print(f"client request methods: {len(output['clientRequestMethods'])}")
        print(f"server request methods: {len(output['serverRequestMethods'])}")
        print()
        print("Client request methods")
        for method in output["clientRequestMethods"]:
            print(f"- {method}")
        print()
        print("Server request methods")
        for method in output["serverRequestMethods"]:
            print(f"- {method}")

        runtime = output.get("runtime")
        if runtime is not None:
            print()
            print("Runtime summary")
            print(f"- userAgent: {runtime['userAgent']}")
            print(f"- models: {', '.join(model['id'] for model in runtime['models']) or '-'}")
            print(
                f"- mcp servers: {', '.join(server['name'] for server in runtime['mcpServers']) or '-'}"
            )
            print(f"- apps count: {runtime['appsCount']}")
            print(
                f"- experimental features: {', '.join(runtime['experimentalFeatures']) or '-'}"
            )
            print(f"- timed out requests: {', '.join(runtime['timeouts']) or '-'}")
            for entry in runtime["skillsByCwd"]:
                print(f"- skills[{entry['cwd']}]: {', '.join(entry['skills']) or '-'}")


if __name__ == "__main__":
    main()
