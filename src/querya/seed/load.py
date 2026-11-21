import logging
from pathlib import Path

from sqlalchemy import create_engine, insert, make_url

from querya.seed.generate import Dataset
from querya.seed.schema import LOAD_ORDER, metadata

logger = logging.getLogger(__name__)

BATCH_SIZE = 5_000


def load_dataset(database_url: str, data: Dataset) -> dict[str, int]:
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(url)
    rows_by_table = dict(data.tables())
    counts: dict[str, int] = {}
    try:
        with engine.begin() as conn:
            metadata.drop_all(conn)
            metadata.create_all(conn)
            for table in LOAD_ORDER:
                rows = rows_by_table[table.name]
                for start in range(0, len(rows), BATCH_SIZE):
                    conn.execute(insert(table), rows[start : start + BATCH_SIZE])
                counts[table.name] = len(rows)
                logger.info("loaded %s: %d rows", table.name, len(rows))
    finally:
        engine.dispose()
    return counts
