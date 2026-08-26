#!/usr/bin/env python3
"""
relay.py — stdin relay with clean engine teardown on EOF.

Problem: when `docker exec` is killed by the host, dockerd does NOT send
SIGTERM/SIGKILL to the child process inside the container. The engine
would keep burning CPU indefinitely.

Solution: this relay owns stdin, forwards lines to the engine, and kills
the engine when stdin EOF is reached — which is exactly what happens when
the docker exec connection is dropped.

Usage: relay.py [runner [runner-args...]] engine-exe [engine-args...]
  relay.py /usr/bin/qemu-x86_64-static /path/to/engine
  relay.py wine /path/to/engine.exe
  relay.py /path/to/engine
"""
import os
import sys
import subprocess
import signal
import threading


def _kill_proc(proc):
    """Best-effort engine teardown: SIGTERM first, then SIGKILL."""
    try:
        proc.stdin.close()
    except Exception:
        pass
    # Try killing the whole process group (only works if setsid() succeeded)
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        pass
    # Direct kill as fallback
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        proc.wait(timeout=2)
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit("relay.py: no engine specified")

    proc = subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        # stdout/stderr inherited: engine writes directly, zero extra latency
        stdout=None,
        stderr=None,
    )

    def _pump():
        try:
            for line in sys.stdin.buffer:
                if proc.poll() is not None:
                    break
                proc.stdin.write(line)
                proc.stdin.flush()
        except (BrokenPipeError, IOError):
            pass
        finally:
            # stdin EOF or error — kill the engine
            _kill_proc(proc)

    t = threading.Thread(target=_pump, daemon=True)
    t.start()

    try:
        proc.wait()
    except KeyboardInterrupt:
        _kill_proc(proc)
    sys.exit(proc.returncode or 0)


if __name__ == "__main__":
    # Try to create a new session so killpg works for process trees.
    # This is blocked in some Docker configurations — that's OK, we have fallbacks.
    try:
        os.setsid()
    except PermissionError:
        pass
    main()
