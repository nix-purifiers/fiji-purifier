{ lib }:
{
  src,
  lockFile ? src + "/fiji-purifier.lock.json",
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  entries = data.entries or [ ];
  component =
    value: builtins.isString value && builtins.match "[A-Za-z0-9][A-Za-z0-9_.+ -]*" value != null;
  path = value: builtins.isString value && builtins.all component (lib.splitString "/" value);
  jar =
    value:
    path value
    && lib.hasSuffix ".jar" value
    && (lib.hasPrefix "jars/" value || lib.hasPrefix "plugins/" value);
  selection =
    if builtins.pathExists (src + "/fiji-purifier.json") then
      builtins.fromJSON (builtins.readFile (src + "/fiji-purifier.json"))
    else
      null;
  valid =
    (data.version or null) == 1
    && (data.purifier or null) == "fiji"
    && builtins.isString (data.sdk or null)
    && builtins.isAttrs (data.selection or null)
    && data.selection == selection
    && builtins.isList (data.selection.plugins or null)
    && builtins.all jar data.selection.plugins
    && builtins.length (lib.unique data.selection.plugins) == builtins.length data.selection.plugins
    && builtins.isList (data.selection.updateSites or null)
    && data.selection.updateSites != [ ]
    && builtins.all (
      site:
      builtins.isAttrs site
      && component (site.name or null)
      && builtins.isString (site.url or null)
      && lib.hasPrefix "https://" site.url
    ) data.selection.updateSites
    && builtins.isString (data.native.catalog or null)
    && data.native.catalog != ""
    && builtins.isList entries
    && builtins.all (
      entry:
      builtins.isAttrs entry
      && jar (entry.path or null)
      && component (entry.site or null)
      && builtins.elem entry.site (map (site: site.name) data.selection.updateSites)
      && builtins.isString (entry.url or null)
      && lib.hasPrefix "https://" entry.url
      && builtins.isList (entry.mirrors or null)
      && builtins.all builtins.isString entry.mirrors
      && builtins.isString (entry.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" entry.hash != null
      && builtins.isString (entry.checksum or null)
      && builtins.match "[0-9a-f]{40}" entry.checksum != null
      && builtins.isInt (entry.timestamp or null)
      && entry.timestamp > 0
      && builtins.isList (entry.replaces or null)
      && builtins.all jar entry.replaces
    ) entries
    && builtins.length (lib.unique (map (entry: entry.path) entries)) == builtins.length entries;
in
{
  purifier = "fiji";
  inherit data entries;
  problems = lib.optional (
    !valid
  ) "Fiji lock is missing, malformed, or stale; run fiji-purifier lock --update";
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
}
