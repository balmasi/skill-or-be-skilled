#!/usr/bin/env python3
"""Capture the real first-prompt API request a coding agent sends, without
spending tokens.

Runs a local proxy that records the request body and replies 400 (non-retryable,
so the agent exits at once instead of backing off). Everything agent-specific —
how the CLI is launched, when it is ready, how a prompt is delivered — lives in
scripts/adapters/<agent>.py.
"""
import argparse, http.server, json, os, socket, subprocess, sys, threading, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adapters


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class Capturer:
    def __init__(self, outdir):
        self.outdir = outdir; self.n = 0; self.first = threading.Event()
        os.makedirs(outdir, exist_ok=True)

    def serve(self, port):
        cap = self
        class H(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(self, *a): pass
            def _reply(self, code, obj):
                b = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers(); self.wfile.write(b)
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                cap.n += 1
                if cap.n == 1:
                    with open(f"{cap.outdir}/request.json", "wb") as f: f.write(body)
                    with open(f"{cap.outdir}/headers.json", "w") as f:
                        json.dump(dict(self.headers), f, indent=1)
                    cap.first.set()
                # 400 = non-retryable; the CLI gives up at once instead of backing off
                self._reply(400, {"type": "error",
                                  "error": {"type": "invalid_request_error",
                                            "message": "context-audit capture complete"}})
            def do_GET(self): self._reply(200, {})
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default=adapters.DEFAULT, choices=adapters.names())
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--cwd", default=os.getcwd())
    ap.add_argument("--tool-search", choices=["on", "off"], default="on",
                    help="on = what the agent actually sends today; off = every schema unrolled")
    ap.add_argument("--timeout", type=float, default=30)
    ap.add_argument("--settle", type=float, default=0.0,
                    help="extra wait after the agent settles. Default 0: the "
                         "adapter's self-check detects an early capture, so padding "
                         "blind is unnecessary. Raise only if the self-check says to.")
    ap.add_argument("--extra", nargs=argparse.REMAINDER, default=[],
                    help="extra args passed through to the agent, e.g. --extra --disallowed-tools Workflow")
    a = ap.parse_args()

    ad = adapters.get(a.agent)

    os.makedirs(a.outdir, exist_ok=True)
    logpath = os.path.join(a.outdir, "debug.log")
    for p in (logpath, os.path.join(a.outdir, "request.json")):
        if os.path.exists(p): os.remove(p)

    port = free_port()
    cap = Capturer(a.outdir); cap.serve(port)

    env = ad.env(os.environ, port, a.tool_search)
    cmd = ad.command(logpath, a.tool_search, a.extra)

    proc = subprocess.Popen(cmd, cwd=a.cwd, env=env, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
    t0 = time.time()
    ok, started, done = ad.wait_ready(logpath, a.timeout)
    ready = time.time() - t0
    time.sleep(a.settle)
    ad.send_prompt(proc, "say ok")
    got = cap.first.wait(timeout=a.timeout)
    try: proc.stdin.close()
    except Exception: pass
    try: proc.wait(timeout=10)
    except subprocess.TimeoutExpired: proc.kill()

    print(f"[{ad.name}] mcp servers: {done}/{started} settled in {ready:.2f}s "
          f"({'ok' if ok else 'TIMEOUT'})")
    if not got:
        print("ERROR: no request captured", file=sys.stderr); sys.exit(1)
    d = json.load(open(f"{a.outdir}/request.json"))
    print(f"captured {len(ad.parse(d).tools)} tools in {time.time()-t0:.2f}s -> {a.outdir}/request.json")

    log = open(logpath, errors="replace").read() if os.path.exists(logpath) else ""
    err = ad.self_check(d, log)
    if err:
        print(f"WARNING: {err}", file=sys.stderr); sys.exit(2)


if __name__ == "__main__":
    main()
