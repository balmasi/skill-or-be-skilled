#!/usr/bin/env python3
"""Measure several removal scenarios at once.

Captures are independent processes, so they run concurrently: N scenarios cost
about as long as the slowest one rather than N x one. Prints each scenario's real
first-prompt total and its delta against the first scenario listed.

  sweep.py --cwd ~/proj --workdir /tmp/ca \
      "baseline=" \
      "no-workflow=--disallowed-tools Workflow" \
      "lean=--disallowed-tools Workflow Agent ScheduleWakeup ReportFindings"
"""
import argparse, json, os, shlex, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import adapters

def run(name, extra, cwd, workdir, agent):
    out = os.path.join(workdir, name)
    cap = [sys.executable, os.path.join(HERE, "capture.py"), "--agent", agent,
           "--outdir", out, "--cwd", cwd]
    if extra: cap += ["--extra"] + shlex.split(extra)
    t0 = time.time()
    p = subprocess.run(cap, capture_output=True, text=True)
    if p.returncode != 0:
        return name, None, (p.stderr or p.stdout).strip().splitlines()[-1:] or ["failed"]
    an = subprocess.run([sys.executable, os.path.join(HERE, "analyze.py"),
                         "--agent", agent,
                         "--capture", out, "--json-out", os.path.join(out, "report.json")],
                        capture_output=True, text=True)
    if an.returncode != 0:
        return name, None, [(an.stderr or "analyze failed").strip().splitlines()[-1]]
    r = json.load(open(os.path.join(out, "report.json")))
    r["secs"] = time.time() - t0
    return name, r, None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default=adapters.DEFAULT, choices=adapters.names())
    ap.add_argument("--cwd", default=os.getcwd())
    ap.add_argument("--workdir", default="/tmp/context-audit-sweep")
    ap.add_argument("--jobs", type=int, default=4,
                    help="concurrent captures. Each launches a CLI plus its MCP "
                         "servers, so beyond ~4 they contend and stop getting faster.")
    ap.add_argument("scenarios", nargs="+", metavar="NAME=EXTRA_ARGS")
    a = ap.parse_args()

    specs = []
    for s in a.scenarios:
        name, _, extra = s.partition("=")
        specs.append((name.strip(), extra.strip()))
    os.makedirs(a.workdir, exist_ok=True)

    t0 = time.time()
    with ThreadPoolExecutor(a.jobs) as ex:
        results = list(ex.map(lambda s: run(s[0], s[1], a.cwd, a.workdir, a.agent), specs))
    wall = time.time() - t0

    base = next((r for n, r, e in results if r), None)
    print(f"\n{'scenario':26} {'total':>8} {'tools':>8} {'delta':>9}")
    print("-" * 55)
    for name, r, err in results:
        if not r:
            print(f"{name:26} {'FAILED':>8}  {err[0][:40] if err else ''}")
            continue
        delta = r["total"] - base["total"]
        print(f"{name:26} {r['total']:8,} {r['tool_schemas']:8,} "
              f"{delta:+9,}" if r is not base else
              f"{name:26} {r['total']:8,} {r['tool_schemas']:8,} {'—':>9}")
    print(f"\n{len(specs)} scenarios in {wall:.1f}s "
          f"(slowest single capture {max((r['secs'] for _, r, _ in results if r), default=0):.1f}s)")

if __name__ == "__main__":
    main()
