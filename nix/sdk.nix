{
  lib,
  runCommand,
  jdk11,
  python3,
  original,
  sources,
  legacyClasses,
}:
let
  driver = lib.fileset.toSource {
    root = ../native;
    fileset = lib.fileset.unions [
      ../native/freeze_updater.py
      ../native/patch_jar.py
      ../native/java_patch.py
    ];
  };
in
runCommand "fiji-frozen-update-manager"
  {
    nativeBuildInputs = [
      jdk11
      python3
    ];
  }
  ''
    python ${driver}/freeze_updater.py \
      ${sources.updaterSource}/src/main/java/net/imagej/updater \
      patched ${sources.launcherSource}/src/main/java/net/imagej/launcher
    mkdir classes
    javac -proc:none -cp '${sources.updater}:${original}/fiji/jars/*' -d classes patched/*.java
    python ${driver}/patch_jar.py ${sources.updater} classes \
      net/imagej/updater updater.jar
    python ${driver}/patch_jar.py ${original}/fiji/jars/imagej-launcher-6.0.2.jar classes \
      net/imagej/launcher launcher.jar
    cp -rs ${original}/fiji "$out"
    find "$out" -type d -exec chmod u+w {} +
    cp --remove-destination ${original}/fiji/ImageJ-linux64 "$out/ImageJ-linux64"
    cp updater.jar "$out/jars/imagej-updater-1.1.2.jar"
    cp --remove-destination launcher.jar "$out/jars/imagej-launcher-6.0.2.jar"
    python ${driver}/patch_jar.py ${original}/fiji/jars/ij-1.54p.jar \
      ${legacyClasses}/classes ij/plugin legacy.jar
    cp --remove-destination legacy.jar "$out/jars/ij-1.54p.jar"
  ''
