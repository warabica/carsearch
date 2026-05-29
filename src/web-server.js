import { createServer } from "node:http";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");
const publicDir = path.join(rootDir, "public");
const reportsDir = path.join(rootDir, "reports");
const port = Number(process.env.PORT || 3000);

const modelConfig = {
  G80: {
    label: "G80",
    reportPrefix: "kcar-mobile-g80-rg3-all-",
    status: "ready"
  },
  GV80: {
    label: "GV80",
    reportPrefix: "kcar-mobile-gv80-all-",
    status: "ready"
  },
  GV70: {
    label: "GV70",
    reportPrefix: "kcar-mobile-gv70-all-",
    status: "ready"
  }
};

const contentTypes = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon"
};

function sendJson(res, status, payload) {
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store"
  });
  res.end(JSON.stringify(payload));
}

function sendError(res, status, message) {
  sendJson(res, status, { error: message });
}

async function findLatestReport(prefix) {
  const files = await readdir(reportsDir).catch(() => []);
  const matched = files
    .filter((file) => file.startsWith(prefix) && file.endsWith(".json"))
    .sort()
    .reverse();

  if (matched.length === 0) return null;
  return matched[0];
}

function summarizeRows(rows) {
  const failures = {};
  for (const row of rows) {
    for (const reason of row.failures || []) {
      failures[reason] = (failures[reason] || 0) + 1;
    }
    for (const reason of row.unknowns || []) {
      failures[reason] = (failures[reason] || 0) + 1;
    }
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

async function handleApi(req, res, url) {
  if (url.pathname === "/api/models") {
    sendJson(res, 200, {
      models: Object.entries(modelConfig).map(([id, config]) => ({
        id,
        label: config.label,
        status: config.status
      }))
    });
    return;
  }

  if (url.pathname === "/api/search") {
    const model = String(url.searchParams.get("model") || "").toUpperCase();
    const config = modelConfig[model];
    if (!config) {
      sendError(res, 404, "지원하지 않는 모델입니다.");
      return;
    }

    if (config.status !== "ready") {
      sendJson(res, 200, {
        model,
        status: config.status,
        message: `${model} 검색은 아직 연결되지 않았습니다.`,
        scanned: 0,
        candidates: [],
        all: []
      });
      return;
    }

    const reportFile = await findLatestReport(config.reportPrefix);
    if (!reportFile) {
      sendError(res, 404, "G80 검색 결과 파일을 찾을 수 없습니다. 먼저 CLI 검색을 실행해 주세요.");
      return;
    }

    const rows = JSON.parse(await readFile(path.join(reportsDir, reportFile), "utf8"));
    const candidates = rows.filter((row) => row.passed).map(toPublicCar);
    const all = rows.map(toPublicCar);

    sendJson(res, 200, {
      model,
      status: "ready",
      reportFile,
      scanned: rows.length,
      matched: candidates.length,
      candidates,
      all,
      failureSummary: summarizeRows(rows)
    });
    return;
  }

  sendError(res, 404, "API endpoint not found.");
}

async function serveStatic(res, pathname) {
  const safePath = pathname === "/" ? "/index.html" : pathname;
  const filePath = path.resolve(publicDir, `.${safePath}`);

  if (!filePath.startsWith(publicDir)) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }

  try {
    const body = await readFile(filePath);
    res.writeHead(200, {
      "content-type": contentTypes[path.extname(filePath)] || "application/octet-stream; charset=utf-8"
    });
    res.end(body);
  } catch {
    res.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    res.end("Not found");
  }
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);

  try {
    if (url.pathname.startsWith("/api/")) {
      await handleApi(req, res, url);
      return;
    }

    await serveStatic(res, url.pathname);
  } catch (error) {
    sendError(res, 500, error instanceof Error ? error.message : String(error));
  }
});

server.listen(port, () => {
  console.log(`Carsearch web app running at http://localhost:${port}`);
});
