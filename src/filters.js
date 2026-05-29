export function normalizeText(value) {
  return String(value ?? "")
    .replace(/\s+/g, " ")
    .trim();
}

export function parseKoreanDate(value) {
  const text = normalizeText(value);
  if (!text) return null;

  const match = text.match(/(20\d{2}|\d{2})\s*(?:년|[-./])\s*(1[0-2]|0?[1-9])\s*(?:(?:월|[-./])\s*(3[01]|[12]\d|0?[1-9]))?/);
  if (!match) return null;

  const year = match[1].length === 2 ? 2000 + Number(match[1]) : Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3] ?? 1);
  return new Date(Date.UTC(year, month - 1, day));
}

export function parseCount(value) {
  const text = normalizeText(value);
  if (!text) return null;
  if (/(없음|해당\s*없|이력\s*없|0\s*건|0\s*회)/.test(text)) return 0;

  const countMatch = text.match(/(\d+)\s*(?:건|회)/);
  if (countMatch) return Number(countMatch[1]);

  return null;
}

export function meansNone(value) {
  const text = normalizeText(value);
  if (!text) return null;
  if (/(없음|해당\s*없|이력\s*없|0\s*건|0\s*회|미발견|정상)/.test(text)) return true;
  if (/(있음|주의|사고|피해|렌트|대여|영업|특수용도|침수|전손|도난|화재)/.test(text)) return false;
  return null;
}

export function isOneOwner(value) {
  const text = normalizeText(value);
  if (!text) return null;
  if (/(1인\s*소유|소유주?\s*변경\s*총?\s*0\s*회|변경\s*0\s*회|총\s*0\s*회)/.test(text)) return true;
  if (/(소유주?\s*변경\s*총?\s*[1-9]\d*\s*회|변경\s*[1-9]\d*\s*회|총\s*[1-9]\d*\s*회|[2-9]\s*인\s*소유)/.test(text)) return false;
  return null;
}

export function isAccidentFree(value) {
  const text = normalizeText(value);
  if (!text) return null;
  if (/(무사고|사고\s*없|프레임\s*이상\s*없)/.test(text)) return true;
  if (/(단순수리|유사고|사고|프레임|교환|판금|용접)/.test(text)) return false;
  return null;
}

function requireTrue(check, failureReason, unknownReason, failures, unknowns) {
  if (check === true) return;
  if (check === false) failures.push(failureReason);
  else unknowns.push(unknownReason);
}

function modelMatches(title, model) {
  const normalizedTitle = normalizeText(title).toLowerCase();
  const normalizedModel = normalizeText(model).toLowerCase();
  if (normalizedTitle.includes(normalizedModel)) return true;

  if (normalizedModel.includes("g80") && normalizedModel.includes("rg3")) {
    return normalizedTitle.includes("g80") && normalizedTitle.includes("rg3");
  }

  return false;
}

export function evaluateCar(car, criteria = {}) {
  const model = normalizeText(criteria.model ?? "G80 (RG3)").toLowerCase();
  const minimumDate = parseKoreanDate(criteria.minimumDate ?? "2023-01-01");
  const failures = [];
  const unknowns = [];

  const title = normalizeText(car.title || car.name || car.modelName);
  if (!modelMatches(title, model)) {
    failures.push(`모델명이 ${criteria.model ?? "G80 (RG3)"} 조건과 다름`);
  }

  const registrationDate = parseKoreanDate(car.year || car.firstRegistrationDate || car.registrationDate);
  if (!registrationDate) {
    unknowns.push("연식/최초등록일 확인 불가");
  } else if (minimumDate && registrationDate < minimumDate) {
    failures.push("2023년 1월 이전 차량");
  }

  const ownDamageCount = parseCount(car.ownDamage || car.myCarDamage);
  if (ownDamageCount === null) {
    requireTrue(meansNone(car.ownDamage || car.myCarDamage), "내차 피해 있음", "내차 피해 확인 불가", failures, unknowns);
  } else if (ownDamageCount > 0) {
    failures.push("내차 피해 있음");
  }

  requireTrue(meansNone(car.warningHistory), "주의 이력 있음", "주의 이력 확인 불가", failures, unknowns);
  requireTrue(isAccidentFree(car.accidentHistory || car.accident), "무사고 아님", "사고 여부 확인 불가", failures, unknowns);
  requireTrue(meansNone(car.rentHistory), "렌트 이력 있음", "렌트 이력 확인 불가", failures, unknowns);

  return {
    passed: failures.length === 0 && unknowns.length === 0,
    needsReview: failures.length === 0 && unknowns.length > 0,
    failures,
    unknowns
  };
}
