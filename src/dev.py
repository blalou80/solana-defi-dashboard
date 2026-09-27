#!/usr/bin/env python3
"""defi-up — one command for local development.

Starts the data daemon and the Streamlit dashboard as child processes and
shuts both down cleanly on Ctrl-C. Deliberately simple (subprocess, not
threads): each half keeps its own logs and either can be run standalone
(`defi-daemon`, `streamlit run src/dashboard/app.py`).
"""
import os
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    env = {**os.environ, "PYTHONPATH": ROOT}
    daemon = subprocess.Popen(
        [sys.executable, "-m", "src.main"], cwd=ROOT, env=env
    )
    ui = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run",
            os.path.join(ROOT, "src", "dashboard", "app.py"),
            "--server.headless", "true",
        ],
        cwd=ROOT,
        env=env,
    )
    procs = [daemon, ui]
    print("defi-up: daemon + dashboard started. Ctrl-C to stop.")
    try:
        while all(p.poll() is None for p in procs):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            if p.poll() is None:
                p.send_signal(signal.SIGINT)
        deadline = time.time() + 10
        for p in procs:
            if p.poll() is None:
                try:
                    p.wait(timeout=max(0.1, deadline - time.time()))
                except subprocess.TimeoutExpired:
                    p.kill()
    codes = {p.poll() for p in procs}
    print(f"defi-up: stopped (exit codes {sorted(codes)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
