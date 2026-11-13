"""hwpbench 명령줄."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import corpus, report, runner, score, truth


def _set(value: str | None) -> set[str] | None:
    return {v.strip() for v in value.split(",") if v.strip()} if value else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hwpbench", description="HWP·HWPX 파서 벤치마크")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch", help="저장소에 없는 코퍼스 파일을 원 출처에서 받고 해시 확인")
    p_truth = sub.add_parser("truth", help="정답 생성 (검수된 정답은 건너뜀)")
    p_truth.add_argument("--only", help="문서 id 목록 (쉼표)")
    p_run = sub.add_parser("run", help="어댑터 실행 → 채점 → 순위표")
    p_run.add_argument("--adapters", help="어댑터 이름 목록 (쉼표). 생략하면 전부")
    p_run.add_argument("--only", help="문서 id 목록 (쉼표)")
    p_run.add_argument("--jobs", type=int, default=4)
    p_score = sub.add_parser("score", help="기존 실행 결과를 다시 채점하고 순위표 갱신")
    p_score.add_argument("run_dir", type=Path)
    args = parser.parse_args(argv)

    if args.cmd == "fetch":
        print(f"받은 파일 {corpus.fetch()}개")
    elif args.cmd == "truth":
        print(f"정답 {truth.build(_set(args.only))}개 생성")
    elif args.cmd == "run":
        run_dir = runner.run(_set(args.adapters), _set(args.only), args.jobs)
        _finish(run_dir)
    elif args.cmd == "score":
        _finish(args.run_dir)
    return 0


def _finish(run_dir: Path) -> None:
    score.score_run(run_dir)
    score.summarize(run_dir)
    print(report.write(run_dir))
    print(f"\n결과: {run_dir}")


if __name__ == "__main__":
    sys.exit(main())
