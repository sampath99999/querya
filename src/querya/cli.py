import argparse
import logging

from querya.config import get_settings
from querya.logging_setup import configure_logging

logger = logging.getLogger("querya")


def _cmd_seed(args: argparse.Namespace) -> None:
    from querya.seed import SeedConfig, generate, load_dataset

    url = args.url or get_settings().database_url
    data = generate(SeedConfig(seed=args.seed, customers=args.customers))
    counts = load_dataset(url, data)
    logger.info("seeded %s with %d rows", url, sum(counts.values()))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="querya")
    sub = parser.add_subparsers(dest="command", required=True)

    seed = sub.add_parser("seed", help="Generate the sample retail dataset and load it")
    seed.add_argument("--url", help="Target database URL (defaults to QUERYA_DATABASE_URL)")
    seed.add_argument("--seed", type=int, default=42)
    seed.add_argument("--customers", type=int, default=4_000)
    seed.set_defaults(func=_cmd_seed)
    return parser


def main(argv: list[str] | None = None) -> None:
    configure_logging(get_settings().log_level)
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
