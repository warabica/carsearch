import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";

const rootDir = process.cwd();
const reportsDir = path.join(rootDir, "reports");
const outputDir = path.join(rootDir, "public", "data");

function summarizeRows(rows) {
  const failures = {};
  for (const row of rows) {
    for (const reason of row.failures || []) failures[reason] = (failures[reason] || 0) + 1;
    for (const reason of row.unknowns || []) failures[reason] = (failures[reason] || 0) + 1;
  }
  return failures;
}

function toPublicCar(row) {
  return {
    rank: row.listRank,
    id: row.carCd,
    title: row.title,
    price: row.price,
    year: row.year,
    mileage: row.api?.milg ? `${Number(row.api.milg).toLocaleString("ko-KR")}km` : row.mileage,
    accident: row.accidentHistory,
    ownDamage: row.ownDamage,
    owner: row.ownerHistory,
    warning: row.warningHistory,
    rent: row.rentHistory,
    url: row.url,
    passed: row.passed,
    failures: row.failures || [],
    unknowns: row.unknowns || []
  };
}

async function latestReport(prefix) {
  const files = await readdir(reportsDir);
  return files
    .filter((file) => file.startsWith(prefix) && file.endsWith(".json"))
    .sort()
    .reverse()[0];
}

async function main() {
  const reportFile = await latestReport("kcar-mobile-g80-rg3-all-");
  if (!reportFile) throw new Error("No G80 report found. Run npm.cmd run search first.");

  const rows = JSON.parse(await readFile(path.join(reportsDir, reportFile), "utf8"));
  const candidates = rows.filter((row) => row.passed).map(toPublicCar);
  const payload = {
    model: "G80",
    status: "ready",
    reportFile,
    scanned: rows.length,
    matched: candidates.length,
    candidates,
    all: rows.map(toPublicCar),
    failureSummary: summarizeRows(rows)
  };

  await mkdir(outputDir, { recursive: true });
  await writeFile(path.join(outputDir, "G80.json"), `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  console.log(`Exported public/data/G80.json from ${reportFile}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
