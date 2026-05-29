# kcar-fix: 케이카 사이트 변경 대응 가이드

케이카(kcar.com) 사이트 구조가 변경되어 스크래퍼가 동작하지 않을 때 실행하는 스킬입니다.

## 진단 순서

### 1. 증상 확인
먼저 어떤 문제인지 파악한다:
- 차량 코드가 0개 수집됨 → 목록 API 변경
- 차량 코드는 수집되지만 상세 정보가 None → 상세 API 변경
- 필터 통과 차량이 이상하게 많거나 적음 → 파싱 필드명 변경

### 2. 현재 코드 확인
- `src/kcar-scraper.js` — 목록 수집 로직 (모바일 m.kcar.com 사용)
- `src/filters.js` — 필터 조건 및 필드 파싱
- `scraper.py` — Python 버전 (데스크톱 www.kcar.com 사용)
- `parser.py` — 상세 API JSON 파싱

---

## Node.js 스크래퍼 (src/kcar-scraper.js) 진단

### 목록 API 변경 시

브라우저에서 `https://m.kcar.com/bc/search?searchWord=gv80` 접속 후
DevTools → Network → XHR 필터로 실제 검색 API URL 확인.

과거 패턴:
- `api.kcar.com/bc/search/list/drct` (POST, 암호화된 body)
- `api.kcar.com/bc/wish-yn-list` (POST, `{"carList":["EC61xxx",...]}`)

wish-yn-list 인터셉트로 차량 코드 수집하는 방식이 동작하는지 확인:
```js
page.on("request", (req) => {
  if (req.url().includes("wish-yn-list")) {
    const body = JSON.parse(req.postData());
    // body.carList 에 코드 배열이 있어야 함
  }
});
```

wish-yn-list 방식이 사라진 경우 → DOM에서 직접 차량 코드 추출:
```js
// 모바일 목록 페이지의 차량 링크에서 carCd 파라미터 추출
const links = await page.$$eval("a[href*='CarInfoDtl']", els =>
  els.map(el => new URLSearchParams(new URL(el.href).search).get("i_sCarCd"))
);
```

### 상세 API 변경 시

현재 상세 API:
```
GET https://api.kcar.com/bc/car-info-detail-of-ng?i_sCarCd={code}&i_sPassYn=N&bltbdKnd=CM050
```

API가 변경된 경우 브라우저에서 상세 페이지 접속 후 Network 탭에서 JSON 반환하는 API 찾기.

`parser.py`의 `parse_from_api()` 또는 `src/kcar-scraper.js`의 `fetchCarDetail()`에서
필드명 매핑 수정:
```
owncarDmgeAcdtCnt  → inner_damage (0이면 False)
acdtCnt            → accident_history (0이면 False)
rentHistYn         → rental_history ("Y"이면 True)
ownrChngCnt + 1    → owner_count
fldgAcdtCnt        → caution_history 일부
gnrlTtlsAcdtCnt    → caution_history 일부
bizuseHistYn       → caution_history 일부 ("Y"이면 True)
mfgDt              → year/month ("2023-05" 형식)
salprc             → price (만원)
milg               → mileage (km)
```

---

## Python 스크래퍼 (scraper.py) 진단

### 목록 수집 실패 시

현재 URL: `https://www.kcar.com/bc/search?searchCond={"wr_txt_idx":"gv80"}`

브라우저에서 해당 URL 접속 후 Network 탭 확인:
- `api.kcar.com/bc/search/list/*` 응답에 `rows` 배열이 있는지
- `api.kcar.com/bc/wish-yn-list` POST 요청이 발생하는지

URL 패턴이 변경된 경우 `config.py`의 `search_url` 프로퍼티 수정:
```python
@property
def search_url(self) -> str:
    import urllib.parse
    cond = urllib.parse.quote(f'{{"wr_txt_idx":"{self.search_word}"}}')
    return f"{self.base_url}/bc/search?searchCond={cond}"
```

---

## 변경 반영 후 전체 실행 순서

```bash
# 1. Node.js 배치 실행 (G80/GV80/GV70 순차)
npm run batch

# 2. 정적 데이터 생성 (public/data/*.json 갱신)
npm run export:static

# 3. GitHub 커밋 및 푸시
git add reports/ public/data/
git commit -m "Update nightly K Car search results"
git push origin main

# 4. GitHub Pages 배포 (gh-pages 브랜치 갱신)
tmpdir=$(mktemp -d)
cp -R public/. "$tmpdir/"
git checkout --orphan gh-pages-work
git rm -rf .
cp -R "$tmpdir"/. .
git add .
git commit -m "Deploy nightly K Car search results"
git push --force origin gh-pages-work:gh-pages
git checkout main
git branch -D gh-pages-work
```

배포 확인: https://warabica.github.io/carsearch

---

## 자주 발생하는 오류

| 오류 | 원인 | 해결 |
|------|------|------|
| 차량 코드 0개 | 검색 URL 변경 | config.py search_url 또는 scraper.js URL 수정 |
| `'NoneType' object is not subscriptable` | BC 접두사 위탁 차량 | 정상 동작 — 무시해도 됨 |
| 필터 통과 0개인데 매물 다수 | title_keyword 필터 과도 | `--lenient` 옵션으로 테스트 |
| wish-yn-list 미호출 | 페이지 로드 미완료 | networkidle 대기 시간 증가 |
| drct rows=0 | 암호화 API 변경 | wish-yn-list 인터셉트 방식으로 대체 |
