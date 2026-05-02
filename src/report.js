const columns = [
  ["listRank", "목록순위"],
  ["carCd", "차량ID"],
  ["title", "차량명"],
  ["price", "가격"],
  ["year", "연식"],
  ["firstRegistrationDate", "최초등록일"],
  ["mileage", "주행거리"],
  ["accidentHistory", "사고여부"],
  ["ownerHistory", "소유이력"],
  ["rentHistory", "렌트이력"],
  ["ownDamage", "내차피해"],
  ["warningHistory", "주의이력"],
  ["url", "상세URL"]
];

function escapeCsv(value) {
  const text = Array.isArray(value) ? value.join("; ") : String(value ?? "");
  if (/[",\n\r]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

export function toCsv(rows) {
  const header = columns.map(([, label]) => escapeCsv(label)).join(",");
  const body = rows.map((row) => columns.map(([key]) => escapeCsv(row[key])).join(","));
  return `\uFEFF${[header, ...body].join("\n")}`;
}
