"""Run a working-tree macro with the same immutable native Fiji runtime."""

import os
import subprocess
from pathlib import Path

from runtime import command

invocation, env, output, status = command(
    os.environ["FIJI_PURIFIER_ENVIRONMENT"],
    Path(os.environ["TMPDIR"]) / "fiji-state",
    os.environ["FIJI_PURIFIER_JAVA"],
    [
        "--headless",
        "--console",
        "-macro",
        os.environ["FIJI_PURIFIER_SCRIPT"],
        os.environ["FIJI_PURIFIER_OUTPUT"],
    ],
    os.environ.copy(),
)
if invocation is None:
    raise RuntimeError(f"native Fiji launch failed ({status}): {output}")
subprocess.run(invocation, env=env, check=True)
