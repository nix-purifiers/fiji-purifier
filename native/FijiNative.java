/** Thin adapter to the original ImageJ updater's catalog, graph and installer. */
import java.io.File;
import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
import net.imagej.updater.*;
import net.imagej.updater.FileObject.Action;
import net.imagej.updater.util.StderrProgress;

public class FijiNative {
  static final Gson JSON = new GsonBuilder().setPrettyPrinting().create();
  static JsonObject request;
  static FilesCollection files;
  static File root;
  static final StderrProgress progress = new StderrProgress(80);

  static void select() {
    for (FileObject file : files) file.setNoAction();
    for (JsonElement element : request.getAsJsonObject("selection").getAsJsonArray("plugins")) {
      String name = element.getAsString();
      FileObject selected = files.get(name);
      if (selected == null || selected.isObsolete() || !selected.isUpdateablePlatform(files) ||
          !selected.setFirstValidAction(files, Action.UPDATE, Action.INSTALL)) {
        throw new IllegalArgumentException("No compatible native plugin: " + name);
      }
    }
    Iterable<Conflicts.Conflict> conflicts = new Conflicts(files).getConflicts(false);
    if (Conflicts.needsFeedback(conflicts)) throw new IllegalArgumentException("Unresolved native dependency conflict");
  }

  static void safePath(String value) {
    Path path = Paths.get(value);
    if (path.isAbsolute() || !path.normalize().toString().equals(value) ||
        value.contains("\\") || value.contains("\n") || value.contains("\r") ||
        value.contains("\u0000") || value.isEmpty() || value.startsWith("../")) {
      throw new IllegalArgumentException("Unsupported native artifact path: " + value);
    }
  }

  static List<String> replacements(String filename) throws Exception {
    String identity = FileObject.getFilename(filename, true);
    Path sdk = Paths.get(request.get("sdkRoot").getAsString());
    List<String> result = new ArrayList<>();
    for (String directory : Arrays.asList("jars", "plugins")) {
      try (java.util.stream.Stream<Path> paths = Files.walk(sdk.resolve(directory))) {
        paths.filter(Files::isRegularFile).forEach(path -> {
          String relative = sdk.relativize(path).toString();
          if (FileObject.getFilename(relative,true).equals(identity)) result.add(relative);
        });
      }
    }
    Collections.sort(result);
    return result;
  }

  static JsonArray closure() throws Exception {
    JsonArray result = new JsonArray();
    for (FileObject file : files.toInstallOrUpdate()) {
      safePath(file.filename);
      // Native/JNI library builds require a platform provider beyond JAR replay.
      if (!file.filename.endsWith(".jar") ||
          !(file.filename.startsWith("jars/") || file.filename.startsWith("plugins/"))) {
        throw new IllegalArgumentException("Native dependency needs an additional provider: " + file.filename);
      }
      JsonObject entry = new JsonObject();
      entry.addProperty("path", file.filename);
      entry.addProperty("url", files.getURL(file));
      entry.addProperty("checksum", file.current.checksum);
      entry.addProperty("timestamp", file.current.timestamp);
      entry.addProperty("site", file.updateSite);
      entry.add("replaces", JSON.toJsonTree(replacements(file.filename)));
      result.add(entry);
    }
    return result;
  }

  static JsonObject capture() throws Exception {
    List<UpdateSite> sites = new ArrayList<>();
    for (JsonElement element : request.getAsJsonObject("selection").getAsJsonArray("updateSites")) {
      JsonObject site = element.getAsJsonObject();
      UpdateSite nativeSite=new UpdateSite(site.get("name").getAsString(),site.get("url").getAsString(),null,null,null,null,0);
      nativeSite.setActive(true);
      sites.add(nativeSite);
    }
    files.replaceUpdateSites(sites);
    String warnings = files.downloadIndexAndChecksum(progress);
    if (!warnings.isEmpty()) throw new IllegalArgumentException("Native catalog failed: " + warnings);
    select();
    JsonObject response = new JsonObject();
    response.add("entries",closure());
    files.write();
    response.addProperty("catalog", Base64.getEncoder().encodeToString(Files.readAllBytes(root.toPath().resolve("db.xml.gz"))));
    return response;
  }

  static JsonObject replay() throws Exception {
    Files.write(root.toPath().resolve("db.xml.gz"),Base64.getDecoder().decode(request.get("catalog").getAsString()));
    files.replaceUpdateSites(Collections.emptyList());
    files.read();
    List<UpdateSite> sites = new ArrayList<>(files.getUpdateSites(false));
    JsonArray requestedSites = request.getAsJsonObject("selection").getAsJsonArray("updateSites");
    if (sites.size()!=requestedSites.size()) throw new IllegalArgumentException("Native update-site selection changed");
    for (int index=0; index<sites.size(); index++) {
      JsonObject expectedSite=requestedSites.get(index).getAsJsonObject();
      if (!sites.get(index).getName().equals(expectedSite.get("name").getAsString()) ||
          !sites.get(index).getURL().equals(expectedSite.get("url").getAsString())) {
        throw new IllegalArgumentException("Native update-site URL or precedence changed");
      }
    }
    new Checksummer(files,progress).updateFromLocal();
    select();
    JsonArray expected = request.getAsJsonArray("entries");
    JsonArray actual = closure();
    Map<String,JsonObject> byPath = new HashMap<>();
    for (JsonElement element : actual) byPath.put(element.getAsJsonObject().get("path").getAsString(),element.getAsJsonObject());
    if (actual.size()!=expected.size()) throw new IllegalArgumentException("Native dependency closure changed");
    for (JsonElement element : expected) {
      JsonObject entry=element.getAsJsonObject();
      JsonObject nativeEntry=byPath.get(entry.get("path").getAsString());
      if (nativeEntry==null) throw new IllegalArgumentException("Unexpected locked artifact");
      for (String key : Arrays.asList("url","checksum","timestamp","site","replaces")) {
        if (!nativeEntry.get(key).equals(entry.get(key))) throw new IllegalArgumentException("Native lock metadata changed: "+key);
      }
      files.getUpdateSite(entry.get("site").getAsString()).setURL(
        new File(request.get("archives").getAsString(),entry.get("site").getAsString()).toURI().toString());
    }
    Installer installer=new Installer(files,progress);
    installer.start();installer.moveUpdatedIntoPlace();files.write();
    for (JsonElement element:expected) if (!root.toPath().resolve(element.getAsJsonObject().get("path").getAsString()).toFile().isFile()) {
      throw new IllegalStateException("Native installer did not install selected artifact");
    }
    JsonObject response=new JsonObject();response.addProperty("installed",expected.size());return response;
  }

  public static void main(String[] args) throws Exception {
    request=JsonParser.parseString(Files.readString(Paths.get(args[0]))).getAsJsonObject();
    root=new File(request.get("root").getAsString());root.mkdirs();
    files=new FilesCollection(root);
    JsonObject response=request.get("action").getAsString().equals("capture") ? capture() : replay();
    Files.writeString(Paths.get(args[1]),JSON.toJson(response)+"\n");
  }
}
