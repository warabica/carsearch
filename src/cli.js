#!/usr/bin/env node

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { searchKcar } from "./kcar-scraper.js";
import { evaluateCar } from "./filters.js";
import { toCsv } from "./report.js";

function parseArgs(argv) {
  const options = {
    model: "g80 (RG3)",
    from: "2023-01",
    outputDir: "reports",
    maxCars: 30,
    delayMs: 1000,
    headful: false,
    debug: false
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = argv[i + 1];
    if (arg === "--model") {
      options.model = next;
      i += 1;
    } else if (arg === "--from") {
      options.from = next;
      i += 1;
    } else if (arg === "--output-dir") {
      options.outputDir = next;
      i += 1;
    } else if (arg === "--max-cars") {
      options.maxCars = Number(next);
      i += 1;
    } else if (arg === "--delay-ms") {
      options.delayMs = Number(next);
      i += 1;
    } else if (arg === "--headful") {
      options.headful = true;
    } else if (arg === "--debug") {
      options.debug = true;
    } else if (arg === "--help" || arg === "-h") {
      options.help = true;
    }
  }

  return options;
}

function printHelp() {
  console.log(`Usage:
  npm run search -- [options]

Options:
  --model "g80 (RG3)"     Search keyword/model. Default: g80 (RG3)
  --from 2023-01          Minimum registration year-month. Default: 2023-01
  --max-cars 30           Maximum detail pages to scan from the first mobile list page. Default: 30
  --delay-ms 1000         Delay between detail pages. Default: 1000
  --output-dir reports    Report output directory. Default: reports
  --headful               Show browser
  --debug                 Keep extra debug fields
`);
}

function timestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    printHelp();
    return;
  }

  const minimumDate = `${options.from.length === 7 ? options.from : "2023-01"}-01`;
  console.log(`Searching K Car mobile for ${options.model} from ${minimumDate}, high price first...`);

  const cars = await searchKcar({
    keyword: options.model,
    maxCars: options.maxCars,
    delayMs: options.delayMs,
    headless: !options.headful,
    debug: options.debug
  });

  const evaluated = cars.map((car) => {
    const evaluation = evaluateCar(car, {
      model: options.model,
      minimumDate
    });
    return { ...car, ...evaluation };
  });

  const candidates = evaluated.filter((car) => car.passed);
  await mkdir(options.outputDir, { recursive: true });

  const stamp = timestamp();
  const safeModel = options.model.toLowerCase().replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "");
  const jsonPath = path.join(options.outputDir, `kcar-mobile-${safeModel}-all-${stamp}.json`);
  const csvPath = path.join(options.outputDir, `kcar-mobile-${safeModel}-candidates-${stamp}.csv`);

  await writeFile(jsonPath, JSON.stringify(evaluated, null, 2), "utf8");
  await writeFile(csvPath, toCsv(candidates), "utf8");

  console.log(`Scanned ${evaluated.length} cars.`);
  console.log(`Matched ${candidates.length} candidates.`);
  console.log(`JSON: ${jsonPath}`);
  console.log(`CSV: ${csvPath}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
