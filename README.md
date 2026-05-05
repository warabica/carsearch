# K Car Mobile Search

K Car 모바일 사이트 기준으로 `G80`, `GV80`, `GV70`를 검색하고, 통합검색 화면의 `K Car 직영차 더보기` 링크가 가리키는 직영차 목록을 `높은 가격순`으로 조회한 뒤, 첫번째 리스트 페이지의 차량 상세 이력을 검사하는 도구입니다.

## 필터 조건

- 검색어: `g80 (RG3)`, `GV80`, `GV70`
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
npm.cmd run search -- --model "GV80" --from 2023-01 --max-cars 30 --delay-ms 0
npm.cmd run search -- --model "GV70" --from 2023-01 --max-cars 30 --delay-ms 0
npm.cmd run export:static
```

## 자동 실행

GitHub Actions가 매일 아래 작업을 실행합니다.

- `21:00 KST`: `G80`, `GV80`, `GV70` 검색 후 `reports/`, `public/data/` 갱신
- `22:00 KST`: 최신 후보 리스트를 `minseok.lee@gmail.com`으로 발송

메일 발송에는 저장소 Secrets가 필요합니다.

```text
SMTP_HOST
SMTP_PORT
SMTP_USER
SMTP_PASSWORD
SMTP_FROM
```

Gmail을 사용할 경우 `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER`는 Gmail 주소, `SMTP_PASSWORD`는 앱 비밀번호를 사용합니다.

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
