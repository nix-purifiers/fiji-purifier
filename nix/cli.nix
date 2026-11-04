{
  lib,
  runCommand,
  writeText,
  makeWrapper,
  python3,
  original,
  sdk,
  jdk11,
  sources,
  nativeTools,
  nix,
  gh,
  cacert,
  nixpkgsSrc,
  purifierSrc,
}:
let
  integration = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      (lib.fileset.fileFilter (file: file.hasExt "py") ../fiji_purifier)
      (lib.fileset.fileFilter (file: file.hasExt "py" || file.hasExt "java") ../native)
      (lib.fileset.fileFilter (file: file.hasExt "nix") ./.)
    ];
  };
  bootstrap = writeText "fiji-purifier-main.py" "import os,runpy,sys; sys.path.insert(0, ${builtins.toJSON integration}); sys.argv[0]=os.environ['FIJI_PURIFIER_COMMAND']; runpy.run_module('fiji_purifier.main',run_name='__main__')";
  realize = writeText "fiji-purifier-realize.nix" ''
    { lockPath, projectPath, target ? "environment" }:
    let
      pkgs = import (builtins.storePath "${nixpkgsSrc}") {};
      scope = import ${integration}/nix/scope.nix {
        inherit pkgs;
        nixpkgsSrc = builtins.storePath "${nixpkgsSrc}";
        purifierSrc = builtins.storePath "${purifierSrc}";
      };
      lockFile = builtins.toPath lockPath;
      src = if target == "environment" then builtins.toPath projectPath else builtins.path {
        path = builtins.toPath projectPath;
        name = "fiji-project";
        filter = path: type: !(builtins.elem (baseNameOf path) [ ".git" ".fiji-purifier" "__pycache__" "result" "output" ]);
      };
      build = scope.buildFijiProject { inherit src lockFile; };
    in if target == "environment" then scope.environment { lock = scope.readLock { inherit src lockFile; }; }
       else if target == "project" then build.packages.project
       else if target == "release" then build.release
       else throw "Unknown FIJI purifier target"
  '';
in
runCommand "fiji-purifier" { nativeBuildInputs = [ makeWrapper ]; } ''
  mkdir -p "$out/bin"
  for name in fiji-purifier fiji; do
    makeWrapper ${python3}/bin/python "$out/bin/$name" \
      --add-flags ${bootstrap} \
      --set FIJI_PURIFIER_COMMAND "$name" \
      --set FIJI_PURIFIER_NATIVE ${integration}/native \
      --set FIJI_PURIFIER_ORIGINAL ${original} \
      --set FIJI_PURIFIER_JAVA ${jdk11}/bin/java \
      --set FIJI_PURIFIER_NATIVE_CP '${nativeTools}/classes:${sources.updater}:${original}/fiji/jars/*' \
      --set FIJI_PURIFIER_SDK ${sdk} \
      --set FIJI_PURIFIER_REALIZE ${realize} \
      --set-default FIJI_PURIFIER_GH ${gh}/bin/gh \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default NIX_SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --prefix PATH : ${
        lib.makeBinPath [
          nix
          gh
        ]
      }
  done
''
