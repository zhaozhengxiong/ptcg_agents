"""Interactive helper that fetches card data and runs the IR pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

sys.path.append(str(Path(__file__).resolve().parents[2] / "auto-card-IR-gen"))

from auto_card_ir_gen import (  # noqa: E402  - local path injection happens above
    CompiledRule,
    PokemonTCGClient,
    RuleCompilationPipeline,
    RuleTemplateEngine,
    Storage,
)
from rules.engine import RuleEngine  # noqa: E402

try:  # pragma: no cover - optional import for nicer error messages
    import psycopg
except Exception:  # pragma: no cover - fallback to generic handling
    psycopg = None


@dataclass(slots=True)
class CardRequest:
    """User supplied card lookup parameters."""

    name: str
    set_code: str
    number: str


def _parse_card_line(line: str) -> CardRequest:
    parts = line.strip().split()
    if len(parts) < 3:
        raise ValueError(
            "Expected input in the form '<card name> <set code> <number>', received: " + line.strip()
        )
    number = parts[-1]
    set_code = parts[-2]
    name = " ".join(parts[:-2])
    if not name:
        raise ValueError("Card name cannot be empty")
    return CardRequest(name=name, set_code=set_code, number=number)


def _read_requests(initial: Iterable[str]) -> List[CardRequest]:
    requests: List[CardRequest] = []
    for line in initial:
        line = line.strip()
        if not line:
            continue
        requests.append(_parse_card_line(line))
    return requests


def _collect_requests_from_stdin() -> List[CardRequest]:
    if not sys.stdin.isatty():
        return _read_requests(sys.stdin)

    print("输入每张卡的名称、系列编码和编号，例如：'Pidgey MEW 16'。按回车结束。")
    lines: List[str] = []
    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        if not line.strip():
            break
        lines.append(line)
    return _read_requests(lines)


def _format_header(request: CardRequest, card_id: str) -> str:
    return f"=== {request.name} ({request.set_code} #{request.number}) -> {card_id} ==="


def _format_rule(compiled: CompiledRule) -> str:
    payload = compiled.rule.model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _format_raw_payload(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch cards and render their compiled IR")
    parser.add_argument(
        "cards",
        nargs="*",
        help="Card request lines formatted as '<name> <set code> <number>'",
    )
    parser.add_argument(
        "--database",
        default="postgresql://postgres@localhost:5432/pokemon",
        help=(
            "PostgreSQL URL used to persist raw payloads and compiled rules. "
            "Credentials can also be provided via POKEMON_DB_USER/POKEMON_DB_PASSWORD (or PGUSER/PGPASSWORD)."
        ),
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Optional PokemonTCG.io API key",
    )
    parser.add_argument(
        "--base-url",
        default="https://api.pokemontcg.io/v2",
        help="Override the PokemonTCG.io API base URL",
    )
    args = parser.parse_args(argv)

    if args.cards:
        requests = _read_requests(args.cards)
    else:
        requests = _collect_requests_from_stdin()

    if not requests:
        print("未提供卡牌信息，脚本结束。")
        return 0

    try:
        storage = Storage(args.database)
    except Exception as exc:  # pragma: no cover - interactive assistance
        if psycopg is not None and isinstance(exc, psycopg.OperationalError):
            print(
                "无法连接到 PostgreSQL 数据库。请在 --database URL 中提供用户名/密码，"
                "或设置 POKEMON_DB_USER 与 POKEMON_DB_PASSWORD (PGUSER/PGPASSWORD)。",
                file=sys.stderr,
            )
            return 2
        raise
    client = PokemonTCGClient(base_url=args.base_url, api_key=args.api_key)
    pipeline = RuleCompilationPipeline(
        client=client,
        storage=storage,
        template_engine=RuleTemplateEngine(),
        rule_engine=RuleEngine(),
    )

    for request in requests:
        try:
            card = client.search_card(request.name, request.set_code, request.number)
            result = pipeline.compile_card(str(card.get("id")))
        except Exception as exc:  # pragma: no cover - interactive best effort
            print(_format_header(request, "<not found>"))
            print(f"错误：{exc}")
            print()
            continue

        print(_format_header(request, result.card_id))
        print("-- 原始卡牌数据 --")
        print(_format_raw_payload(result.raw_payload))
        for compiled in result.rules:
            print("-- 解析后的 IR --")
            print(_format_rule(compiled))
            print(
                f"测试结果: {'通过' if compiled.tests.passed else '未通过'}"
                + (f" - {compiled.tests.details}" if compiled.tests.details else "")
            )
            print(f"存储状态: {compiled.storage_record.status}")
            if compiled.storage_record.reviewer:
                print(
                    f"审核人: {compiled.storage_record.reviewer}"
                    f" @ {compiled.storage_record.reviewed_at}"
                )
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
