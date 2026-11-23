#!/usr/bin/env bash
# Runs the Playwright E2E suite with raw video recording enabled (E2E_VIDEO=1),
# copies each untouched .webm recording into docs/verification/raw/, converts
# each to a straight H.264 .mp4 and a full-length preview .gif in
# docs/verification/, and writes docs/verification/results.json with SHA-256
# checksums from Playwright's JSON reporter.
#
# Safe to re-run. Works in Git Bash on Windows and in bash on Linux/macOS.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

to_native_path() {
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -m "$1"
  else
    printf '%s\n' "$1"
  fi
}

for cmd in node npx ffmpeg git; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Required command not found: $cmd" >&2
    exit 1
  fi
done

if [[ ! -x "$ROOT/backend/.venv/Scripts/python.exe" && ! -x "$ROOT/backend/.venv/bin/python" ]]; then
  echo "backend/.venv not found. Create it first (see README.md)." >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

RAW_REPORT_POSIX="$TMP_DIR/playwright-raw.json"
RAW_REPORT_NATIVE="$(to_native_path "$RAW_REPORT_POSIX")"

OUT_DIR="$ROOT/docs/verification"
RAW_DIR="$OUT_DIR/raw"
mkdir -p "$RAW_DIR"

echo "=== Running Playwright E2E suite with E2E_VIDEO=1 (slowMo: 400ms) ==="
PW_EXIT=0
(
  cd "$ROOT/e2e"
  E2E_VIDEO=1 E2E_JSON_REPORT="$RAW_REPORT_NATIVE" npx playwright test
) || PW_EXIT=$?

if [[ ! -f "$RAW_REPORT_POSIX" ]]; then
  echo "Playwright JSON report was not created at $RAW_REPORT_POSIX" >&2
  exit "${PW_EXIT:-1}"
fi

