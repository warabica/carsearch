import { chromium, devices } from "playwright";

const MOBILE_BASE_URL = "https://m.kcar.com";

async function delay(ms) {
  if (ms > 0) await new Promise((resolve) => setTimeout(resolve, ms));
}

async function safeText(locator) {
  try {
    return (await locator.first().innerText({ timeout: 1200 })).trim();
  } catch {
    return "";
  }
}

function detailUrl(carCd) {
  if (!carCd) return null;
  const normalized = String(carCd).startsWith("EC") ? String(carCd) : `EC${carCd}`;
  return `${MOBILE_BASE_URL}/bc/detail/CarInfoDtl?i_sCarCd=${encodeURIComponent(normalized)}`;
}

function carListUrl(searchCond) {
  return `${MOBILE_BASE_URL}/bc/search/CarList?searchCond=${encodeURIComponent(JSON.stringify(searchCond))}`;
}

function formatPrice(row) {
  if (row.dcFlag === "Y" && row.dcPrc) return `${Number(row.dcPrc).toLocaleString("ko-KR")}만원 ${Number(row.prc).toLocaleString("ko-KR")}만원`;
  if (row.prc) return `${Number(row.prc).toLocaleString("ko-KR")}만원`;
  return "";
}

function formatYear(mfgDt, productionYear) {
  const raw = String(mfgDt || "");
  if (/^\d{6}$/.test(raw)) {
    const year = raw.slice(2, 4);
    const month = String(Number(raw.slice(4, 6)));
    const suffix = productionYear && String(productionYear).slice(2, 4) !== year ? `(${String(productionYear).slice(2, 4)}년형)` : "";
    return `${year}년 ${month}월식${suffix}`;
  }
  return productionYear ? `${String(productionYear).slice(2, 4)}년식` : "";
}

function mapApiRowToSummary(row, index, listUrl) {
  const carCd = String(row.carCd || "").replace(/^EC/, "");
  const labels = String(row.hotmarkNm || "")
    .split(";")
    .map((label) => label.trim())
    .filter(Boolean);

  return {
    listRank: index + 1,
    carCd,
    title: row.carWhlNm || "",
    price: formatPrice(row),
    year: formatYear(row.mfgDt, row.prdcnYr),
    mileage: row.milg ? `${Number(row.milg).toLocaleString("ko-KR")}km` : "",
    fuel: row.fuelNm || "",
    center: row.cntrNm || row.cntrRgnNm || "",
    labels,
    listUrl,
    url: detailUrl(carCd),
    api: {
      acdtHistCnts: row.acdtHistCnts || "",
      acdtHistCd: row.acdtHistCd || "",
      hotmarkNm: row.hotmarkNm || "",
      mfgDt: row.mfgDt || "",
      prc: row.prc || "",
      milg: row.milg || ""
    }
  };
}

function pickFieldByLabels(text, labels) {
  const lines = String(text ?? "")
    .replace(/\r/g, "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  for (const label of labels) {
    const labelPattern = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const inline = new RegExp(`${labelPattern}\\s*[:：]?\\s*([^\\n]{1,100})`, "i").exec(text);
    if (inline?.[1]?.trim()) return inline[1].trim();

    const index = lines.findIndex((line) => new RegExp(`^${labelPattern}\\s*[:：]?$`, "i").test(line));
    if (index >= 0) {
      const next = lines.slice(index + 1).find((line) => !labels.includes(line));
      if (next) return next;
    }
  }

  return "";
}

async function getDirectOwnedMoreHref(page) {
  const href = await page.evaluate(() => {
    const anchors = [...document.querySelectorAll("a[href]")];
    const target = anchors.find((a) => (a.innerText || a.textContent || "").replace(/\s+/g, " ").trim().includes("K Car 직영차 더보기"));
    return target?.getAttribute("href") || "";
  });

  if (!href) return null;
  return new URL(href, MOBILE_BASE_URL).toString();
}

function parseSearchCondFromHref(href, keyword) {
  if (!href) {
    return {
      wr_txt_idx: keyword,
      pageno: 1,
      orderFlag: true,
      orderBy: "prc:desc"
    };
  }

  const url = new URL(href);
  const raw = url.searchParams.get("searchCond");
  const cond = raw ? JSON.parse(raw) : {};
  return {
    ...cond,
    wr_txt_idx: cond.wr_txt_idx || keyword,
    pageno: 1,
    orderFlag: true,
    orderBy: "prc:desc"
  };
}

