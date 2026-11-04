{
  lib,
  runCommand,
  jdk11,
  python3,
  original,
  sources,
}:
let
  driver = lib.fileset.toSource {
    root = ../native;
    fileset = lib.fileset.unions [
      ../native/freeze_legacy.py
      ../native/java_patch.py
    ];
  };
in
runCommand "fiji-frozen-legacy-installers"
  {
    nativeBuildInputs = [
      jdk11
      python3
    ];
  }
  ''
    python ${driver}/freeze_legacy.py ${sources.legacySource}/ij/plugin patched
    mkdir -p "$out/classes"
    javac -proc:none -cp '${original}/fiji/jars/*' -d "$out/classes" patched/*.java
  ''
