{
  lib,
  runCommand,
  writeText,
  fetchurl,
  fetchgit,
  python3,
  jdk11,
  original,
  frozenSdk,
  sources,
  legacyClasses,
  nativeTools,
  purifier,
  sdk,
}:
{
  lock,
  fetchers ? { },
}:
let
  checked = purifier.checkLock lock;
  archives = purifier.tree (
    {
      name = "fiji-native-artifact-archives";
      entries = map (entry: {
        path = entry.site + "/" + entry.path + "-" + toString entry.timestamp;
        inherit (entry) url hash mirrors;
      }) checked.entries;
      inherit
        runCommand
        writeText
        fetchurl
        fetchgit
        python3
        ;
    }
    // fetchers
  );
  request = writeText "fiji-native-replay.json" (
    builtins.toJSON {
      action = "replay";
      inherit archives;
      sdkRoot = "${original}/fiji";
      inherit (checked.data) selection entries;
      catalog = checked.data.native.catalog;
    }
  );
  driver = lib.fileset.toSource {
    root = ../native;
    fileset = lib.fileset.unions [
      ../native/install_request.py
      ../native/overlay_plugins.py
      ../native/patch_jar.py
    ];
  };
in
assert lib.assertMsg (checked.data.sdk == sdk) "Fiji SDK changed; run fiji-purifier lock --update";
runCommand "fiji-locked-plugin-environment" { nativeBuildInputs = [ python3 ]; } ''
  export HOME="$TMPDIR/home" XDG_CONFIG_HOME="$TMPDIR/config" XDG_CACHE_HOME="$TMPDIR/cache"
  mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME"
  python ${driver}/install_request.py ${request} "$TMPDIR/installed" "$TMPDIR/request.json"
  ${jdk11}/bin/java -Djava.awt.headless=true -Duser.home="$HOME" \
    -Djava.util.prefs.userRoot="$XDG_CONFIG_HOME" \
    -cp '${nativeTools}/classes:${sources.updater}:${original}/fiji/jars/*' \
    FijiNative "$TMPDIR/request.json" "$TMPDIR/response.json" > "$TMPDIR/native.log"
  cp -rs ${frozenSdk} "$out"
  find "$out" -type d -exec chmod u+w {} +
  cp --remove-destination ${frozenSdk}/ImageJ-linux64 "$out/ImageJ-linux64"
  python ${driver}/overlay_plugins.py ${request} "$TMPDIR/installed" "$out"
  test -f "$out/jars/ij-1.54p.jar" || { echo 'Fiji core version needs an additional provider' >&2; exit 1; }
  python ${driver}/patch_jar.py "$out/jars/ij-1.54p.jar" \
    ${legacyClasses}/classes ij/plugin "$TMPDIR/legacy.jar"
  cp --remove-destination "$TMPDIR/legacy.jar" "$out/jars/ij-1.54p.jar"
  ln -s ${writeText "fiji-lock.json" (builtins.toJSON checked.data)} "$out/lock.json"
''
