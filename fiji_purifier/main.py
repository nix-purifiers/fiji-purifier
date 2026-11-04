"""FIJI's normal application workflow with a frozen native extension profile."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def public_url(url):
    if not isinstance(url, str):
        raise TypeError("Fiji update-site URLs must be strings")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError("FIJI addon repositories must use public HTTPS URLs")
    return url


def selection(project):
    value = json.loads((project / "fiji-purifier.json").read_text())
    if set(value) != {"plugins", "updateSites"}:
        raise ValueError("fiji-purifier.json needs plugins and updateSites lists")
    if (
        not isinstance(value["plugins"], list)
        or not isinstance(value["updateSites"], list)
        or not value["updateSites"]
    ):
        raise ValueError("invalid Fiji plugin/update-site selection")
    component = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+ -]*")
    for name in value["plugins"]:
        if (
            not isinstance(name, str)
            or not name.endswith(".jar")
            or not name.startswith(("jars/", "plugins/"))
            or not all(component.fullmatch(part) for part in name.split("/"))
        ):
            raise ValueError("select native JAR filenames from jars/ or plugins/")
    if len(set(value["plugins"])) != len(value["plugins"]):
        raise ValueError("duplicate native plugin selection")
    names = []
    for site in value["updateSites"]:
        if (
            not isinstance(site, dict)
            or set(site) != {"name", "url"}
            or not isinstance(site["name"], str)
            or not component.fullmatch(site["name"])
        ):
            raise ValueError("update sites need native name and public HTTPS URL")
        public_url(site["url"])
        if not site["url"].endswith("/"):
            raise ValueError("native update-site URLs must end in /")
        names.append(site["name"])
    if len(set(names)) != len(names):
        raise ValueError("duplicate native update-site name")
    return value


def project_path(explicit):
    if explicit:
        return Path(explicit).resolve()
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "fiji-purifier.json").exists() or (
            parent / "fiji-purifier.lock.json"
        ).exists():
            return parent
    return current


def validate(project, lock):
    data = json.loads(lock.read_text())
    if data.get("version") != 1 or data.get("purifier") != "fiji":
        raise ValueError("unsupported Fiji lock")
    if data.get("sdk") != os.environ["FIJI_PURIFIER_SDK"]:
        raise ValueError("Fiji SDK changed; run fiji-purifier lock --update")
    if data.get("selection") != selection(project):
        raise ValueError("extension selection changed; run fiji-purifier lock --update")
    return data


def realize(project, lock, target="environment", out_link=None):
    args = [
        "nix",
        "build",
        "--impure",
        "--file",
        os.environ["FIJI_PURIFIER_REALIZE"],
        "--argstr",
        "projectPath",
        str(project),
        "--argstr",
        "lockPath",
        str(lock),
        "--argstr",
        "target",
        target,
        "--json",
    ]
    args += ["--out-link", str(out_link)] if out_link else ["--no-link"]
    result = run(args, stdout=subprocess.PIPE, text=True)
    return Path(json.loads(result.stdout)[0]["outputs"]["out"])


def native_operation(root, requested):
    request = root / "request.json"
    response = root / "response.json"
    request.write_text(
        json.dumps(
            {
                "action": "capture",
                "selection": requested,
                "root": str(root / "native"),
                "sdkRoot": str(Path(os.environ["FIJI_PURIFIER_ORIGINAL"]) / "fiji"),
            }
        )
    )
    env = os.environ.copy()
    for name in ["JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "CLASSPATH"]:
        env.pop(name, None)
    home = root / "home"
    home.mkdir()
    run(
        [
            os.environ["FIJI_PURIFIER_JAVA"],
            "-Djava.awt.headless=true",
            "-Duser.home=" + str(home),
            "-Djava.util.prefs.userRoot=" + str(home / "prefs"),
            "-cp",
            os.environ["FIJI_PURIFIER_NATIVE_CP"],
            "FijiNative",
            str(request),
            str(response),
        ],
        env=env,
        stdout=sys.stderr,
    )
    return json.loads(response.read_text())


def prefetch(url):
    return json.loads(
        run(
            ["nix", "store", "prefetch-file", "--json", public_url(url)],
            stdout=subprocess.PIPE,
            text=True,
        ).stdout
    )


def capture(project, lock):
    requested = selection(project)
    with tempfile.TemporaryDirectory(prefix="fiji-purifier-") as temporary:
        root = Path(temporary)
        native = native_operation(root, requested)
        entries = []
        for entry in native["entries"]:
            fetched = prefetch(entry["url"])
            entries.append(entry | {"hash": fetched["hash"], "mirrors": []})
        data = {
            "version": 1,
            "purifier": "fiji",
            "sdk": os.environ["FIJI_PURIFIER_SDK"],
            "selection": requested,
            "entries": entries,
            "native": {"catalog": native["catalog"]},
        }
        candidate = root / "fiji-purifier.lock.json"
        candidate.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        realize(project, candidate)
        lock.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", dir=lock.parent, delete=False
        ) as output:
            output.write(candidate.read_text())
            pending = Path(output.name)
        try:
            os.replace(pending, lock)
        finally:
            pending.unlink(missing_ok=True)


def native_exec(project, lock, arguments, command="fiji"):
    if not lock.exists():
        print(
            "warning: no Fiji purifier lock; using ordinary, impure plugin resolution",
            file=sys.stderr,
        )
        executable = Path(os.environ["FIJI_PURIFIER_ORIGINAL"]) / "bin/fiji"
        os.execve(executable, [str(executable), *arguments], os.environ.copy())
    validate(project, lock)
    state = project / ".fiji-purifier"
    state.mkdir(exist_ok=True)
    environment = realize(project, lock, out_link=state / "environment")
    sys.path.insert(0, os.environ["FIJI_PURIFIER_NATIVE"])
    from runtime import execute

    execute(
        environment,
        state,
        os.environ["FIJI_PURIFIER_JAVA"],
        arguments,
        os.environ.copy(),
    )


def main():
    if os.environ.get("FIJI_PURIFIER_COMMAND") not in {None, "fiji-purifier"}:
        project = project_path(os.environ.get("FIJI_PURIFIER_PROJECT"))
        lock = Path(
            os.environ.get("FIJI_PURIFIER_LOCK", project / "fiji-purifier.lock.json")
        ).resolve()
        native_exec(project, lock, sys.argv[1:], os.environ["FIJI_PURIFIER_COMMAND"])
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("--project")
    parser.add_argument("--lock")
    sub = parser.add_subparsers(dest="action", required=True)
    lock_parser = sub.add_parser("lock")
    lock_parser.add_argument("--update", action="store_true")
    sub.add_parser("prefetch")
    for name in ["build", "bundle"]:
        sub.add_parser(name)
    publish = sub.add_parser("publish")
    publish.add_argument("--tag", required=True)
    execute = sub.add_parser("exec")
    execute.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    project = project_path(args.project or os.environ.get("FIJI_PURIFIER_PROJECT"))
    lock = Path(
        args.lock
        or os.environ.get("FIJI_PURIFIER_LOCK", project / "fiji-purifier.lock.json")
    ).resolve()
    if args.action == "lock" and args.update:
        capture(project, lock)
        return
    if args.action == "exec":
        arguments = (
            args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
        )
        native_exec(project, lock, arguments)
        return
    validate(project, lock)
    if args.action == "lock":
        realize(project, lock)
    elif args.action == "prefetch":
        print(realize(project, lock))
    elif args.action in {"build", "bundle"}:
        print(
            realize(project, lock, "project" if args.action == "build" else "release")
        )
    elif args.action == "publish":
        release = realize(project, lock, "release")
        run(
            [
                os.environ.get("FIJI_PURIFIER_GH", "gh"),
                "release",
                "upload",
                args.tag,
                str(release / "fiji-project.tar.gz"),
                "--clobber",
            ]
        )


if __name__ == "__main__":
    try:
        main()
    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"fiji-purifier: {error}", file=sys.stderr)
        sys.exit(1)
