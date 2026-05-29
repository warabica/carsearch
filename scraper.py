import asyncio
import logging
import ssl
import json as json_module
import urllib.request

from playwright.async_api import async_playwright

from config import SearchConfig, ScraperConfig
from parser import DetailPageParser

logger = logging.getLogger(__name__)

DETAIL_API = "https://api.kcar.com/bc/car-info-detail-of-ng?i_sCarCd={code}&i_sPassYn=N&bltbdKnd=CM050"
DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class KCarScraper:
    def __init__(self, search_cfg: SearchConfig, scraper_cfg: ScraperConfig):
        self.search_cfg = search_cfg
        self.scraper_cfg = scraper_cfg
        self._detail_parser = DetailPageParser()
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

    async def run(self) -> list[dict]:
        car_codes = await self._collect_car_codes()
        logger.info(f"총 {len(car_codes)}개 차량 코드 수집 완료")

        cars = await self._fetch_details_batch(car_codes)
        valid = [c for c in cars if c is not None]
        logger.info(f"상세 정보 수집 완료: {len(valid)}개")
        return valid

    # ── 목록 수집 ────────────────────────────────────────────────────────────
    async def _collect_car_codes(self) -> list[str]:
        """
        케이카 전체 검색 페이지(bc/search?searchCond=...)에서
        api.kcar.com/bc/search/list/drct 및 wish-yn-list를 인터셉트해
        첫 페이지 결과를 수집한다. (networkidle 대기 후 즉시 반환)
        """
        collected: set[str] = set()
        total_count: list[int] = [0]   # mutable container for closure

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.scraper_cfg.headless)
            ctx = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=DESKTOP_UA,
            )
            page = await ctx.new_page()

            async def on_response(resp):
                url = resp.url
                # api.kcar.com/bc/search/list/* 패턴 (drct, rent, dc, rdy, time 등)
                if "api.kcar.com/bc/search/list/" in url:
                    try:
                        ct = resp.headers.get("content-type", "")
                        if "json" in ct:
                            data = await resp.json()
                            inner = data.get("data", {}) or {}
                            endpoint = url.split("/bc/search/list/")[-1].split("?")[0]

                            # totalCnt는 여러 키 시도
                            t = (inner.get("totalCnt") or inner.get("total_cnt")
                                 or inner.get("totCnt") or 0)

                            # 차량 코드 리스트는 여러 키 이름 시도
                            rows = (inner.get("rows") or inner.get("carList")
                                    or inner.get("list") or inner.get("data") or [])
                            if not isinstance(rows, list):
                                rows = []

                            # drct 파싱 시 구조 디버그
                            if endpoint == "drct":
                                logger.debug(
                                    f"[drct] pageNo={inner.get('pageNo')} "
                                    f"limit={inner.get('limit')} "
                                    f"totalPageCnt={inner.get('totalPageCnt')} "
                                    f"totalCnt={t} rows={len(rows)}"
                                )

                            codes = [r.get("carCd") for r in rows if isinstance(r, dict) and r.get("carCd")]
                            new = [c for c in codes if c not in collected]
                            collected.update(codes)
                            if new:
                                logger.info(
                                    f"[{endpoint}] total={t} +{len(new)}개 (누적 {len(collected)}개)"
                                )
                            elif endpoint == "drct":
                                logger.debug(
                                    f"[drct] 응답 rows={len(rows)} codes={len(codes)} new=0 "
                                    f"(모두 이미 수집됨) t={t}"
                                )

                            # drct 결과의 totalCnt를 기준값으로 저장
                            if endpoint == "drct" and t:
                                try:
                                    total_count[0] = int(t)
                                except (ValueError, TypeError):
                                    pass
                    except Exception as e:
                        logger.debug(f"search/list 파싱 오류 ({url}): {e}")

            async def on_request(req):
                if "api.kcar.com/bc/wish-yn-list" in req.url and req.post_data:
                    try:
                        data = json_module.loads(req.post_data)
                        codes = data.get("carList", [])
                        new = [c for c in codes if c not in collected]
                        collected.update(codes)
                        if new:
                            logger.info(f"wish-yn-list +{len(new)}개 (누적 {len(collected)}개)")
                    except Exception as e:
                        logger.debug(f"wish-yn-list 파싱 오류: {e}")

            page.on("response", on_response)
            page.on("request", on_request)

            url = self.search_cfg.search_url
            logger.info(f"전체 검색 페이지 접속: {url}")
            # networkidle까지 대기해야 wish-yn-list 및 drct 응답을 모두 캡처
            try:
                await page.goto(url, wait_until="networkidle",
                                timeout=self.scraper_cfg.page_load_timeout * 2)
            except Exception:
                # networkidle 타임아웃 시 domcontentloaded까지만 기다림
                await page.goto(url, wait_until="domcontentloaded",
                                timeout=self.scraper_cfg.page_load_timeout)
                await page.wait_for_timeout(8000)

            logger.info(f"첫 페이지 수집 완료: {len(collected)}개 / 전체 매물: {total_count[0]}개")
            await browser.close()

        return list(collected)

    # ── 상세 정보 수집 ────────────────────────────────────────────────────────
    async def _fetch_details_batch(self, car_codes: list[str]) -> list[dict | None]:
        semaphore = asyncio.Semaphore(self.scraper_cfg.max_concurrent)

        async def fetch_one(code: str) -> dict | None:
            async with semaphore:
                result = await self._retry(self._fetch_detail_direct, code)
                await asyncio.sleep(self.scraper_cfg.delay_between_requests)
                return result

        tasks = [fetch_one(code) for code in car_codes]
        return await asyncio.gather(*tasks)

    async def _fetch_detail_direct(self, car_code: str) -> dict | None:
        """브라우저 없이 상세 API를 직접 호출 (훨씬 빠름)."""
        url = DETAIL_API.format(code=car_code)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": DESKTOP_UA,
                "Referer": "https://www.kcar.com/",
                "Accept": "application/json",
            },
        )
        loop = asyncio.get_event_loop()

        def _call():
            with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=15) as resp:
                return json_module.loads(resp.read())

        try:
            data = await loop.run_in_executor(None, _call)
            car = self._detail_parser.parse_from_api(data, car_code)
            car["detail_url"] = self.search_cfg.detail_url(car_code)
            logger.info(
                f"[{car_code}] {car.get('title','?')[:30]} | "
                f"mfgDt={car.get('year')}/{car.get('month')} | "
                f"owner={car['history'].get('owner_count')} | "
                f"rental={car['history'].get('rental_history')}"
            )
            return car
        except Exception as e:
            logger.error(f"[{car_code}] 상세 API 실패: {e}")
            return None

    async def _retry(self, func, *args, **kwargs):
        cfg = self.scraper_cfg
        for attempt in range(cfg.retry_count):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt == cfg.retry_count - 1:
                    logger.error(f"최대 재시도 초과: {e}")
                    return None
                wait = cfg.retry_base_delay * (2 ** attempt)
                logger.warning(f"재시도 {attempt+1}/{cfg.retry_count} ({wait:.1f}s): {e}")
                await asyncio.sleep(wait)
        return None
