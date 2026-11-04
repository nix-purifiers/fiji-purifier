"""Replace scoped native classes while retaining deterministic JAR contents."""

import sys
import zipfile
from pathlib import Path

original, classes, prefix, output = sys.argv[1:]
contents = {}
with zipfile.ZipFile(original) as archive:
    for name in archive.namelist():
        contents[name] = archive.read(name)
for path in (Path(classes) / prefix).rglob("*.class"):
    contents[path.relative_to(classes).as_posix()] = path.read_bytes()
with zipfile.ZipFile(
    output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
) as archive:
    for name, data in sorted(contents.items()):
        info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = (0o40555 if name.endswith("/") else 0o100444) << 16
        archive.writestr(info, data, compresslevel=9)
