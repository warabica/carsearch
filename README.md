# K Car Mobile G80 Search

K Car 모바일 사이트 기준으로 `g80 (RG3)`를 검색하고, 통합검색 화면의 `K Car 직영차 더보기` 링크가 가리키는 직영차 목록을 `높은 가격순`으로 조회한 뒤, 첫번째 리스트 페이지의 차량 상세 이력을 검사하는 도구입니다.

## 필터 조건

- 검색어: `g80 (RG3)`
- 목록: 모바일 `K Car 직영차 더보기`
- 정렬: 높은 가격순
- 범위: 첫번째 리스트 페이지, 기본 최대 30대
- 연식: `2023년 1월` 이후
- 내차 피해: 없음
- 주의 이력: 없음
- 사고 여부: 무사고
- 소유 이력: 1인 소유 또는 소유주 변경 0회
- 렌트 이력: 없음

## 실행

```bash
npm.cmd run search -- --model "g80 (RG3)" --from 2023-01 --max-cars 30 --delay-ms 0
```

브라우저를 보면서 확인하려면:

```bash
npm.cmd run search -- --model "g80 (RG3)" --headful --debug
```

## 출력

결과는 `reports/` 폴더에 저장됩니다.

- `kcar-mobile-g80-rg3-all-YYYYMMDD-HHmmss.json`: 조회한 전체 차량과 탈락 사유
- `kcar-mobile-g80-rg3-candidates-YYYYMMDD-HHmmss.csv`: 조건 통과 차량

## 검증

```bash
npm.cmd test
```
