{
  lib,
  purifier,
  runCommand,
  python3,
  jdk11,
  environment,
  readLock,
  gnutar,
  gzip,
}:
{
  src,
  lockFile ? src + "/fiji-purifier.lock.json",
  script ? "build.ijm",
  fetchers ? { },
  doCheck ? false,
  checkCommand ? "",
  resourceRoots ? { },
  resourceDependencies ? [ ],
}:
let
  lock = readLock { inherit src lockFile; };
  profile = environment { inherit lock fetchers; };
  driver = lib.fileset.toSource {
    root = ../native;
    fileset = lib.fileset.unions [
      ../native/build_project.py
      ../native/runtime.py
    ];
  };
  projectSource = lib.cleanSourceWith {
    inherit src;
    filter =
      path: type:
      !(builtins.elem (baseNameOf path) [
        ".git"
        ".fiji-purifier"
        "__pycache__"
        "result"
        "output"
      ]);
  };
  builtProject = runCommand "fiji-project" { } ''
    export FIJI_PURIFIER_ENVIRONMENT=${profile} FIJI_PURIFIER_JAVA=${jdk11}/bin/java
    export FIJI_PURIFIER_OUTPUT="$out"
    mkdir -p "$out"
    cp -r ${projectSource} project
    chmod -R u+w project
    cd project
    export FIJI_PURIFIER_SCRIPT="$PWD/"${lib.escapeShellArg script}
    ${python3}/bin/python ${driver}/build_project.py
    ${lib.optionalString doCheck checkCommand}
  '';
  projections = lib.optionalAttrs (resourceRoots != { }) (
    purifier.resourceProjections {
      producer = builtProject;
      roots = resourceRoots;
      dependencies = resourceDependencies;
      inherit runCommand python3;
    }
  );
  project = builtProject // {
    inherit projections;
  };
  release =
    runCommand "fiji-project-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        mkdir -p "$out"
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -cf - -C ${project} . | gzip -n > "$out/fiji-project.tar.gz"
      '';
in
{
  packages = {
    default = project;
    inherit project;
    environment = profile;
  };
  tests = project;
  inherit release projections;
  fetches = lock.entries;
}