# Remove previous generated media/results while keeping README.md intact.
rm -f "$RAW_DIR"/*.webm "$OUT_DIR"/*.mp4 "$OUT_DIR"/*.gif "$OUT_DIR/results.json"

echo
echo "=== Collecting raw WEBM recordings, converting MP4s and preview GIFs ==="
cd "$ROOT"
RAW_REPORT_PATH="$RAW_REPORT_NATIVE" node <<'NODE'
const crypto = require("node:crypto");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const root = process.cwd();
const reportPath = process.env.RAW_REPORT_PATH;
const outDir = path.join(root, "docs", "verification");
const rawDir = path.join(outDir, "raw");
const tmpDir = path.dirname(reportPath);

const report = JSON.parse(fs.readFileSync(reportPath, "utf8"));

const KNOWN_JOURNEYS = new Map([
  [
    "manager sees the case-study numbers and cannot act on invoices",
    { slug: "01-manager-dashboard", label: "Manager dashboard and read-only view" },
  ],
  [
    "supplier submits an invoice against its own PO; a repeated number is refused",
    { slug: "02-supplier-submit", label: "Supplier submits invoice and duplicate number is refused" },
  ],
  [
    "an inactive supplier is told it cannot submit",
    { slug: "03-inactive-supplier", label: "Inactive supplier is told it cannot submit" },
  ],
  [
    "finance reviews INV006's flags, then approves and pays it",
    { slug: "04-finance-review-approve-pay", label: "Finance reviews INV006 flags, approves, and pays" },
  ],
  [
    "finance rejects INV008 with a reason the supplier can read",
    { slug: "05-finance-reject", label: "Finance rejects INV008 with supplier-visible reason" },
  ],
]);

function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
}

function collectSpecs(suite, inheritedFile, acc) {
  const file = suite.file || inheritedFile || "";
  for (const spec of suite.specs || []) {
    acc.push({ spec, file: spec.file || file });
  }
  for (const child of suite.suites || []) {
    collectSpecs(child, file, acc);
  }
}

function runFfmpeg(args) {
  execFileSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error", ...args], {
    stdio: "inherit",
  });
}

function sha256File(filePath) {
  const hash = crypto.createHash("sha256");
  hash.update(fs.readFileSync(filePath));
  return hash.digest("hex");
}

function makePreviewGif(inputWebm, outputGif) {
  const maxBytes = 8 * 1024 * 1024;
  const profiles = [
    { fps: 8, width: 960 },
    { fps: 6, width: 960 },
    { fps: 5, width: 800 },
    { fps: 4, width: 720 },
  ];
  const palettePath = path.join(tmpDir, "palette.png");

  for (const profile of profiles) {
    const scaleFilter = `fps=${profile.fps},scale=${profile.width}:-1:flags=lanczos`;
    runFfmpeg([
      "-i",
      inputWebm,
      "-vf",
      `${scaleFilter},palettegen=stats_mode=diff`,
      palettePath,
    ]);
    runFfmpeg([
      "-i",
      inputWebm,
      "-i",
      palettePath,
      "-lavfi",
      `${scaleFilter}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3`,
      outputGif,
    ]);
    const size = fs.statSync(outputGif).size;
    if (size <= maxBytes) {
      return { size, ...profile };
    }
  }
  throw new Error(`Preview GIF ${outputGif} still exceeds 8 MB after lowest profile`);
}

const specs = [];
for (const suite of report.suites || []) {
  collectSpecs(suite, "", specs);
}

if (specs.length === 0) {
  throw new Error("No Playwright test specs found in JSON report");
}

const gitSha = execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).trim();
const gitShortSha = execFileSync("git", ["rev-parse", "--short", "HEAD"], { encoding: "utf8" }).trim();

const journeys = [];
let passed = 0;
let failed = 0;

specs.forEach(({ spec, file }, idx) => {
  const index = idx + 1;
  const testEntry = (spec.tests || [])[0];
  const result = testEntry ? testEntry.results[testEntry.results.length - 1] : null;
  if (!result) {
    throw new Error(`Missing test result for spec: ${spec.title}`);
  }

  const status = result.status === "passed" ? "passed" : result.status || "failed";
  if (status === "passed") passed += 1;
  else failed += 1;

  const known = KNOWN_JOURNEYS.get(spec.title);
  const slug = known ? known.slug : `${String(index).padStart(2, "0")}-${slugify(spec.title)}`;
  const label = known ? known.label : spec.title;

  const videoAttachment = (result.attachments || []).find(
    (att) => att.name === "video" && att.path && fs.existsSync(att.path),
  );
  if (!videoAttachment) {
    throw new Error(`Missing Playwright video attachment for test: ${spec.title}`);
  }

  const rawWebmPath = path.join(rawDir, `${slug}.webm`);
  const mp4Path = path.join(outDir, `${slug}.mp4`);
  const gifPath = path.join(outDir, `${slug}.gif`);

  // Exact byte-for-byte copy of Playwright's untouched recording.
  fs.copyFileSync(videoAttachment.path, rawWebmPath);
  const rawWebmSha256 = sha256File(rawWebmPath);
  const rawWebmBytes = fs.statSync(rawWebmPath).size;

  // Straight H.264 format conversion: no filters, no trimming, same length and frames.
  runFfmpeg([
    "-i",
    rawWebmPath,
    "-c:v",
    "libx264",
    "-crf",
    "20",
    "-pix_fmt",
    "yuv420p",
    "-movflags",
    "+faststart",
    mp4Path,
  ]);
  const mp4Bytes = fs.statSync(mp4Path).size;

  // Full-length preview GIF for inline Markdown display (no cuts, no text added).
  const gifInfo = makePreviewGif(rawWebmPath, gifPath);

  console.log(
    `  [${String(index).padStart(2, "0")}] ${status.toUpperCase().padEnd(6)} ${slug} (${result.duration} ms)` +
      ` | webm=${(rawWebmBytes / 1024).toFixed(0)} KB | mp4=${(mp4Bytes / 1024).toFixed(0)} KB` +
      ` | gif=${(gifInfo.size / 1024).toFixed(0)} KB (${gifInfo.width}px @ ${gifInfo.fps}fps)`,
  );

  journeys.push({
    index,
    slug,
    label,
    journey: spec.title,
    specFile: file.replace(/\\/g, "/"),
    status,
    durationMs: result.duration,
    rawWebm: `raw/${slug}.webm`,
    rawWebmBytes,
    rawWebmSha256,
    mp4: `${slug}.mp4`,
    mp4Bytes,
    gif: `${slug}.gif`,
    gifBytes: gifInfo.size,
    gifWidth: gifInfo.width,
    gifFps: gifInfo.fps,
  });
});

const summary = {
  recordedAt: new Date().toISOString(),
  gitSha,
  gitShortSha,
  slowMoMs: 400,
  viewport: { width: 1366, height: 768 },
  total: journeys.length,
  passed,
  failed,
  journeys,
};

fs.writeFileSync(path.join(outDir, "results.json"), JSON.stringify(summary, null, 2) + "\n", "utf8");
console.log(`\nWrote docs/verification/results.json (${passed}/${journeys.length} passed).`);
NODE

exit "$PW_EXIT"
