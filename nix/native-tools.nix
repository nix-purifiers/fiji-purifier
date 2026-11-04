{
  lib,
  runCommand,
  jdk11,
  original,
  sources,
}:
let
  driver = lib.fileset.toSource {
    root = ../native;
    fileset = ../native/FijiNative.java;
  };
in
runCommand "fiji-native-lock-tools" { nativeBuildInputs = [ jdk11 ]; } ''
  mkdir -p "$out/classes"
  javac -proc:none -cp '${sources.updater}:${original}/fiji/jars/*' \
    -d "$out/classes" ${driver}/FijiNative.java
''
