// Fails (exit 1) if docs/openapi.json or lib/api/schema.d.ts is stale.
//   (a) fresh export of backend.main:app (same serialization as backend/export_openapi.py) == docs/openapi.json
//   (b) openapi-typescript(docs/openapi.json) == lib/api/schema.d.ts
// Env overrides (used to demonstrate failure without touching committed files):
//   API_CHECK_OPENAPI  path of the committed openapi.json   (default ../docs/openapi.json)
//   API_CHECK_SCHEMA   path of the committed schema.d.ts    (default lib/api/schema.d.ts)
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, "..");
const root = path.resolve(frontend, "..");
const openapiPath = path.resolve(process.env.API_CHECK_OPENAPI ?? path.join(root, "docs", "openapi.json"));
const schemaPath = path.resolve(process.env.API_CHECK_SCHEMA ?? path.join(frontend, "lib", "api", "schema.d.ts"));
const python = path.join(root, ".venv", "bin", "python");
const tmp = mkdtempSync(path.join(tmpdir(), "check-api-"));
const problems = [];

try {
  // (a) must match backend/export_openapi.py's serialization exactly.
  const freshJson = path.join(tmp, "openapi.json");
  const code =
    "import json,sys\nfrom backend.main import app\n" +
    "open(sys.argv[1],'w').write(json.dumps(app.openapi(), indent=2, sort_keys=True) + '\\n')";
  execFileSync(python, ["-c", code, freshJson], { cwd: root, stdio: ["ignore", "ignore", "inherit"] });
  if (!readFileSync(freshJson).equals(readFileSync(openapiPath))) {
    problems.push(`${path.relative(root, openapiPath)} is stale (differs from the live backend OpenAPI)`);
  }

  // (b) generated types from the committed openapi.json.
  const freshTs = path.join(tmp, "schema.d.ts");
  let generated = true;
  try {
    execFileSync(path.join(frontend, "node_modules", ".bin", "openapi-typescript"), [openapiPath, "-o", freshTs], {
      cwd: frontend,
      stdio: "ignore",
    });
  } catch {
    generated = false;
    problems.push(`openapi-typescript could not process ${path.relative(root, openapiPath)} (invalid OpenAPI)`);
  }
  if (generated && !readFileSync(freshTs).equals(readFileSync(schemaPath))) {
    problems.push(`${path.relative(root, schemaPath)} is stale (differs from openapi-typescript output of ${path.relative(root, openapiPath)})`);
  }
} finally {
  rmSync(tmp, { recursive: true, force: true });
}

if (problems.length) {
  for (const p of problems) console.error(`check:api FAILED: ${p}`);
  console.error("Run `make ui-gen` to regenerate.");
  process.exit(1);
}
console.log("check:api OK: docs/openapi.json and lib/api/schema.d.ts are up to date");