async function openMobileHighPriceList(page, keyword) {
  const searchUrl = `${MOBILE_BASE_URL}/bc/search/IntgSearchList?searchWord=${encodeURIComponent(keyword)}`;
  await page.goto(searchUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
  await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
  await page.waitForFunction(() => document.body.innerText.includes("K Car 직영차 더보기"), { timeout: 15000 }).catch(() => {});

  const moreHref = await getDirectOwnedMoreHref(page);
  const searchCond = parseSearchCondFromHref(moreHref, keyword);
  const listUrl = carListUrl(searchCond);

  const directListResponse = page
    .waitForResponse((response) => response.url().includes("/bc/search/list/drct") && response.request().method() === "POST", {
      timeout: 30000
    })
    .catch(() => null);

  await page.goto(listUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
  await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
  await page.waitForFunction(() => document.querySelectorAll(".carListBox").length > 0, { timeout: 15000 }).catch(() => {});

  const response = await directListResponse;
  let apiRows = [];
  if (response) {
    const json = await response.json().catch(() => null);
    apiRows = json?.data?.rows || [];
  }

  return { listUrl, apiRows };
}

async function loadVisibleListCards(page, targetCount) {
  let previousCount = 0;
  let stableRounds = 0;

  for (let i = 0; i < 20; i += 1) {
    const count = await page.locator(".carListBox").count();
    if (count >= targetCount) return;

    if (count === previousCount) stableRounds += 1;
    else stableRounds = 0;

    if (stableRounds >= 4) return;
    previousCount = count;

    await page.evaluate(() => window.scrollBy(0, Math.max(window.innerHeight * 2, 1200)));
    await page.waitForLoadState("networkidle", { timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(700);
  }
}

async function extractMobileListCards(page, keyword) {
  return page.evaluate((kw) => {
    const keywordLower = kw.toLowerCase();
    return [...document.querySelectorAll(".carListBox")]
      .map((card, index) => {
        const text = (card.innerText || "").replace(/\s+/g, " ").trim();
        const title = card.querySelector(".carName, #clickCarNm")?.textContent?.replace(/\s+/g, " ").trim() || "";
        const price = card.querySelector(".carExp")?.textContent?.replace(/\s+/g, " ").trim() || "";
        const spec = [...card.querySelectorAll(".detailCarCon span")].map((span) => span.textContent.replace(/\s+/g, " ").trim());
        const image = card.querySelector("img[src*='carpicture'], img[src*='3dcarpicture']")?.getAttribute("src") || "";
        const stateId = card.querySelector("[id^='stateDlvy']")?.id || "";
        const html = card.outerHTML;
        const carCd =
          stateId.match(/EC(\d+)/)?.[1] ||
          image.match(/(?:pic|\/)(\d{8})[_/]/)?.[1] ||
          html.match(/EC(\d{8})/)?.[1] ||
          html.match(/(\d{8})_\d+\/main/)?.[1] ||
          "";
        const labels = [...card.querySelectorAll(".infoLabel li, .grayLabel, .blueLabelKcar2")]
          .map((el) => el.textContent.replace(/\s+/g, " ").trim())
          .filter(Boolean);

        return {
          listRank: index + 1,
          carCd,
          title,
          price,
          year: spec[0] || "",
          mileage: spec[1] || "",
          fuel: spec[2] || "",
          center: spec[3] || "",
          labels,
          text
        };
      })
      .filter((item) => item.carCd && `${item.title} ${item.text}`.toLowerCase().includes(keywordLower.split(" ")[0]));
  }, keyword);
}

async function collectFirstMobileListPage(page, keyword, maxCars) {
  const { listUrl, apiRows } = await openMobileHighPriceList(page, keyword);
  if (apiRows.length > 0) {
    return apiRows.slice(0, maxCars).map((row, index) => mapApiRowToSummary(row, index, listUrl));
  }

  await loadVisibleListCards(page, maxCars);
  const cards = await extractMobileListCards(page, keyword);
  return cards.slice(0, maxCars).map((card) => ({
    ...card,
    listUrl,
    url: detailUrl(card.carCd)
  }));
}

function inferAccidentHistory(text) {
  if (/무사고\s*차량|#\s*무사고|사고진단\s*무사고|무사고/.test(text)) return "무사고";
  if (/단순수리\s*차량|사고진단\s*단순수리|단순수리/.test(text)) return "단순수리";
  return pickFieldByLabels(text, ["사고진단", "사고이력", "사고 여부"]);
}

async function extractDetail(page, summary, debug = false) {
  await page.goto(summary.url, { waitUntil: "domcontentloaded", timeout: 45000 });
  await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
  await page
    .waitForFunction(() => document.body.innerText.includes("내차 피해") || document.body.innerText.includes("주요 과거이력"), {
      timeout: 15000
    })
    .catch(() => {});

  const bodyText = await safeText(page.locator("body"));
  const warningHistory = pickFieldByLabels(bodyText, ["주의이력", "주의 이력", "특수이력", "특수 이력"]);
  const ownerHistory =
    pickFieldByLabels(bodyText, ["소유주 변경", "소유자 변경", "소유이력", "소유 이력"]) ||
    (summary.labels?.includes("1인소유") ? "1인소유" : "");

  const detail = {
    ...summary,
    title: summary.title || pickFieldByLabels(bodyText, ["차량명"]),
    price: summary.price,
    year: pickFieldByLabels(bodyText, ["연식"]) || summary.year,
    firstRegistrationDate: summary.year,
    mileage: summary.mileage || pickFieldByLabels(bodyText, ["주행거리"]),
    accidentHistory: inferAccidentHistory(bodyText),
    ownerHistory: ownerHistory || (summary.labels?.includes("1인소유") ? "1인소유" : ""),
    rentHistory: /렌트|대여/.test(warningHistory) || /렌트로 출고|장기렌트/.test(bodyText) ? "있음" : "없음",
    ownDamage: pickFieldByLabels(bodyText, ["내차 피해", "내차피해", "자차 피해", "자차피해"]),
    warningHistory
  };

  if (debug) detail.rawTextPreview = bodyText.slice(0, 4000);
  return detail;
}

export async function searchKcar(options = {}) {
  const {
    keyword = "g80 (RG3)",
    maxCars = 30,
    delayMs = 1000,
    headless = true,
    debug = false
  } = options;

  const browser = await chromium.launch({ headless });
  const context = await browser.newContext({
    ...devices["iPhone 13"],
    locale: "ko-KR"
  });
  const page = await context.newPage();

  try {
    const summaries = await collectFirstMobileListPage(page, keyword, maxCars);
    const details = [];

    for (const summary of summaries) {
      await delay(delayMs);
      try {
        details.push(await extractDetail(page, summary, debug));
      } catch (error) {
        details.push({
          ...summary,
          scrapeError: error instanceof Error ? error.message : String(error)
        });
      }
    }

    return details;
  } finally {
    await browser.close();
  }
}
