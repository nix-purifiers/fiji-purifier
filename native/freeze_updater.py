import sys
from pathlib import Path

from java_patch import replace_method

source, output = map(Path, sys.argv[1:3])
output.mkdir(parents=True, exist_ok=True)


for name, methods in {
    "UpToDate.java": [
        (
            "public static Result check(final File ijRoot)",
            "\t\treturn Result.UPDATES_MANAGED_DIFFERENTLY;",
        )
    ],
    "Installer.java": [
        (
            "public synchronized void start()",
            '\t\tthrow new IOException("Fiji plugins are locked; run fiji-purifier lock --update");',
        ),
        (
            "public void moveUpdatedIntoPlace()",
            '\t\tthrow new IOException("Fiji plugins are locked; run fiji-purifier lock --update");',
        ),
    ],
    "XMLFileDownloader.java": [
        (
            "public void start(boolean closeProgressAtEnd)",
            '\t\tthrow new IllegalStateException("Fiji update sites are locked; run fiji-purifier lock --update");',
        )
    ],
}.items():
    text = (source / name).read_text()
    for signature, body in methods:
        text = replace_method(text, signature, body)
    (output / name).write_text(text)

launcher = Path(sys.argv[3])
text = (launcher / "RemoteUpdater.java").read_text()
text = replace_method(
    text, "public static boolean runRemote(final Throwable cause)", "\t\treturn false;"
)
(output / "RemoteUpdater.java").write_text(text)
