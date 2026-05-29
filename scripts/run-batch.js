import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { searchKcar } from "../src/kcar-scraper.js";
import { evaluateCar } from "../src/filters.js";
import { toCsv } from "../src/report.js";

const models = [
  { id: "G80", keyword: "g80 (RG3)", safeName: "g80-rg3" },
  { id: "GV80", keyword: "GV80", safeName: "gv80" },
  { id: "GV70", keyword: "GV70", safeName: "gv70" }
];

const outputDir = "reports";
const minimumDate = "2023-01-01";
const maxCars = Number(process.env.MAX_CARS || 30);
const delayMs = Number(process.env.DELAY_MS || 0);

function timestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

async function runModel(model) {
  console.log(`[${model.id}] search started`);
  const cars = await searchKcar({
    keyword: model.keyword,
    maxCars,
    delayMs,
    headless: true,
    debug: false
  });

  const evaluated = cars.map((car) => ({
    ...car,
    ...evaluateCar(car, {
      model: model.keyword,
      minimumDate
    })
  }));

  const candidates = evaluated.filter((car) => car.passed);
  const stamp = timestamp();
  const jsonPath = path.join(outputDir, `kcar-mobile-${model.safeName}-all-${stamp}.json`);
  const csvPath = path.join(outputDir, `kcar-mobile-${model.safeName}-candidates-${stamp}.csv`);

  await writeFile(jsonPath, `${JSON.stringify(evaluated, null, 2)}\n`, "utf8");
  await writeFile(csvPath, toCsv(candidates), "utf8");

  console.log(`[${model.id}] scanned=${evaluated.length} matched=${candidates.length}`);
  console.log(`[${model.id}] json=${jsonPath}`);
  console.log(`[${model.id}] csv=${csvPath}`);
}

async function main() {
  await mkdir(outputDir, { recursive: true });

  for (const model of models) {
    await runModel(model);
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
