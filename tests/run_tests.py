#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess

def main():
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(tests_dir)
    
    # Make sure we add project_root to PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = project_root + os.path.pathsep + env.get("PYTHONPATH", "")
    
    dbus_cmd = shutil.which("dbus-run-session")
    args = sys.argv[1:] if len(sys.argv) > 1 else [tests_dir]
    if dbus_cmd:
        print("Re-running tests inside dbus-run-session...", flush=True)
        cmd = [dbus_cmd, "--", sys.executable, "-m", "pytest", "-v"] + args
        res = subprocess.run(cmd, env=env)
        sys.exit(res.returncode)
    else:
        print("WARNING: dbus-run-session not found on this system. Running tests directly.", file=sys.stderr)
        cmd = [sys.executable, "-m", "pytest", "-v"] + args
        res = subprocess.run(cmd, env=env)
        sys.exit(res.returncode)

if __name__ == '__main__':
    main()
