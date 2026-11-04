"""Run native image edits, preferences, guarded managers, HTTP and fallback."""

import hashlib
import http.server
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

cli = Path(sys.argv[1]).resolve() / "bin"
original = Path(sys.argv[2]).resolve() / "bin/fiji"
source = Path(__file__).resolve().parents[1]


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"project networking works")

    def log_message(self, *args):
        pass


with tempfile.TemporaryDirectory(prefix="fiji-native-") as temporary:
    root = Path(temporary)
    project = root / "project"
    shutil.copytree(
        source / "examples/minimal",
        project,
        ignore=shutil.ignore_patterns(".fiji-purifier", "output"),
    )
    env = os.environ.copy() | {"FIJI_PURIFIER_PROJECT": str(project)}
    for name in [
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "WAYLAND_SOCKET",
        "DBUS_SESSION_BUS_ADDRESS",
    ]:
        env.pop(name, None)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    script = project / "build.ijm"
    script_source = script.read_text()
    dry = subprocess.run(
        [cli / "fiji", "--headless", "--dry-run"],
        env=env,
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
    )
    java = Path(shlex.split(dry.stdout)[0]).resolve()
    profile = (project / ".fiji-purifier/environment").resolve()
    classes = root / "ambient-classes"
    classes.mkdir()
    ambient = root / "AmbientPlugin.java"
    ambient.write_text(
        "public class AmbientPlugin implements ij.plugin.PlugIn { public void run(String arg) {} }\n"
    )
    subprocess.run(
        [
            java.parent / "javac",
            "-proc:none",
            "-cp",
            str(profile / "jars/ij-1.54p.jar"),
            "-d",
            classes,
            ambient,
        ],
        check=True,
    )
    poison = project / ".fiji-purifier/home/.plugins"
    poison.mkdir()
    subprocess.run(
        [java.parent / "jar", "-cf", poison / "ambient.jar", "-C", classes, "."],
        check=True,
    )
    control = root / "control.ijm"
    control.write_text(
        "print(eval(\"script\", \"java.lang.Class.forName('AmbientPlugin',false,Packages.ij.IJ.getClassLoader()); 'ambientcontrol';\"));\n"
    )
    result = subprocess.run(
        [
            original,
            "-Duser.home=" + str(poison.parent),
            "-Djava.util.prefs.userRoot=" + str(root / "control-prefs"),
            "--",
            "--headless",
            "--allow-multiple",
            "--console",
            "-macro",
            control,
        ],
        env=env,
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "ambientcontrol" in result.stdout, result.stdout + result.stderr
    javascript = """
var IJ=Packages.ij.IJ;
var Prefs=Packages.ij.Prefs;
try {
 var ambient=false;
 try {java.lang.Class.forName('AmbientPlugin',false,IJ.getClassLoader());ambient=true;}catch(e){}
 if(ambient)throw 'mutable home plugin was loaded';
 var cls=java.lang.Class.forName('inra.ijpb.morphology.Morphology',false,IJ.getClassLoader());
 var location=cls.getProtectionDomain().getCodeSource().getLocation().toURI();
 var code=new java.io.File(location);
 if(!code.getCanonicalPath().startsWith('/nix/store/') || code.canWrite()) throw 'mutable plugin code';
 var legacy=new Packages.ij.plugin.PluginInstaller();
 var locked=false;
 try { legacy.install('http://127.0.0.1:1/unlocked.jar'); } catch(e) {locked=(''+e).indexOf('locked')>=0;}
 if(!locked) throw 'legacy importer not frozen';
 locked=false;
 try {new Packages.ij.plugin.ImageJ_Updater().run('');} catch(e) {locked=(''+e).indexOf('locked')>=0;}
 if(!locked)throw 'legacy updater not frozen';
 var state=new java.io.File(java.lang.System.getProperty('user.home'),'updater-probe');
 state.mkdirs();
 var files=new Packages.net.imagej.updater.FilesCollection(state);
 locked=false;
 try {new Packages.net.imagej.updater.Installer(files,new Packages.net.imagej.updater.util.StderrProgress()).start();}
 catch(e){locked=(''+e).indexOf('locked')>=0;}
 if(!locked)throw 'native updater not frozen';
 if(''+Packages.net.imagej.updater.UpToDate.check(state)!='UPDATES_MANAGED_DIFFERENTLY')throw 'startup update check not frozen';
 if(Packages.net.imagej.launcher.RemoteUpdater.runRemote(new java.lang.RuntimeException('probe')))throw 'remote bootstrap enabled';
 var input=new java.net.URL('__TEST_URL__').openStream();
 var scanner=new java.util.Scanner(input,'UTF-8').useDelimiter('\\\\A');
 if(scanner.next()!='project networking works')throw 'project networking blocked';
 scanner.close();
 var counter=parseInt(Prefs.get('purifier.counter','0'))+1;
 Prefs.set('purifier.counter',''+counter);
 Prefs.savePreferences();
 ''+counter;
} catch(e) {java.lang.System.err.println(e);java.lang.System.exit(1);}
""".replace("__TEST_URL__", f"http://127.0.0.1:{server.server_port}/")
    appended = '\ncounter=eval("script", ' + json.dumps(javascript) + ");\n"
    appended += 'File.saveString(counter,getArgument()+"/counter.txt");\n'
    lock = project / "fiji-purifier.lock.json"
    before = lock.read_bytes()
    hashes = []
    try:
        for counter, length in enumerate([3, 4, 3], 1):
            script.write_text(
                script_source.replace("length = 3;", f"length = {length};") + appended
            )
            result = subprocess.run(
                [
                    cli / "fiji",
                    "--headless",
                    "--console",
                    "-macro",
                    script,
                    project / "output",
                ],
                env=env,
                cwd=project,
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            assert (project / "output/counter.txt").read_text() == str(counter)
            hashes.append(
                hashlib.sha256(
                    (project / "output/dilated.tif").read_bytes()
                ).hexdigest()
            )
            assert lock.read_bytes() == before
    finally:
        server.shutdown()
        server.server_close()
    assert hashes[0] != hashes[1] and hashes[0] == hashes[2]
    assert (
        (project / ".fiji-purifier/environment").resolve().is_relative_to("/nix/store")
    )
    selection = project / "fiji-purifier.json"
    value = json.loads(selection.read_text())
    value["plugins"] = []
    selection.write_text(json.dumps(value))
    rejected = subprocess.run(
        [cli / "fiji", "--help"], env=env, capture_output=True, text=True, check=False
    )
    assert rejected.returncode and "selection changed" in rejected.stderr
    lock.unlink()
    logging = project / "logging.properties"
    logging.write_text(".level=OFF\n")
    exit_macro = project / "exit.ijm"
    exit_macro.write_text(
        "eval(\"script\", \"java.lang.System.out.println('native output'); java.lang.System.err.println('native error'); java.lang.System.exit(7);\");\n"
    )
    args = [
        "-Duser.home=" + str(root / "fallback-home"),
        "-Djava.util.prefs.userRoot=" + str(root / "fallback-prefs"),
        "-Djava.util.logging.config.file=" + str(logging),
        "--",
        "--headless",
        "--allow-multiple",
        "--console",
        "-macro",
        str(exit_macro),
    ]
    for arguments in [["--help"], args]:
        expected = subprocess.run(
            [original, *arguments],
            env=env,
            cwd=project,
            capture_output=True,
            check=False,
        )
        actual = subprocess.run(
            [cli / "fiji", *arguments],
            env=env,
            cwd=project,
            capture_output=True,
            check=False,
        )
        assert actual.returncode == expected.returncode
        assert actual.stdout == expected.stdout
        assert (
            actual.stderr
            == b"warning: no Fiji purifier lock; using ordinary, impure plugin resolution\n"
            + expected.stderr
        )
        if arguments == args:
            assert actual.returncode == 7
print(
    "Fiji native source, preferences, immutable managers, networking and fallback passed"
)
