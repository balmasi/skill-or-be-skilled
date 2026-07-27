#!/usr/bin/env python3
"""Price a captured request: what every tool, server and skill costs on the
first prompt of every session.

The pricing maths here is agent-neutral. Parsing the wire format and issuing
token counts belong to the adapter (scripts/adapters/<agent>.py).

All independent counts are issued in one parallel wave, and per-tool prices are
cached on disk keyed by schema hash, so re-analysing a what-if capture that
shares most of its tools is nearly free."""
import argparse, json, os, re, sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adapters


def wave(fns, jobs):
    """Run independent count jobs concurrently. Adapters may supply their own."""
    with ThreadPoolExecutor(jobs) as ex:
        return list(ex.map(lambda f: f(), fns))


def solve_overhead(solo):
    """Every solo price carries the same fixed per-request tool-block overhead.

    With N priced tools, Σ(solo prices) counts that overhead N times while
    pricing all tools in one request counts it once, so the difference divided
    by N-1 recovers it. `solo` is [(name, price_including_overhead)] where the
    price is already relative to an empty request; `all_minus_base` is the cost
    of every tool in one request, likewise relative.
    """
    def _solve(all_minus_base):
        if len(solo) < 2:
            return 0.0
        return (sum(v for _, v in solo) - all_minus_base) / (len(solo) - 1)
    return _solve


def schema_costs(solo, allt, base, leave_one_out):
    """Turn solo prices into true per-tool schema costs.

    Tools the provider rejects when sent alone price as None; they fall back to
    leave-one-out, which carries no overhead term and so needs no correction.
    Returns (overhead, {name: schema_cost}).
    """
    good = [(k, v) for k, v in solo if v is not None]
    oh = solve_overhead(good)(allt - base)
    costs = {k: v - oh for k, v in good}
    for name, v in solo:
        if v is None:
            costs[name] = leave_one_out(name)
    return oh, costs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default=adapters.DEFAULT, choices=adapters.names())
    ap.add_argument("--capture", required=True, help="dir from capture.py")
    ap.add_argument("--json-out")
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args()

    ad = adapters.get(a.agent)
    d = json.load(open(os.path.join(a.capture, "request.json")))
    h = json.load(open(os.path.join(a.capture, "headers.json")))
    cap = ad.parse(d)
    count = ad.counter(h, jobs=a.jobs, use_cache=not a.no_cache)
    run = getattr(count, "wave", None) or (lambda fns: wave(fns, a.jobs))

    schemas = [t.schema for t in cap.tools]
    sys_, msgs, texts = cap.system, cap.messages, cap.texts

    # One wave: every count below is independent of the others.
    base = count.count()
    jobs = [lambda: count.count(schemas, system=sys_, messages=msgs),
            lambda: count.count([], system=sys_, messages=msgs),
            lambda: count.count(schemas, system=None, messages=msgs),
            lambda: count.count([], system=None, messages=msgs),
            lambda: count.count(schemas)]
    jobs += [(lambda t=t: count.count(messages=[{"role": "user", "content": t}])) for t in texts]
    jobs += [(lambda t=t: count.tool_price(t, base)) for t in cap.tools]
    r = run(jobs)

    total, no_tools, no_sys, msg_only, allt = r[:5]
    blk = list(zip(texts, [v - base for v in r[5:5 + len(texts)]]))
    solo = list(zip([t.name for t in cap.tools], r[5 + len(texts):]))

    oh, sch = schema_costs(
        solo, allt, base,
        leave_one_out=lambda name: allt - count.count(
            [t.schema for t in cap.tools if t.name != name]))
    count.save()

    print(f"\n{'='*62}\n  FIRST-PROMPT CONTEXT ({ad.name}): {total:,} tokens\n{'='*62}")
    print(f"  {'tool schemas':28} {total-no_tools:8,}")
    print(f"  {'system prompt':28} {total-no_sys:8,}")
    print(f"  {'messages / reminders':28} {msg_only:8,}")

    print(f"\n  message blocks")
    for t, n in blk:
        print(f"    {re.sub(r'\\s+',' ',t[:52]).strip():52} {n:7,}")

    print(f"\n  loaded tools  (fixed tool-block overhead: {oh:.0f})")
    for n_, v in sorted(sch.items(), key=lambda x: -x[1]):
        print(f"    {n_:52} {v:7,.0f}")

    # Adapter-declared breakdowns of individual message blocks.
    groups = {}
    for sec in ad.sections():
        text = next((t for t, _ in blk if sec.match(t)), None)
        if not text: continue
        tok = dict(blk)[text]
        rows = list(sec.split(text))
        tot = sum(w for _, w, _ in rows) or 1
        print(f"\n  {sec.title}  ({len(rows)} rows, {tok:,} tokens)")
        for label, w, note in rows[:sec.limit] if sec.limit else rows:
            groups[label] = w / tot * tok
            print(f"    {label:52} {groups[label]:7,.0f}  {note}".rstrip())

    controls = ad.controls(cap)
    if controls:
        print("\n  adjustable controls")
        for name, note in controls:
            print(f"    {name:44} {note}")

    print(f"\n  [{count.calls} count calls, {count.cached} from cache]")
    if a.json_out:
        json.dump({"agent": ad.name, "total": total, "tool_schemas": total - no_tools,
                   "system": total - no_sys, "messages": msg_only,
                   "tools": sch, "overhead": oh, "groups": groups,
                   "controls": dict(controls)},
                  open(a.json_out, "w"), indent=1)
        print(f"  wrote {a.json_out}")


if __name__ == "__main__":
    main()
