"""Replace only native updater identities validated by the replay helper."""

import json
import shutil
import sys
from pathlib import Path

request, installed, output = sys.argv[1:]
entries = json.loads(Path(request).read_text())["entries"]
output = Path(output)
for entry in entries:
    for name in entry["replaces"]:
        (output / name).unlink(missing_ok=True)
    target = output / entry["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    shutil.copyfile(Path(installed) / entry["path"], target)
