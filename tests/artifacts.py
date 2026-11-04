"""Consume exported native TIFF images, external locks and exact release assets."""

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

cli = Path(sys.argv[1]).resolve() / "bin/fiji-purifier"
original = Path(sys.argv[2]).resolve() / "bin/fiji"
source = Path(__file__).resolve().parents[1]


def call(arguments, *, env, cwd):
    result = subprocess.run(
        arguments, check=True, env=env, cwd=cwd, text=True, capture_output=True
    )
    return result.stdout.strip()


with tempfile.TemporaryDirectory(prefix="fiji-artifacts-") as temporary:
    root = Path(temporary)
    project = root / "project"
    shutil.copytree(
        source / "examples/minimal",
        project,
        ignore=shutil.ignore_patterns(".fiji-purifier"),
    )
    env = os.environ.copy() | {
        "HOME": str(root / "home"),
        "XDG_DATA_HOME": str(root / "data"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "QT_QPA_PLATFORM": "offscreen",
    }
    for name in ["home", "data", "config", "cache"]:
        (root / name).mkdir()
    args = [str(cli), "--project", str(project)]
    build = Path(call([*args, "build"], env=env, cwd=root))
    assert (build / "dilated.tif").is_file()
    marker = root / "consumed.txt"
    consumer = root / "consumer.ijm"
    consumer.write_text(
        f"open({json.dumps(str(build / 'dilated.tif'))});\n"
        "getDimensions(w,h,c,z,t);\n"
        'if(w!=12 || h!=12 || z!=1) exit("Unexpected TIFF dimensions");\n'
        "getHistogram(values,counts,256);\n"
        'if(counts[255]!=25) exit("Unexpected dilation output");\n'
        f'File.saveString(""+counts[255],{json.dumps(str(marker))});\n'
    )
    call(
        [
            str(original),
            "-Duser.home=" + str(root / "consumer-home"),
            "-Djava.util.prefs.userRoot=" + str(root / "consumer-prefs"),
            "--",
            "--headless",
            "--allow-multiple",
            "--console",
            "-macro",
            str(consumer),
        ],
        env=env,
        cwd=root,
    )
    assert marker.read_text() == "25"
    release = Path(call([*args, "bundle"], env=env, cwd=root))
    archive = release / "fiji-project.tar.gz"
    with tarfile.open(archive) as tar:
        assert (
            tar.extractfile("./dilated.tif").read()
            == (build / "dilated.tif").read_bytes()
        )
    external = root / "external-lock.json"
    shutil.copyfile(project / "fiji-purifier.lock.json", external)
    replay = Path(call([*args, "--lock", str(external), "bundle"], env=env, cwd=root))
    assert (replay / archive.name).read_bytes() == archive.read_bytes()
    fake = root / "gh"
    fake.write_text(
        f"#!{sys.executable}\nimport json,os,sys\nfrom pathlib import Path\n"
        "Path(os.environ['UPLOAD_RECORD']).write_text(json.dumps(sys.argv[1:]))\n"
        "Path(os.environ['UPLOAD_BYTES']).write_bytes(Path(sys.argv[4]).read_bytes())\n"
    )
    fake.chmod(0o755)
    publish_env = env | {
        "FIJI_PURIFIER_GH": str(fake),
        "UPLOAD_RECORD": str(root / "upload.json"),
        "UPLOAD_BYTES": str(root / "upload.tar.gz"),
    }
    call([*args, "publish", "--tag", "proof"], env=publish_env, cwd=root)
    record = json.loads((root / "upload.json").read_text())
    assert record[:3] == ["release", "upload", "proof"] and record[3] == str(archive)
    assert (root / "upload.tar.gz").read_bytes() == archive.read_bytes()
print("native FIJI artifact consumers passed")
