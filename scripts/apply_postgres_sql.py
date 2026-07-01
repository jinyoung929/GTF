#!/usr/bin/env python3
import os
import sys
from pathlib import Path

import psycopg


def split_sql(script: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_single_quote = False
    in_double_quote = False
    i = 0
    while i < len(script):
        char = script[i]
        next_char = script[i + 1] if i + 1 < len(script) else ""
        current.append(char)
        if char == "'" and not in_double_quote:
            if next_char == "'":
                current.append(next_char)
                i += 1
            else:
                in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        elif char == ";" and not in_single_quote and not in_double_quote:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        i += 1
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def main() -> int:
    database_url = os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL")
    if not database_url:
        print("DATABASE_URL or NEON_DATABASE_URL is required.", file=sys.stderr)
        return 2
    files = [Path(arg) for arg in sys.argv[1:]]
    if not files:
        print("Usage: apply_postgres_sql.py <sql-file> [<sql-file> ...]", file=sys.stderr)
        return 2
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for sql_file in files:
                script = sql_file.read_text(encoding="utf-8")
                statements = split_sql(script)
                for statement in statements:
                    cur.execute(statement)
                print(f"applied {sql_file}: {len(statements)} statements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
