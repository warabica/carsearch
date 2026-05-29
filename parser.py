import re
import logging
from datetime import datetime
from playwright.async_api import Page

logger = logging.getLogger(__name__)

# 주요 과거이력 키워드 매핑 (사이트 표기 변형 대응)
HISTORY_KEYWORDS = {
    "inner_damage": ["내차피해", "내 차 피해", "내차 피해"],
    "caution_history": ["주의이력", "주의 이력"],
    "accident_history": ["사고이력", "사고 이력", "전손", "침수"],
    "owner_count": ["소유자수", "소유자 수", "소유이력"],
    "rental_history": ["렌트이력", "렌트 이력", "렌터카"],
}

# "없음"으로 해석할 텍스트 패턴
NONE_PATTERNS = re.compile(r"없음|0건|해당없음|이력없음")
# "있음"으로 해석할 텍스트 패턴
HAS_PATTERNS = re.compile(r"있음|[1-9]\d*건")
# 숫자 추출
NUMBER_PATTERN = re.compile(r"\d+")


class ListPageParser:
    async def extract_car_codes(self, page: Page) -> list[str]:
        codes: list[str] = []

        # 전략 1: href에서 i_sCarCd 파라미터 추출
        try:
            links = await page.locator("a[href*='i_sCarCd']").all()
            for link in links:
                href = await link.get_attribute("href") or ""
                code = self._extract_car_code(href)
                if code and code not in codes:
                    codes.append(code)
        except Exception as e:
            logger.debug(f"전략1 실패: {e}")

        # 전략 2: CarInfoDtl 링크에서 추출
        if not codes:
            try:
                links = await page.locator("a[href*='CarInfoDtl']").all()
                for link in links:
                    href = await link.get_attribute("href") or ""
                    code = self._extract_car_code(href)
                    if code and code not in codes:
                        codes.append(code)
            except Exception as e:
                logger.debug(f"전략2 실패: {e}")

        # 전략 3: data-car-code 속성
        if not codes:
            try:
                elements = await page.locator("[data-car-code]").all()
                for el in elements:
                    code = await el.get_attribute("data-car-code") or ""
                    if code and code not in codes:
                        codes.append(code)
            except Exception as e:
                logger.debug(f"전략3 실패: {e}")

        # 전략 4: JavaScript로 페이지 전체 href 스캔
        if not codes:
            try:
                hrefs = await page.evaluate("""
                    () => Array.from(document.querySelectorAll('a[href]'))
                        .map(a => a.href)
                        .filter(h => h.includes('i_sCarCd') || h.includes('CarInfoDtl'))
                """)
                for href in hrefs:
                    code = self._extract_car_code(href)
                    if code and code not in codes:
                        codes.append(code)
            except Exception as e:
                logger.debug(f"전략4 실패: {e}")

        return codes

    async def has_next_page(self, page: Page) -> bool:
        # 다음 페이지 버튼/링크 탐색
        selectors = [
            "a.next", "button.next", "[class*='next']",
            "a:has-text('다음')", "button:has-text('다음')",
            "[aria-label='다음']", ".pagination .next",
        ]
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    disabled = await el.get_attribute("disabled")
                    aria_disabled = await el.get_attribute("aria-disabled")
                    class_attr = await el.get_attribute("class") or ""
                    if disabled is None and aria_disabled != "true" and "disabled" not in class_attr:
                        return True
            except Exception:
                continue
        return False

    @staticmethod
    def _extract_car_code(href: str) -> str | None:
        match = re.search(r"i_sCarCd=([A-Z0-9]+)", href, re.IGNORECASE)
        if match:
            return match.group(1)
        # /CarInfoDtl/EC61221470 형태
        match = re.search(r"CarInfoDtl[/?]([A-Z0-9]+)", href, re.IGNORECASE)
        if match:
            return match.group(1)
        return None


