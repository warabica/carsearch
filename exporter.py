import csv
import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

COLUMNS = [
    "car_code", "title", "year", "month",
    "price_만원", "mileage_km",
    "inner_damage", "caution_history", "accident_history",
    "owner_count", "rental_history",
    "detail_url", "scraped_at",
]


class ResultExporter:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def export_csv(self, cars: list[dict], filename: str | None = None) -> str:
        path = self._build_path(filename, "csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for car in cars:
                writer.writerow(self._flatten_car(car))
        logger.info(f"CSV 저장: {path}")
        return path

    def export_json(self, all_cars: list[dict], filtered_cars: list[dict],
                    search_word: str, filename: str | None = None) -> str:
        path = self._build_path(filename, "json")
        payload = {
            "metadata": {
                "search_word": search_word,
                "scraped_at": datetime.now().isoformat(timespec="seconds"),
                "total_found": len(all_cars),
                "filter_passed": len(filtered_cars),
            },
            "cars": filtered_cars,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info(f"JSON 저장: {path}")
        return path

    def print_summary(self, all_cars: list[dict], filtered_cars: list[dict],
                      search_word: str = ""):
        total = len(all_cars)
        passed = len(filtered_cars)
        rejected = total - passed
        kw = search_word.upper() if search_word else "전체"
        print("\n" + "=" * 55)
        print(f"  검색어: {kw}   총 수집: {total}건")
        print(f"  필터 통과: {passed}건   제외: {rejected}건")
        print("=" * 55)

    def print_results(self, cars: list[dict]):
        if not cars:
            print("\n조건에 맞는 차량이 없습니다.\n")
            return

        header = f"{'#':>3}  {'연식':6}  {'가격(만원)':>10}  {'주행(km)':>10}  {'제목'}"
        print("\n" + header)
        print("-" * 80)
        for i, car in enumerate(cars, 1):
            year_str = f"{car.get('year', '?')}년 {car.get('month') or '?'}월"
            price = f"{car.get('price', '?'):,}" if car.get("price") else "?"
            mileage = f"{car.get('mileage', '?'):,}" if car.get("mileage") else "?"
            title = (car.get("title") or "")[:35]
            print(f"{i:>3}. {year_str:8}  {price:>10}  {mileage:>10}  {title}")
            print(f"     {car.get('detail_url', '')}")
        print()

    def _build_path(self, filename: str | None, ext: str) -> str:
        if filename:
            return os.path.join(self.output_dir, filename)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.output_dir, f"results_{ts}.{ext}")

    @staticmethod
    def _flatten_car(car: dict) -> dict:
        h = car.get("history", {})
        return {
            "car_code": car.get("car_code"),
            "title": car.get("title"),
            "year": car.get("year"),
            "month": car.get("month"),
            "price_만원": car.get("price"),
            "mileage_km": car.get("mileage"),
            "inner_damage": h.get("inner_damage"),
            "caution_history": h.get("caution_history"),
            "accident_history": h.get("accident_history"),
            "owner_count": h.get("owner_count"),
            "rental_history": h.get("rental_history"),
            "detail_url": car.get("detail_url"),
            "scraped_at": car.get("scraped_at"),
        }
