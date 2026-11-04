import json
import sys
from pathlib import Path

source, root, destination = sys.argv[1:]
request = json.loads(Path(source).read_text())
request["root"] = root
Path(destination).write_text(json.dumps(request))
