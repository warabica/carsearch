import asyncio
import argparse
import logging

from config import SearchConfig, FilterConfig, ScraperConfig
from scraper import KCarScraper
from filter import CarFilter
from exporter import ResultExporter


def setup_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="케이카 G80 중고차 필터 검색")
    parser.add_argument("--search-word", default="g80", help="검색어 (기본: g80)")
    parser.add_argument("--min-year", type=int, default=2023, help="최소 연식 (기본: 2023)")
    parser.add_argument("--min-month", type=int, default=1, help="최소 월 (기본: 1)")
    parser.add_argument("--max-owners", type=int, default=1, help="최대 소유자 수 (기본: 1)")
    parser.add_argument("--max-pages", type=int, default=0,
                        help="최대 목록 페이지 수, 0=전체 (테스트용)")
    parser.add_argument("--max-concurrent", type=int, default=3,
                        help="동시 상세 페이지 수집 수 (기본: 3)")
    parser.add_argument("--no-headless", action="store_true",
                        help="브라우저를 화면에 표시 (디버깅용)")
    parser.add_argument("--lenient", action="store_true",
                        help="정보 없음(None) 필드를 통과로 처리하는 관대한 필터 적용")
    parser.add_argument("--no-export", action="store_true", help="파일 저장 생략")
    parser.add_argument("--debug", action="store_true", help="디버그 로그 출력")
    return parser.parse_args()


async def main():
    args = parse_args()
    setup_logging(args.debug)

    search_cfg = SearchConfig(search_word=args.search_word)
    filter_cfg = FilterConfig(
        min_year=args.min_year,
        min_month=args.min_month,
        max_owners=args.max_owners,
        title_keyword=args.search_word.upper(),   # 검색어를 차량명 필터로도 적용
    )
    scraper_cfg = ScraperConfig(
        headless=not args.no_headless,
        max_concurrent=args.max_concurrent,
        max_pages=args.max_pages,
    )

    print(f"\n케이카 중고차 검색 시작: '{search_cfg.search_word}'")
    print(f"필터 조건: {args.min_year}년 {args.min_month}월 이후 / "
          f"최대 {args.max_owners}인 소유 / 내차피해·주의·사고·렌트 이력 없음")
    if args.max_pages:
        print(f"[테스트 모드] 최대 {args.max_pages} 페이지만 수집")
    print()

    scraper = KCarScraper(search_cfg, scraper_cfg)
    all_cars = await scraper.run()

    car_filter = CarFilter(filter_cfg)
    if args.lenient:
        filtered = car_filter.apply_lenient(all_cars)
    else:
        filtered = car_filter.apply(all_cars)

    exporter = ResultExporter()
    exporter.print_summary(all_cars, filtered, search_word=args.search_word)
    exporter.print_results(filtered)

    if not args.no_export and filtered:
        csv_path = exporter.export_csv(filtered)
        json_path = exporter.export_json(all_cars, filtered, search_cfg.search_word)
        print(f"결과 저장:\n  CSV : {csv_path}\n  JSON: {json_path}\n")
    elif not filtered:
        print("저장할 차량이 없습니다.\n")


if __name__ == "__main__":
    asyncio.run(main())
