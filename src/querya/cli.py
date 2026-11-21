import argparse
import asyncio
import logging
import sys

from querya.config import get_settings
from querya.logging_setup import configure_logging

logger = logging.getLogger("querya")


def _out(line: str = "") -> None:
    sys.stdout.write(line + "\n")


def _cmd_seed(args: argparse.Namespace) -> None:
    from querya.seed import SeedConfig, generate, load_dataset

    url = args.url or get_settings().database_url
    data = generate(SeedConfig(seed=args.seed, customers=args.customers))
    counts = load_dataset(url, data)
    logger.info("seeded %s with %d rows", url, sum(counts.values()))


def _cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run(
        "querya.api:app_factory", factory=True, host=args.host, port=args.port, reload=args.reload
    )


def _cmd_ask(args: argparse.Namespace) -> None:
    from querya.runtime import build_runtime
    from querya.service import AskService
    from querya.tracing import TraceStore

    settings = get_settings()
    runtime = build_runtime(settings)
    store = TraceStore(settings.trace_database_url)
    service = AskService(
        runtime.agent, store, provider=runtime.llm.provider, model=runtime.llm.model
    )
    try:
        run_id, result = asyncio.run(service.ask(args.question))
    finally:
        runtime.close()
        store.close()
    if result is None:
        raise SystemExit(f"run {run_id} crashed, see the logs")
    _out(f"run:    {run_id} ({result.status}, {result.latency_ms / 1000:.1f}s)")
    _out(f"answer: {result.answer or result.error}")
    if result.sql:
        _out(f"sql:    {result.sql}")
    if result.columns:
        _out(" | ".join(result.columns))
        for row in result.rows[:20]:
            _out(" | ".join(str(v) for v in row))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="querya")
    sub = parser.add_subparsers(dest="command", required=True)

    seed = sub.add_parser("seed", help="Generate the sample retail dataset and load it")
    seed.add_argument("--url", help="Target database URL (defaults to QUERYA_DATABASE_URL)")
    seed.add_argument("--seed", type=int, default=42)
    seed.add_argument("--customers", type=int, default=4_000)
    seed.set_defaults(func=_cmd_seed)

    serve = sub.add_parser("serve", help="Run the API server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    serve.set_defaults(func=_cmd_serve)

    ask = sub.add_parser("ask", help="Ask one question from the terminal")
    ask.add_argument("question")
    ask.set_defaults(func=_cmd_ask)
    return parser


def main(argv: list[str] | None = None) -> None:
    configure_logging(get_settings().log_level)
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