class DetailPageParser:
    def parse_from_api(self, data: dict, car_code: str) -> dict:
        """API JSON 응답에서 직접 차량 정보를 파싱한다."""
        car: dict = {
            "car_code": car_code,
            "title": None,
            "year": None,
            "month": None,
            "price": None,
            "mileage": None,
            "history": {
                "inner_damage": None,
                "caution_history": None,
                "accident_history": None,
                "owner_count": None,
                "rental_history": None,
            },
            "scraped_at": datetime.now().isoformat(timespec="seconds"),
        }

        inner = data.get("data", data)
        rvo = inner.get("rvo", {}) or {}
        carhistory = inner.get("carhistory", {}) or {}

        # 차량명
        parts = [rvo.get("modelNm"), rvo.get("grdFullNm")]
        car["title"] = " ".join(p for p in parts if p) or rvo.get("carNm") or None

        # 연식 (mfgDt = "YYYYMM")
        mfg = str(rvo.get("mfgDt", "") or "")
        if len(mfg) >= 6:
            try:
                car["year"] = int(mfg[:4])
                car["month"] = int(mfg[4:6])
            except ValueError:
                pass

        # 가격 (만원)
        try:
            raw = rvo.get("salprc")
            if raw is not None:
                car["price"] = int(str(raw).replace(",", ""))
        except (ValueError, TypeError):
            pass

        # 주행거리 (km)
        try:
            raw = rvo.get("milg")
            if raw is not None:
                car["mileage"] = int(str(raw).replace(",", ""))
        except (ValueError, TypeError):
            pass

        # 주요 과거이력
        h = car["history"]

        def _cnt(val) -> int:
            try:
                return int(val or 0)
            except (ValueError, TypeError):
                return 0

        def _yn(val) -> bool:
            return str(val or "N").upper() == "Y"

        h["inner_damage"] = _cnt(carhistory.get("owncarDmgeAcdtCnt")) > 0
        h["accident_history"] = _cnt(carhistory.get("acdtCnt")) > 0
        h["caution_history"] = (
            _cnt(carhistory.get("fldgAcdtCnt")) > 0
            or _cnt(carhistory.get("gnrlTtlsAcdtCnt")) > 0
            or _yn(carhistory.get("bizuseHistYn"))
        )
        h["owner_count"] = _cnt(carhistory.get("ownrChngCnt")) + 1
        h["rental_history"] = _yn(carhistory.get("rentHistYn"))

        return car

    async def parse(self, page: Page, car_code: str, intercepted: dict) -> dict:
        car: dict = {
            "car_code": car_code,
            "title": None,
            "year": None,
            "month": None,
            "price": None,
            "mileage": None,
            "history": {
                "inner_damage": None,
                "caution_history": None,
                "accident_history": None,
                "owner_count": None,
                "rental_history": None,
            },
            "scraped_at": datetime.now().isoformat(timespec="seconds"),
        }

        # 인터셉트된 API JSON이 있으면 우선 파싱
        if intercepted.get("api"):
            self._parse_from_api(intercepted["api"], car)

        # DOM 파싱으로 누락 필드 보완
        await self._parse_from_dom(page, car, car_code)

        return car

    def _parse_from_api(self, data: dict, car: dict):
        flat = self._flatten(data)

        for key, val in flat.items():
            key_lower = key.lower()
            val_str = str(val) if val is not None else ""

            if any(k in key_lower for k in ["title", "carnm", "carnme", "modelnm"]):
                if car["title"] is None:
                    car["title"] = val_str
            elif any(k in key_lower for k in ["year", "myyear", "frstregdt"]):
                year_match = re.search(r"(20\d{2})", val_str)
                if year_match and car["year"] is None:
                    car["year"] = int(year_match.group(1))
                    month_match = re.search(r"(20\d{2})[-./]?(\d{2})", val_str)
                    if month_match and car["month"] is None:
                        car["month"] = int(month_match.group(2))
            elif any(k in key_lower for k in ["price", "sellprc", "amt"]):
                num = NUMBER_PATTERN.search(val_str)
                if num and car["price"] is None:
                    car["price"] = int(num.group())
            elif any(k in key_lower for k in ["mileage", "drivedist", "drivdis"]):
                num = NUMBER_PATTERN.search(val_str)
                if num and car["mileage"] is None:
                    car["mileage"] = int(num.group())
            elif any(k in key_lower for k in ["innerdmg", "mycar", "inner"]):
                self._set_bool_field(car["history"], "inner_damage", val_str)
            elif any(k in key_lower for k in ["caution", "warn", "jui"]):
                self._set_bool_field(car["history"], "caution_history", val_str)
            elif any(k in key_lower for k in ["accident", "acc", "sabgo"]):
                self._set_bool_field(car["history"], "accident_history", val_str)
            elif any(k in key_lower for k in ["owner", "sowoner", "holder"]):
                num = NUMBER_PATTERN.search(val_str)
                if num and car["history"]["owner_count"] is None:
                    car["history"]["owner_count"] = int(num.group())
            elif any(k in key_lower for k in ["rental", "rent", "lent"]):
                self._set_bool_field(car["history"], "rental_history", val_str)

    async def _parse_from_dom(self, page: Page, car: dict, car_code: str):
        # 제목
        if car["title"] is None:
            car["title"] = await self._extract_title(page)

        # 연식/월
        if car["year"] is None:
            year, month = await self._extract_year_month(page)
            car["year"] = year
            car["month"] = month

        # 가격
        if car["price"] is None:
            car["price"] = await self._extract_price(page)

        # 주행거리
        if car["mileage"] is None:
            car["mileage"] = await self._extract_mileage(page)

        # 주요 과거이력
        await self._extract_history(page, car["history"], car_code)

    async def _extract_title(self, page: Page) -> str | None:
        selectors = ["h1", "h2", "[class*='carNm']", "[class*='car-name']", "[class*='carName']"]
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    text = (await el.inner_text()).strip()
                    if text:
                        return text
            except Exception:
                continue
        return None

    async def _extract_year_month(self, page: Page) -> tuple[int | None, int | None]:
        # 텍스트에서 연식 패턴 탐색
        try:
            text = await page.inner_text("body")
            match = re.search(r"(20\d{2})년\s*(\d{1,2})월", text)
            if match:
                return int(match.group(1)), int(match.group(2))
            match = re.search(r"(20\d{2})\s*[./\-]\s*(\d{2})", text)
            if match:
                return int(match.group(1)), int(match.group(2))
            match = re.search(r"연식[^\d]*(20\d{2})", text)
            if match:
                return int(match.group(1)), None
        except Exception as e:
            logger.debug(f"연식 추출 실패: {e}")
        return None, None

    async def _extract_price(self, page: Page) -> int | None:
        selectors = ["[class*='price']", "[class*='Price']", "[class*='prc']"]
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    text = await el.inner_text()
                    num = NUMBER_PATTERN.search(text.replace(",", ""))
                    if num:
                        return int(num.group())
            except Exception:
                continue
        return None

    async def _extract_mileage(self, page: Page) -> int | None:
        try:
            text = await page.inner_text("body")
            match = re.search(r"주행[^\d]*([\d,]+)\s*km", text, re.IGNORECASE)
            if match:
                return int(match.group(1).replace(",", ""))
        except Exception:
            pass
        return None

    async def _extract_history(self, page: Page, history: dict, car_code: str):
        """주요 과거이력 섹션을 다중 전략으로 파싱"""

        # 전략 1: 텍스트 로케이터로 섹션 탐색
        extracted = await self._history_from_locators(page)
        if extracted:
            for field, val in extracted.items():
                if history.get(field) is None:
                    history[field] = val
            logger.debug(f"[{car_code}] 전략1(텍스트 로케이터) 성공")

        # 전략 2: JS로 페이지 전체 텍스트 맵 추출
        if any(v is None for v in history.values()):
            extracted2 = await self._history_from_js(page)
            for field, val in extracted2.items():
                if history.get(field) is None:
                    history[field] = val
            if extracted2:
                logger.debug(f"[{car_code}] 전략2(JS) 보완")

        # 여전히 None인 필드 경고
        none_fields = [k for k, v in history.items() if v is None]
        if none_fields:
            logger.warning(f"[{car_code}] 파싱 미완료 필드: {none_fields}")

    async def _history_from_locators(self, page: Page) -> dict:
        result: dict = {}

        section_texts = ["주요 과거이력", "과거이력", "사고이력", "이력정보"]
        section = None
        for text in section_texts:
            try:
                loc = page.locator(f"text={text}").first
                if await loc.count() > 0:
                    section = loc
                    break
            except Exception:
                continue

        if section is None:
            return result

        try:
            # 섹션 부모 컨테이너의 전체 텍스트 가져오기
            container_text = ""
            for depth in range(1, 5):
                parent = section
                for _ in range(depth):
                    parent = parent.locator("..")
                try:
                    container_text = await parent.inner_text()
                    if len(container_text) > 50:
                        break
                except Exception:
                    continue

            if container_text:
                result = self._parse_history_text(container_text)
        except Exception as e:
            logger.debug(f"섹션 컨테이너 파싱 실패: {e}")

        return result

    async def _history_from_js(self, page: Page) -> dict:
        try:
            text = await page.evaluate("""
                () => {
                    const keywords = ['내차피해', '내 차 피해', '주의이력', '주의 이력',
                                      '사고이력', '사고 이력', '소유자수', '소유자 수',
                                      '렌트이력', '렌트 이력'];
                    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                    const found = {};
                    let node;
                    while (node = walker.nextNode()) {
                        const t = node.textContent.trim();
                        for (const kw of keywords) {
                            if (t.includes(kw)) {
                                // 부모와 형제 텍스트 함께 수집
                                const parent = node.parentElement;
                                if (parent) {
                                    found[kw] = parent.closest('tr, li, div')?.innerText || parent.innerText || t;
                                }
                            }
                        }
                    }
                    return JSON.stringify(found);
                }
            """)
            import json
            data = json.loads(text)
            result: dict = {}
            for kw, val in data.items():
                field = self._keyword_to_field(kw)
                if field and field not in result:
                    normalized = self._normalize_value(field, val)
                    if normalized is not None:
                        result[field] = normalized
            return result
        except Exception as e:
            logger.debug(f"JS 전략 실패: {e}")
            return {}

    def _parse_history_text(self, text: str) -> dict:
        result: dict = {}
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        for i, line in enumerate(lines):
            for field, keywords in HISTORY_KEYWORDS.items():
                if any(kw in line for kw in keywords):
                    # 같은 줄 또는 다음 줄에서 값 추출
                    value_text = line
                    if i + 1 < len(lines):
                        value_text = line + " " + lines[i + 1]
                    normalized = self._normalize_value(field, value_text)
                    if normalized is not None and field not in result:
                        result[field] = normalized

        return result

    def _keyword_to_field(self, keyword: str) -> str | None:
        for field, keywords in HISTORY_KEYWORDS.items():
            if keyword in keywords:
                return field
        return None

    @staticmethod
    def _normalize_value(field: str, text: str) -> bool | int | None:
        if field == "owner_count":
            num = NUMBER_PATTERN.search(text)
            if num:
                return int(num.group())
            return None
        if NONE_PATTERNS.search(text):
            return False
        if HAS_PATTERNS.search(text):
            return True
        return None

    @staticmethod
    def _set_bool_field(history: dict, field: str, val_str: str):
        if history.get(field) is not None:
            return
        if NONE_PATTERNS.search(val_str):
            history[field] = False
        elif HAS_PATTERNS.search(val_str) or val_str in ("Y", "1", "true"):
            history[field] = True
        elif val_str in ("N", "0", "false"):
            history[field] = False

    @staticmethod
    def _flatten(data, prefix="", sep=".") -> dict:
        items: dict = {}
        if isinstance(data, dict):
            for k, v in data.items():
                new_key = f"{prefix}{sep}{k}" if prefix else k
                items.update(DetailPageParser._flatten(v, new_key, sep))
        elif isinstance(data, list):
            for i, v in enumerate(data):
                new_key = f"{prefix}{sep}{i}" if prefix else str(i)
                items.update(DetailPageParser._flatten(v, new_key, sep))
        else:
            items[prefix] = data
        return items
