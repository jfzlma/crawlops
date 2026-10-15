// Validate in an empty directory: an existing node_modules can mask missing peers.
import { mkdtempSync, copyFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const source = fileURLToPath(new URL("../", import.meta.url));
const directory = mkdtempSync(join(tmpdir(), "crawlops-lock-"));
try {
  for (const name of ["package.json", "package-lock.json"]) {
    copyFileSync(join(source, name), join(directory, name));
  }
  for (const cpu of ["arm64", "x64"]) {
    const result = spawnSync("npm", ["ci", "--dry-run", "--ignore-scripts", "--no-audit", "--no-fund", "--os=linux", `--cpu=${cpu}`], {
      cwd: directory, encoding: "utf8", env: process.env,
    });
    if (result.status !== 0 || result.error) {
      process.stderr.write(result.stdout || "");
      process.stderr.write(result.stderr || String(result.error || ""));
      process.exitCode = result.status || 1;
      break;
    }
    console.log(`Clean Linux ${cpu} lockfile validation passed.`);
  }
} finally {
  rmSync(directory, { recursive: true, force: true });
}
