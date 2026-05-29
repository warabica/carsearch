import logging
from config import FilterConfig

logger = logging.getLogger(__name__)


class CarFilter:
    def __init__(self, cfg: FilterConfig):
        self.cfg = cfg

    def apply(self, cars: list[dict]) -> list[dict]:
        passed, rejected = [], []
        for car in cars:
            reason = self.rejection_reason(car)
            if reason:
                rejected.append((car, reason))
                logger.debug(f"[{car.get('car_code')}] 제외: {reason}")
            else:
                passed.append(car)

        logger.info(f"필터 결과 - 통과: {len(passed)}, 제외: {len(rejected)}")
        return passed

    def rejection_reason(self, car: dict) -> str | None:
        """조건을 통과하지 못한 이유를 반환. 통과하면 None."""
        h = car.get("history", {})

        # 차량명 키워드 체크 (검색어가 title에 포함되어야 함)
        if self.cfg.title_keyword:
            title = (car.get("title") or "").upper()
            if self.cfg.title_keyword.upper() not in title:
                return f"차량명 미포함 ({self.cfg.title_keyword})"

        # 연식 체크
        year = car.get("year")
        month = car.get("month") or 1
        if year is None:
            return "연식 정보 없음"
        if year < self.cfg.min_year:
            return f"연식 미달 ({year}년)"
        if year == self.cfg.min_year and month < self.cfg.min_month:
            return f"연식 미달 ({year}년 {month}월)"

        # 내차 피해
        if self.cfg.no_inner_damage and h.get("inner_damage") is True:
            return "내차 피해 있음"
        if self.cfg.no_inner_damage and h.get("inner_damage") is None:
            return "내차 피해 정보 없음"

        # 주의 이력
        if self.cfg.no_caution and h.get("caution_history") is True:
            return "주의 이력 있음"
        if self.cfg.no_caution and h.get("caution_history") is None:
            return "주의 이력 정보 없음"

        # 사고 이력
        if self.cfg.no_accident and h.get("accident_history") is True:
            return "사고 이력 있음"
        if self.cfg.no_accident and h.get("accident_history") is None:
            return "사고 이력 정보 없음"

        # 소유자 수
        owner_count = h.get("owner_count")
        if owner_count is None:
            return "소유자 정보 없음"
        if owner_count > self.cfg.max_owners:
            return f"소유자 수 초과 ({owner_count}인)"

        # 렌트 이력
        if self.cfg.no_rental and h.get("rental_history") is True:
            return "렌트 이력 있음"
        if self.cfg.no_rental and h.get("rental_history") is None:
            return "렌트 이력 정보 없음"

        return None

    def apply_lenient(self, cars: list[dict]) -> list[dict]:
        """정보 없음(None) 필드는 통과로 처리하는 관대한 필터 (참고용)"""
        passed = []
        for car in cars:
            if self._passes_lenient(car):
                passed.append(car)
        return passed

    def _passes_lenient(self, car: dict) -> bool:
        h = car.get("history", {})
        year = car.get("year")
        month = car.get("month") or 1

        if self.cfg.title_keyword:
            title = (car.get("title") or "").upper()
            if self.cfg.title_keyword.upper() not in title:
                return False

        if year is None or year < self.cfg.min_year:
            return False
        if year == self.cfg.min_year and month < self.cfg.min_month:
            return False
        if self.cfg.no_inner_damage and h.get("inner_damage") is True:
            return False
        if self.cfg.no_caution and h.get("caution_history") is True:
            return False
        if self.cfg.no_accident and h.get("accident_history") is True:
            return False
        owner = h.get("owner_count")
        if owner is not None and owner > self.cfg.max_owners:
            return False
        if self.cfg.no_rental and h.get("rental_history") is True:
            return False
        return True
