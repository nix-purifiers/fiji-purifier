"""Fresh native capture, cold replay and atomic failure against the public catalog."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

cli = Path(sys.argv[1]).resolve() / "bin/fiji-purifier"
source = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="fiji-capture-") as temporary:
    project = Path(temporary)
    shutil.copyfile(
        source / "examples/minimal/fiji-purifier.json",
        project / "fiji-purifier.json",
    )
    env = os.environ.copy() | {"FIJI_PURIFIER_PROJECT": str(project)}
    subprocess.run([str(cli), "lock", "--update"], check=True, env=env, cwd=project)
    lock = project / "fiji-purifier.lock.json"
    before = lock.read_bytes()
    subprocess.run([str(cli), "lock"], check=True, env=env, cwd=project)
    subprocess.run([str(cli), "prefetch"], check=True, env=env, cwd=project)
    assert lock.read_bytes() == before
    selection_file = project / "fiji-purifier.json"
    selection = json.loads(selection_file.read_text())
    selection["plugins"].append("plugins/purifier_missing_plugin_probe.jar")
    selection_file.write_text(json.dumps(selection))
    failed = subprocess.run(
        [str(cli), "lock", "--update"], check=False, env=env, cwd=project
    )
    assert failed.returncode != 0 and lock.read_bytes() == before
    selection_file.write_text(json.dumps(json.loads(before)["selection"]))
    damaged = json.loads(before)
    damaged["entries"][0]["checksum"] = "0" * 40
    lock.write_text(json.dumps(damaged))
    failed = subprocess.run([str(cli), "prefetch"], check=False, env=env, cwd=project)
    assert failed.returncode != 0
    lock.write_bytes(before)
    minimal = project / "minimal-sites"
    minimal.mkdir()
    minimal_selection = json.loads(before)["selection"]
    minimal_selection["updateSites"] = [
        site
        for site in minimal_selection["updateSites"]
        if site["name"] in {"Java-8", "IJPB-plugins"}
    ]
    (minimal / "fiji-purifier.json").write_text(json.dumps(minimal_selection))
    minimal_env = env | {"FIJI_PURIFIER_PROJECT": str(minimal)}
    subprocess.run(
        [str(cli), "lock", "--update"], check=True, env=minimal_env, cwd=minimal
    )
    subprocess.run([str(cli), "prefetch"], check=True, env=minimal_env, cwd=minimal)
    empty = project / "empty"
    empty.mkdir()
    (empty / "fiji-purifier.json").write_text(
        json.dumps({"plugins": [], "updateSites": selection["updateSites"]})
    )
    empty_env = env | {"FIJI_PURIFIER_PROJECT": str(empty)}
    subprocess.run([str(cli), "lock", "--update"], check=True, env=empty_env, cwd=empty)
    macro = empty / "probe.ijm"
    macro.write_text(
        "print(eval(\"script\", \"var present=false; try {java.lang.Class.forName('inra.ijpb.morphology.Morphology',false,Packages.ij.IJ.getClassLoader());present=true;}catch(e){} if(present) java.lang.System.exit(1); 'empty-native-sdk-ok';\"));\n"
    )
    result = subprocess.run(
        [str(cli), "exec", "--", "--headless", "--console", "-macro", str(macro)],
        check=True,
        env=empty_env,
        cwd=empty,
        capture_output=True,
        text=True,
    )
    assert "empty-native-sdk-ok" in result.stdout


print("native fiji capture and atomic failure passed")
