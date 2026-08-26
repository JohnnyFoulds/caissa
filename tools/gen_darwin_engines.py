#!/usr/bin/env python3
"""
gen_darwin_engines.py  — enumerate, smoke-test, and register all engines for macOS.

For every engine in bin/OS/linux/OSEngines.py and bin/OS/win32/OSEngines.py:
  1. Probe it through the bridge (escalating mode tiers).
  2. Write a wrapper script in bin/OS/darwin/Engines/<folder>/<exe>.
  3. Write tools/engine-report.{json,md} — the full compatibility matrix.

Safe to re-run after `git pull`; only re-probes engines whose wrapper doesn't exist
(pass --force to reprobe everything).

Usage:
    python3 tools/gen_darwin_engines.py [--force] [--workers N]
"""
import argparse
import importlib.util
import json
import os
import select
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO = Path(__file__).resolve().parents[1]
DARWIN_ENGINES = REPO / "bin/OS/darwin/Engines"
DARWIN_ENGINES.mkdir(parents=True, exist_ok=True)

LC_ENGINE = REPO / "tools/lc-engine"
REPORT_JSON = REPO / "tools/engine-report.json"
REPORT_MD = REPO / "tools/engine-report.md"

# Engines that are always native (handled by OSEngines.py directly)
NATIVE_KEYS = {"stockfish", "lc0", "irina", "eguzki", "eguzkilore"} | {
    f"maia-{lvl}" for lvl in list(range(1100, 2000, 100)) + [2200]
}


