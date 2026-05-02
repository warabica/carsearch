import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";

const rootDir = process.cwd();
const reportsDir = path.join(rootDir, "reports");
const outputDir = path.join(rootDir, "public", "data");

const models = [
  { id: "G80", prefix: "kcar-mobile-g80-rg3-all-" },
  { id: "GV80", prefix: "kcar-mobile-gv80-all-" }
];

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

async function exportModel(model) {
  const reportFile = await latestReport(model.prefix);
  if (!reportFile) throw new Error(`No ${model.id} report found. Run npm.cmd run search -- --model "${model.id}" first.`);

  const rows = JSON.parse(await readFile(path.join(reportsDir, reportFile), "utf8"));
  const candidates = rows.filter((row) => row.passed).map(toPublicCar);
  const payload = {
    model: model.id,
    status: "ready",
    reportFile,
    scanned: rows.length,
    matched: candidates.length,
    candidates,
    all: rows.map(toPublicCar),
    failureSummary: summarizeRows(rows)
  };

  await writeFile(path.join(outputDir, `${model.id}.json`), `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  console.log(`Exported public/data/${model.id}.json from ${reportFile}`);
}

async function main() {
  await mkdir(outputDir, { recursive: true });
  for (const model of models) {
    await exportModel(model);
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
