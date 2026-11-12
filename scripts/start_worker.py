"""Clear only this container's ephemeral Prometheus files before importing metrics."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

directory = Path(os.environ["PROMETHEUS_MULTIPROC_DIR"])
if str(directory) != "/tmp/triage-metrics":
    raise RuntimeError("Unexpected metrics directory")
directory.mkdir(exist_ok=True)
for path in directory.glob("*.db"):
    path.unlink()

from triage.worker import main  # noqa: E402

main()
