import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../.next");
const manifestRoot = path.join(appRoot, "server/app");
const staticRoot = path.join(appRoot, "static/chunks");
const vaultModulePattern = /[\\/]lib[\\/]vault-manager\.tsx$/;
const vaultOnlyText = [
  "Temporary short link",
  "Temporary text share",
  "Temporary file share",
  "/api/vault/short-links",
  "/api/vault/pastes",
  "/api/vault/files",
];

async function filesUnder(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(
    entries.map(async (entry) => {
      const fullPath = path.join(directory, entry.name);
      return entry.isDirectory() ? filesUnder(fullPath) : [fullPath];
    }),
  );
  return nested.flat();
}

function parseManifest(source, file) {
  const match = source.match(/globalThis\.__RSC_MANIFEST\[(.+?)\]=(\{.*\});?$/);
  assert.ok(match, `Could not parse client reference manifest: ${file}`);
  return { route: JSON.parse(match[1]), manifest: JSON.parse(match[2]) };
}

const manifestFiles = (await filesUnder(manifestRoot)).filter((file) =>
  file.endsWith("client-reference-manifest.js"),
);
const manifests = await Promise.all(
  manifestFiles.map(async (file) =>
    parseManifest(await readFile(file, "utf8"), file),
  ),
);
const vaultRoute = manifests.find(({ route }) => route === "/vault/page");
assert.ok(vaultRoute, "The Vault route client manifest is missing");

const vaultEntry = Object.entries(vaultRoute.manifest.clientModules).find(
  ([modulePath]) => vaultModulePattern.test(modulePath),
);
assert.ok(vaultEntry, "VaultManager is missing from the Vault route manifest");
const vaultChunks = vaultEntry[1].chunks
  .filter((chunk) => chunk.endsWith(".js"))
  .map((chunk) => chunk.replaceAll("\\", "/"));
assert.ok(vaultChunks.some((chunk) => chunk.startsWith("static/chunks/app/vault/")),
  "VaultManager must live in the Vault route's own JavaScript chunk");

for (const { route, manifest } of manifests) {
  if (route === "/vault/page") continue;
  const references = Object.values(manifest.clientModules).flatMap((module) =>
    module.chunks.map((chunk) => chunk.replaceAll("\\", "/")),
  );
  assert.ok(
    !references.some((chunk) => vaultChunks.includes(chunk)),
    `A non-Vault route references the restricted Vault chunk: ${route}`,
  );
}

const allChunks = (await filesUnder(staticRoot)).filter((file) => file.endsWith(".js"));
for (const file of allChunks) {
  const relativePath = path.relative(appRoot, file).replaceAll("\\", "/");
  if (vaultChunks.includes(relativePath)) continue;
  const source = await readFile(file, "utf8");
  for (const restrictedText of vaultOnlyText) {
    assert.ok(
      !source.includes(restrictedText),
      `Vault UI text was found in a non-Vault client bundle: ${relativePath}`,
    );
  }
}

console.log(`Vault bundle isolation passed across ${manifests.length} route manifests.`);
