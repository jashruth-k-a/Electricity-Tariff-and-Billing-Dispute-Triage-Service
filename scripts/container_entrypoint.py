"""Make fresh bind-mounted data directories writable, then drop root permanently."""
import os
import sys
from pathlib import Path

if os.getuid() == 0:
    for directory in [Path("/app/data"), Path("/app/output")]:
        directory.mkdir(parents=True, exist_ok=True)
        os.chown(directory, 10001, 10001)
    os.setgroups([])
    os.setgid(10001)
    os.setuid(10001)
if len(sys.argv) < 2:
    raise SystemExit("A container command is required")
os.execvp(sys.argv[1], sys.argv[1:])
