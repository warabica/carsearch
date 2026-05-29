from dataclasses import dataclass, field
import os


@dataclass
class SearchConfig:
    search_word: str = "g80"
    base_url: str = "https://www.kcar.com"

    @property
    def search_url(self) -> str:
        import urllib.parse
        cond = urllib.parse.quote(f'{{"wr_txt_idx":"{self.search_word}"}}')
        return f"{self.base_url}/bc/search?searchCond={cond}"

    def detail_url(self, car_code: str) -> str:
        return f"{self.base_url}/bc/detail/CarInfoDtl?i_sCarCd={car_code}"


@dataclass
class FilterConfig:
    min_year: int = 2023
    min_month: int = 1
    max_owners: int = 1
    no_inner_damage: bool = True
    no_caution: bool = True
    no_accident: bool = True
    no_rental: bool = True
    title_keyword: str = ""   # 차량명 필수 포함 키워드 (빈 문자열이면 체크 안 함)


@dataclass
class ScraperConfig:
    headless: bool = field(default_factory=lambda: os.getenv("KCAR_HEADLESS", "true").lower() == "true")
    max_concurrent: int = field(default_factory=lambda: int(os.getenv("KCAR_MAX_CONCURRENT", "3")))
    page_load_timeout: int = 30000
    network_idle_timeout: int = 10000
    delay_between_requests: float = 1.5
    retry_count: int = 3
    retry_base_delay: float = 2.0
    max_pages: int = 0  # 0 = 전체 페이지 수집, 양수 = 최대 페이지 수 제한 (테스트용)
