"""Prepare a private native Fiji launch on an immutable plugin tree."""

import os
import shlex
import subprocess
from pathlib import Path


def command(profile, state, java, arguments, env):
    profile = Path(profile).resolve()
    state = Path(state).resolve()
    for directory in ["home", "config", "cache", "data", "tmp"]:
        (state / directory).mkdir(parents=True, exist_ok=True)
    # These flags select a different runtime or an external dependency search tree.
    unsupported = {
        "--java-home",
        "--ij-dir",
        "--ext",
        "--plugins",
        "--ij-jar",
        "--class-path",
        "--classpath",
        "-classpath",
        "--cp",
        "-cp",
        "--jar-path",
        "--jarpath",
        "-jarpath",
        "--full-classpath",
        "--debugger",
        "--retro",
    }
    if any(arg.split("=", 1)[0] in unsupported for arg in arguments):
        raise ValueError(
            "external Fiji runtime/plugin paths need an additional provider"
        )
    env = env.copy()
    for name in [
        "JAVA_TOOL_OPTIONS",
        "JDK_JAVA_OPTIONS",
        "_JAVA_OPTIONS",
        "CLASSPATH",
        "JYTHONPATH",
    ]:
        env.pop(name, None)
    env.update(
        HOME=str(state / "home"),
        XDG_CONFIG_HOME=str(state / "config"),
        XDG_CACHE_HOME=str(state / "cache"),
        XDG_DATA_HOME=str(state / "data"),
        JAVA_HOME=str(Path(java).resolve().parents[1]),
    )
    native = subprocess.run(
        [
            profile / "ImageJ-linux64",
            "--default-gc",
            "--allow-multiple",
            "--dry-run",
            *arguments,
        ],
        env=env,
        stdout=subprocess.PIPE,
        text=True,
        check=False,
    )
    if native.returncode:
        return None, env, native.stdout, native.returncode
    result = shlex.split(native.stdout)
    if not result or Path(result[0]).name != "java":
        return None, env, native.stdout, native.returncode
    result[0] = str(java)
    main = result.index("net.imagej.launcher.ClassLauncher")
    fixed = {
        "user.home": str(state / "home"),
        "java.util.prefs.userRoot": str(state / "config"),
        "java.io.tmpdir": str(state / "tmp"),
        "ij1.plugin.dirs": str(profile / "plugins"),
        "plugins.dir": str(profile),
        "imagej.dir": str(profile),
        "ij.dir": str(profile),
        "fiji.dir": str(profile),
    }
    result[:main] = [
        arg
        for arg in result[:main]
        if not any(arg.startswith("-D" + key + "=") for key in fixed)
    ]
    main = result.index("net.imagej.launcher.ClassLauncher")
    result[main:main] = ["-D" + key + "=" + value for key, value in fixed.items()]
    if "--dry-run" in arguments:
        return None, env, shlex.join(result) + "\n", 0
    return result, env, "", 0


def execute(profile, state, java, arguments, env):
    invocation, env, output, status = command(profile, state, java, arguments, env)
    if invocation is None:
        print(output, end="")
        raise SystemExit(status)
    os.execve(invocation[0], invocation, env)
