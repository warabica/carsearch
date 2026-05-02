const buttons = [...document.querySelectorAll(".model-button")];
const matchedCount = document.querySelector("#matchedCount");
const modelName = document.querySelector("#modelName");
const scannedCount = document.querySelector("#scannedCount");
const reportFile = document.querySelector("#reportFile");
const statusText = document.querySelector("#statusText");
const candidateList = document.querySelector("#candidateList");
const failureSummary = document.querySelector("#failureSummary");

const plannedModels = {
  GV80: "GV80 검색은 아직 연결되지 않았습니다.",
  GV70: "GV70 검색은 아직 연결되지 않았습니다."
};

function setActive(model) {
  for (const button of buttons) {
    button.classList.toggle("active", button.dataset.model === model);
  }
}

function renderEmpty(message) {
  candidateList.innerHTML = `<div class="empty">${message}</div>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderCandidates(candidates) {
  if (!candidates.length) {
    renderEmpty("조건을 통과한 차량이 없습니다.");
    return;
  }

  candidateList.innerHTML = candidates
    .map(
      (car) => `
        <article class="car-card">
          <div>
            <div class="car-title">#${escapeHtml(car.rank)} ${escapeHtml(car.title)}</div>
            <div class="car-meta">
              <span class="badge">${escapeHtml(car.price)}</span>
              <span>${escapeHtml(car.year)}</span>
              <span>${escapeHtml(car.mileage)}</span>
              <span>내차 피해 ${escapeHtml(car.ownDamage)}</span>
              <span>주의이력 ${escapeHtml(car.warning)}</span>
              <span>${escapeHtml(car.accident)}</span>
              <span>렌트 ${escapeHtml(car.rent)}</span>
              <span>소유 ${escapeHtml(car.owner || "확인값 없음")}</span>
            </div>
          </div>
          <a class="detail-link" href="${escapeHtml(car.url)}" target="_blank" rel="noreferrer">상세</a>
        </article>
      `
    )
    .join("");
}

function renderFailures(summary) {
  const entries = Object.entries(summary || {}).sort((a, b) => b[1] - a[1]);
  if (!entries.length) {
    failureSummary.innerHTML = `<div class="empty">탈락 사유가 없습니다.</div>`;
    return;
  }

  failureSummary.innerHTML = entries
    .map(([reason, count]) => `<div class="reason-item"><span>${escapeHtml(reason)}</span><strong>${escapeHtml(count)}</strong></div>`)
    .join("");
}

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${url} 응답 실패`);
  return response.json();
}

async function loadSearchData(model) {
  if (model !== "G80") {
    return {
      model,
      status: "planned",
      message: plannedModels[model] || `${model} 검색은 아직 연결되지 않았습니다.`,
      scanned: 0,
      matched: 0,
      candidates: [],
      failureSummary: {}
    };
  }

  try {
    return await fetchJson(`api/search?model=${encodeURIComponent(model)}`);
  } catch {
    return fetchJson(`data/${encodeURIComponent(model)}.json`);
  }
}

async function loadModel(model) {
  setActive(model);
  modelName.textContent = model;
  matchedCount.textContent = "-";
  scannedCount.textContent = "-";
  reportFile.textContent = "-";
  statusText.textContent = `${model} 결과를 불러오는 중`;
  renderEmpty("불러오는 중입니다.");
  failureSummary.innerHTML = "";

  const data = await loadSearchData(model);

  if (data.status !== "ready") {
    matchedCount.textContent = "0";
    scannedCount.textContent = "0";
    statusText.textContent = data.message;
    renderEmpty(data.message);
    renderFailures({});
    return;
  }

  matchedCount.textContent = data.matched;
  scannedCount.textContent = data.scanned;
  reportFile.textContent = data.reportFile;
  statusText.textContent = `${data.matched}대가 조건을 통과했습니다.`;
  renderCandidates(data.candidates);
  renderFailures(data.failureSummary);
}

for (const button of buttons) {
  button.addEventListener("click", () => {
    loadModel(button.dataset.model).catch((error) => {
      statusText.textContent = "조회 실패";
      renderEmpty(error instanceof Error ? error.message : String(error));
    });
  });
}

loadModel("G80");
