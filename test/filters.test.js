import test from "node:test";
import assert from "node:assert/strict";
import { evaluateCar, parseCount, parseKoreanDate } from "../src/filters.js";

test("parseKoreanDate parses Korean year-month text", () => {
  assert.equal(parseKoreanDate("2023년 01월").toISOString().slice(0, 10), "2023-01-01");
  assert.equal(parseKoreanDate("2024.05.13").toISOString().slice(0, 10), "2024-05-13");
  assert.equal(parseKoreanDate("23년 1월식").toISOString().slice(0, 10), "2023-01-01");
  assert.equal(parseKoreanDate("18년 12월식(19년형)").toISOString().slice(0, 10), "2018-12-01");
});

test("parseCount handles Korean none/count values", () => {
  assert.equal(parseCount("없음"), 0);
  assert.equal(parseCount("0건"), 0);
  assert.equal(parseCount("총 1회"), 1);
  assert.equal(parseCount("총 1,497,304원 (1건)"), 1);
});

test("evaluateCar passes ideal G80 RG3", () => {
  const result = evaluateCar(
    {
      title: "제네시스 G80 (RG3) 가솔린 터보 2.5 2WD",
      firstRegistrationDate: "23년 3월식",
      ownDamage: "없음",
      warningHistory: "없음",
      accidentHistory: "무사고",
      ownerHistory: "1인소유",
      rentHistory: "없음"
    },
    { model: "g80 (RG3)", minimumDate: "2023-01-01" }
  );

  assert.equal(result.passed, true);
  assert.deepEqual(result.failures, []);
  assert.deepEqual(result.unknowns, []);
});

test("evaluateCar rejects damage, rent, and old year but ignores owner changes", () => {
  const result = evaluateCar(
    {
      title: "제네시스 G80 (RG3) 가솔린 터보 2.5 AWD",
      firstRegistrationDate: "22년 12월식",
      ownDamage: "1건",
      warningHistory: "특수용도 (대여)",
      accidentHistory: "무사고",
      ownerHistory: "총 1회",
      rentHistory: "있음"
    },
    { model: "g80 (RG3)", minimumDate: "2023-01-01" }
  );

  assert.equal(result.passed, false);
  assert.match(result.failures.join(" "), /2023년 1월 이전/);
  assert.match(result.failures.join(" "), /내차 피해 있음/);
  assert.match(result.failures.join(" "), /렌트 이력 있음/);
  assert.doesNotMatch(result.failures.join(" "), /1인 소유/);
});