def load_osengines(platform: str, folder_engines: str) -> dict:
    """Import the upstream OSEngines.py for a platform, return its read_engines() dict."""
    import types

    # Stub FasterCode
    fake_fc = types.ModuleType("FasterCode")
    fake_fc.bmi2 = lambda: False
    fake_fc.set_fen = lambda fen: None
    sys.modules["FasterCode"] = fake_fc

    # Temporarily add bin/ and bin/OS/<platform> to sys.path
    bin_dir = str(REPO / "bin")
    os_dir = str(REPO / "bin/OS" / platform)
    sys.path[:0] = [bin_dir, os_dir]

    # OSEngines.py calls Code.configuration.x_maia_nodes_exponential via Engines.set_nodes_maia.
    # Stub out Code.configuration so that read_engines() completes without a full app init.
    import Code
    if Code.configuration is None:
        cfg_stub = types.SimpleNamespace(x_maia_nodes_exponential=False)
        Code.configuration = cfg_stub
        _injected_config = True
    else:
        _injected_config = False

    try:
        spec = importlib.util.spec_from_file_location(
            f"OSEngines_{platform}",
            REPO / "bin/OS" / platform / "OSEngines.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # Call read_engines() while the config stub is still active
        return mod.read_engines(folder_engines)
    finally:
        if _injected_config:
            Code.configuration = None
        sys.path[:2] = []


def probe_engine(key, path_exe: Path, is_windows: bool, timeout=20) -> dict:
    """
    Probe an engine through the bridge.  Send 'uci', read until 'uciok', then quit.

    We use Popen (not run/communicate) so we can read output line-by-line before
    closing stdin.  relay.py kills the engine when it sees stdin EOF; if we close
    stdin before reading 'uciok' the engine gets killed mid-response.
    """
    if is_windows:
        modes = ["wine", "wine32"]
    else:
        modes = ["direct", "qemu64"]

    for mode in modes:
        proc = None
        try:
            proc = subprocess.Popen(
                [str(LC_ENGINE), mode, str(path_exe)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            # Send uci and read output until we see uciok or timeout
            proc.stdin.write("uci\n")
            proc.stdin.flush()

            output_lines = []
            deadline = time.time() + timeout
            found_uciok = False
            while time.time() < deadline:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                # Non-blocking poll so we can respect the deadline even if
                # the engine stops printing (e.g. waiting for more UCI input)
                ready, _, _ = select.select([proc.stdout], [], [], min(remaining, 1.0))
                if not ready:
                    continue   # no data yet, re-check deadline
                line = proc.stdout.readline()
                if not line:  # EOF — engine exited unexpectedly
                    break
                output_lines.append(line)
                if "uciok" in line:
                    found_uciok = True
                    break

            # Clean shutdown: send quit then close stdin (relay will kill if needed)
            try:
                proc.stdin.write("quit\n")
                proc.stdin.flush()
                proc.stdin.close()
            except Exception:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

            if found_uciok:
                return {"status": "ok", "mode": mode, "output_sample": "".join(output_lines[:20])}
        except Exception:
            pass
        finally:
            if proc and proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass

    return {"status": "failed", "mode": None, "output_sample": ""}


def write_wrapper(engine_dir: Path, exe_name: str, mode: str, abs_exe: Path):
    """Write a tiny shell wrapper that calls lc-engine."""
    wrapper = engine_dir / exe_name
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper.write_text(textwrap.dedent(f"""\
        #!/bin/sh
        # Auto-generated by gen_darwin_engines.py
        # Bridges to Docker container: mode={mode}
        exec "{LC_ENGINE}" {mode} "{abs_exe}" "$@"
    """))
    wrapper.chmod(0o755)
    return wrapper


def process_one(entry, force):
    key = entry["key"]
    abs_exe = entry["abs_exe"]
    is_windows = entry["is_windows"]
    folder = entry["folder"]
    exe_name = entry["exe_name"]

    darwin_dir = DARWIN_ENGINES / folder
    wrapper_path = darwin_dir / exe_name

    if wrapper_path.exists() and not force:
        return key, {"status": "cached", "mode": "cached", "note": "wrapper already exists"}

    if not abs_exe.exists():
        return key, {"status": "missing", "mode": None, "note": f"{abs_exe} not in repo"}

    result = probe_engine(key, abs_exe, is_windows)
    if result["status"] == "ok":
        write_wrapper(darwin_dir, exe_name, result["mode"], abs_exe)
        result["wrapper"] = str(wrapper_path)
    return key, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-probe all engines even if wrapper exists")
    parser.add_argument("--workers", type=int, default=6, help="Parallel probe workers (default 6)")
    args = parser.parse_args()

    # Make sure the container is running
    print("Ensuring engine bridge container is running...")
    ret = subprocess.run([str(LC_ENGINE), "--ensure"], capture_output=True, text=True)
    if ret.returncode != 0:
        print(f"WARNING: bridge container not available — skipping bridged engines. ({ret.stderr.strip()})")
        bridge_available = False
    else:
        bridge_available = True

    # Collect all engines from linux + win32
    entries = []
    for platform in ("linux", "win32"):
        is_windows = platform == "win32"
        folder_engines_host = REPO / "bin/OS" / platform / "Engines"
        try:
            engines_dict = load_osengines(platform, str(folder_engines_host))
        except Exception as e:
            print(f"WARNING: could not load {platform}/OSEngines.py: {e}")
            continue

        for key, eng in engines_dict.items():
            if key in NATIVE_KEYS:
                continue
            abs_exe = Path(eng.path_exe).resolve() if not os.path.isabs(eng.path_exe) else Path(eng.path_exe)
            # path_exe in Engines.py uses Util.relative_path which may be relative to cwd.
            # Reconstruct from known layout: <platform>/Engines/<folder>/<exe>
            rel_parts = list(Path(str(eng.path_exe).replace("\\", "/")).parts)
            try:
                ei = [p.lower() for p in rel_parts].index("engines")
                # folder is the directory name immediately after "Engines"
                eng_folder = rel_parts[ei + 1]
                eng_exe = rel_parts[-1]
                # abs_exe preserves the full sub-path (e.g. Engines/pawny/windows/pawny.exe)
                sub_path = Path(*rel_parts[ei + 1:])   # folder/[subdir/...]exe
                abs_exe = folder_engines_host / sub_path
            except (ValueError, IndexError):
                eng_folder = Path(eng.path_exe).parent.name
                eng_exe = Path(eng.path_exe).name
                abs_exe = Path(eng.path_exe)

            entries.append({
                "key": key,
                "platform": platform,
                "is_windows": is_windows,
                "folder": eng_folder,
                "exe_name": eng_exe,
                "abs_exe": abs_exe,
                "author": eng.autor,
                "version": eng.version if hasattr(eng, "version") else "",
                "elo": eng.elo,
            })

    # Prefer linux over win32 for shared keys: native Linux runs faster than Wine.
    # Only use the win32 entry when there is no linux counterpart.
    linux_keys = {e["key"] for e in entries if e["platform"] == "linux"}
    entries = [e for e in entries if e["platform"] == "linux" or e["key"] not in linux_keys]

    print(f"Found {len(entries)} bridged engine candidates.")

    if not bridge_available:
        print("Bridge unavailable — no wrappers generated. Run with Docker running.")
        return

    # Probe in parallel
    results = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(process_one, e, args.force): e for e in entries}
        done = 0
        for fut in as_completed(futs):
            done += 1
            e = futs[fut]
            try:
                key, res = fut.result()
            except Exception as ex:
                key, res = e["key"], {"status": "error", "mode": None, "note": str(ex)}
            results[key] = {**e, **res, "abs_exe": str(e["abs_exe"])}
            status_sym = "✓" if res["status"] == "ok" else ("·" if res["status"] == "cached" else "✗")
            print(f"  [{done:3d}/{len(entries)}] {status_sym} {key:<30} {res.get('mode') or res.get('status','')}")
    elapsed = time.time() - t0

    # Summary
    ok = [k for k, v in results.items() if v["status"] in ("ok", "cached")]
    failed = [k for k, v in results.items() if v["status"] not in ("ok", "cached")]
    print(f"\nDone in {elapsed:.0f}s — {len(ok)} working, {len(failed)} failed/missing")
    if failed:
        print("  Failed:", ", ".join(sorted(failed)))

    # Write JSON report
    REPORT_JSON.write_text(json.dumps(results, indent=2, default=str))

    # Write Markdown report
    lines = [
        "# LucasChess engine bridge report",
        f"\nGenerated: {time.strftime('%Y-%m-%d %H:%M')}  ",
        f"Working: **{len(ok)}**  Failed/missing: **{len(failed)}**\n",
        "| Engine | Platform | Mode | ELO | Status |",
        "|--------|----------|------|-----|--------|",
    ]
    for key in sorted(results):
        r = results[key]
        sym = "✓" if r["status"] in ("ok", "cached") else "✗"
        lines.append(f"| {key} | {r.get('platform','')} | {r.get('mode') or '-'} | {r.get('elo','')} | {sym} {r['status']} |")
    REPORT_MD.write_text("\n".join(lines) + "\n")
    print(f"Reports written to:\n  {REPORT_JSON}\n  {REPORT_MD}")


if __name__ == "__main__":
    # Code/__init__.py uses sys.argv[0] to determine the working directory.
    # Spoof it so __init__.py resolves paths relative to bin/ (as if running LucasR.py).
    sys.argv[0] = str(REPO / "bin" / "LucasR.py")
    main()
