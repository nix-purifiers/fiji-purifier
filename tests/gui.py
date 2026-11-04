import os
import shutil
import signal
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

p = Path(__file__).resolve().parent
cli = Path(sys.argv[1]).resolve()
xvfb = Path(sys.argv[2]).resolve()
resources = Path(sys.argv[3]).resolve()
source = p.parent
with tempfile.TemporaryDirectory(prefix="fiji-gui-") as temporary:
    root = Path(temporary)
    for name in ["home", "config", "data", "cache", "runtime"]:
        (root / name).mkdir(mode=0o700)
    project = root / "project"
    shutil.copytree(
        source / "examples/minimal",
        project,
        ignore=shutil.ignore_patterns(".fiji-purifier", "output"),
    )
    macro = project / "build.ijm"
    prefix = "eval(\"script\", \"var app=Packages.ij.IJ.getInstance(); if(app==null || !app.isVisible()) throw 'native GUI is not visible'; if(!Packages.ij.Menus.getCommands().containsKey('Morphological Filters')) throw 'native plugin menu absent';\");\n"
    macro.write_text(
        prefix + macro.read_text() + '\neval("script", "java.lang.System.exit(0);");\n'
    )
    bus = ET.Element("busconfig")
    ET.SubElement(bus, "type").text = "session"
    ET.SubElement(bus, "listen").text = "unix:tmpdir=" + str(root / "runtime")
    ET.SubElement(bus, "auth").text = "EXTERNAL"
    policy = ET.SubElement(bus, "policy", context="default")
    for attribute in ["own", "send_destination", "receive_sender"]:
        ET.SubElement(policy, "allow", {attribute: "*"})
    ET.ElementTree(bus).write(root / "bus.conf", encoding="UTF-8", xml_declaration=True)
    env = os.environ.copy()
    for name in [
        "WAYLAND_DISPLAY",
        "WAYLAND_SOCKET",
        "DBUS_SESSION_BUS_ADDRESS",
        "DBUS_STARTER_ADDRESS",
        "DBUS_STARTER_BUS_TYPE",
        "SESSION_MANAGER",
        "AT_SPI_BUS_ADDRESS",
        "QT_QPA_PLATFORMTHEME",
        "XDG_ACTIVATION_TOKEN",
        "DESKTOP_STARTUP_ID",
        "INTERACTIVE_HTML_BOM_CLI_MODE",
    ]:
        env.pop(name, None)
    for name in ["JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "CLASSPATH"]:
        env.pop(name, None)
    env.update(
        HOME=str(root / "home"),
        XDG_CONFIG_HOME=str(root / "config"),
        XDG_DATA_HOME=str(root / "data"),
        XDG_CACHE_HOME=str(root / "cache"),
        XDG_RUNTIME_DIR=str(root / "runtime"),
        QT_QPA_PLATFORM="xcb",
        GDK_BACKEND="x11",
        GTK_USE_PORTAL="0",
        QTWEBENGINE_DISABLE_SANDBOX="1",
        NO_AT_BRIDGE="1",
        LIBGL_ALWAYS_SOFTWARE="1",
        DBUS_SYSTEM_BUS_ADDRESS="unix:path=" + str(root / "no-system-bus"),
        FONTCONFIG_FILE=str(resources / "fonts.conf"),
        PYTHONNOUSERSITE="1",
    )
    env["FIJI_PURIFIER_PROJECT"] = str(project)
    args = [
        str(xvfb / "bin/xvfb-run"),
        "-a",
        str(resources / "bin/dbus-run-session"),
        "--dbus-daemon=" + str(resources / "bin/dbus-daemon"),
        "--config-file=" + str(root / "bus.conf"),
        "--",
        str(cli / "bin/fiji"),
        "--console",
        "-macro",
        str(macro),
        str(project / "output"),
    ]
    with (root / "gui-test.log").open("w") as log:
        process = subprocess.Popen(
            args, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
        )
        try:
            status = process.wait(timeout=45)
        finally:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        assert status == 0, (root / "gui-test.log").read_text()
    assert (project / "output/dilated.tif").is_file()
    print("Visible native Fiji GUI executed the MorphoLibJ plugin")
