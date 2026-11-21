from functools import cached_property
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Engine, inspect

from querya.db.engine import to_jsonable


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    primary_key: bool


class ForeignKeyInfo(BaseModel):
    columns: list[str]
    references_table: str
    references_columns: list[str]


class TableSummary(BaseModel):
    name: str
    row_count: int
    columns: list[str]


class TableDetail(BaseModel):
    name: str
    row_count: int
    columns: list[ColumnInfo]
    foreign_keys: list[ForeignKeyInfo]
    sample_rows: list[dict[str, Any]]


class UnknownTableError(LookupError):
    pass


class SchemaCatalog:
    """Cached view of the analytics schema. The dataset is static, so one read is enough."""

    def __init__(self, engine: Engine, *, sample_size: int = 3) -> None:
        self.engine = engine
        self.sample_size = sample_size

    @cached_property
    def _details(self) -> dict[str, TableDetail]:
        insp = inspect(self.engine)
        quote = self.engine.dialect.identifier_preparer.quote
        details: dict[str, TableDetail] = {}
        with self.engine.connect() as conn:
            for name in sorted(insp.get_table_names()):
                if name.startswith("sqlite_"):
                    continue
                pk = set(insp.get_pk_constraint(name).get("constrained_columns") or [])
                columns = [
                    ColumnInfo(
                        name=c["name"],
                        type=str(c["type"]),
                        nullable=bool(c.get("nullable", True)),
                        primary_key=c["name"] in pk,
                    )
                    for c in insp.get_columns(name)
                ]
                fks = [
                    ForeignKeyInfo(
                        columns=fk["constrained_columns"],
                        references_table=fk["referred_table"],
                        references_columns=fk["referred_columns"],
                    )
                    for fk in insp.get_foreign_keys(name)
                ]
                table = quote(name)
                count = conn.exec_driver_sql(f"SELECT COUNT(*) FROM {table}").scalar_one()
                sample = conn.exec_driver_sql(
                    f"SELECT * FROM {table} LIMIT {int(self.sample_size)}"
                ).mappings()
                details[name] = TableDetail(
                    name=name,
                    row_count=int(count),
                    columns=columns,
                    foreign_keys=fks,
                    sample_rows=[{k: to_jsonable(v) for k, v in row.items()} for row in sample],
                )
            conn.rollback()
        return details

    @property
    def table_names(self) -> list[str]:
        return list(self._details)

    def summaries(self) -> list[TableSummary]:
        return [
            TableSummary(name=t.name, row_count=t.row_count, columns=[c.name for c in t.columns])
            for t in self._details.values()
        ]

    def describe(self, table: str) -> TableDetail:
        key = table.strip().strip('"`[]').lower()
        for name, detail in self._details.items():
            if name.lower() == key:
                return detail
        raise UnknownTableError(
            f"Unknown table {table!r}. Available tables: {', '.join(self.table_names)}"
        )

    def all_tables(self) -> list[TableDetail]:
        return list(self._details.values())
