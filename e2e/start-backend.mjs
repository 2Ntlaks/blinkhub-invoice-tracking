// Starts the real backend for E2E on a throwaway SQLite file, freshly reset to the case-study seed,
// so every run starts from exactly the same data. Used by playwright.config.ts (webServer).
import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const backend = join(dirname(fileURLToPath(import.meta.url)), "..", "backend");
const py = [join(backend, ".venv", "Scripts", "python.exe"), join(backend, ".venv", "bin", "python")].find(existsSync);
if (!py) {
  console.error("backend/.venv not found; set up the backend first (see README.md)");
  process.exit(1);
}

const env = { ...process.env, DATABASE_URL: "sqlite:///./e2e.db", SEED_ON_STARTUP: "true" };
const reset = spawnSync(py, ["-m", "app.seed", "--reset"], { cwd: backend, env, stdio: "inherit" });
if (reset.status !== 0) process.exit(reset.status ?? 1);

const server = spawn(py, ["-m", "uvicorn", "app.main:app", "--port", "8000"], { cwd: backend, env, stdio: "inherit" });
const stop = () => server.kill();
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
server.on("exit", (code) => process.exit(code ?? 0));
