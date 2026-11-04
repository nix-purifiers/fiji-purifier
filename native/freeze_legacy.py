"""Freeze legacy ImageJ installation without changing project IO or menu refresh."""

import sys
from pathlib import Path

from java_patch import replace_method

source, output = map(Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
message = 'throw new IllegalStateException("Fiji plugins are locked; run fiji-purifier lock --update");'
for filename, methods in {
    "PluginInstaller.java": [
        ("public void run(String arg)", message),
        ("public boolean install(String path)", message),
    ],
    "ImageJ_Updater.java": [
        (
            "public void run(String arg)",
            'if (arg.equals("menus")) { updateMenus(); return; }\n' + message,
        )
    ],
}.items():
    text = (source / filename).read_text()
    for signature, body in methods:
        text = replace_method(text, signature, body)
    (output / filename).write_text(text)
