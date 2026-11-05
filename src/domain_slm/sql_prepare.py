"""Prepare synthetic or provenance-tracked Text-to-SQL examples safely."""

import argparse
from collections import defaultdict
import hashlib
import json
import logging
import math
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import time
import tomllib
import unicodedata

LOG = logging.getLogger("domain_slm.sql_prepare")
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_COLUMN_TYPES = {"INTEGER", "REAL", "TEXT"}
_BLOCKED_FUNCTIONS = {
    "load_extension", "readfile", "writefile", "random", "randomblob",
    "changes", "last_insert_rowid", "total_changes",
}
_MAX_CONFIG_BYTES = 128 * 1024
_MAX_EXAMPLE_BYTES = 2 * 1024 * 1024
_MAX_DATABASE_BYTES = 1024 * 1024
_MAX_EXAMPLES = 5000
_MAX_DATABASES = 64
_MAX_TABLES = 32
_MAX_COLUMNS = 64
_MAX_ROWS_PER_TABLE = 20000
_MAX_QUERY_CHARS = 8192
_MAX_SCHEMA_PROMPT_CHARS = 32768
_MAX_RESULT_ROWS = 500
_MAX_RESULT_BYTES = 256 * 1024
_MAX_OUTPUT_BYTES = 16 * 1024 * 1024
_MAX_SQL_STEPS = 200_000
_SQL_TIMEOUT_SECONDS = 0.5
_TOTAL_SQL_VALIDATION_SECONDS = 30.0


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _read_limited(path, maximum):
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError(f"input exceeds the {maximum}-byte limit")
    return data


def _identifier(value, description):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{description} must be a simple SQLite identifier")
    return '"' + value + '"'


def _canonical_json(value):
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False,
                          sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("result must contain finite JSON values") from exc


def _validate_cell(value):
    if value is None or type(value) in (str, int):
        if isinstance(value, str) and len(value) > 4096:
            raise ValueError("fixture text values may not exceed 4096 characters")
        if type(value) is int and not -(2**63) <= value < 2**63:
            raise ValueError("fixture integers must fit SQLite's signed 64-bit range")
        return
    if type(value) is float and math.isfinite(value):
        return
    raise ValueError("fixture cells must be null, strings, integers, or finite numbers")


def _schema_tables(database_id, database_spec):
    if not isinstance(database_spec, dict) or set(database_spec) != {"tables"}:
        raise ValueError(f"database {database_id!r} must contain only a tables object")
    tables = database_spec["tables"]
    if not isinstance(tables, dict) or not tables or len(tables) > _MAX_TABLES:
        raise ValueError(f"database {database_id!r} must define 1–{_MAX_TABLES} tables")
    prepared = []
    for table_name in sorted(tables):
        quoted_table = _identifier(table_name, "table name")
        table = tables[table_name]
        if not isinstance(table, dict) or set(table) - {"columns", "rows"} or "columns" not in table:
            raise ValueError(f"table {table_name!r} requires columns and may contain rows")
        columns = table["columns"]
        if not isinstance(columns, list) or not columns or len(columns) > _MAX_COLUMNS:
            raise ValueError(f"table {table_name!r} must define 1–{_MAX_COLUMNS} columns")
        column_names = set()
        normalized_columns = []
        for column in columns:
            if not isinstance(column, dict) or set(column) != {"name", "type"}:
                raise ValueError(f"table {table_name!r} columns require name and type")
            name = column["name"]
            quoted_name = _identifier(name, "column name")
            if name in column_names:
                raise ValueError(f"table {table_name!r} has duplicate columns")
            column_names.add(name)
            column_type = column["type"]
            if not isinstance(column_type, str) or column_type.upper() not in _COLUMN_TYPES:
                raise ValueError(f"column {name!r} must use INTEGER, REAL, or TEXT")
            normalized_columns.append((name, quoted_name, column_type.upper()))
        rows = table.get("rows", [])
        if not isinstance(rows, list) or len(rows) > _MAX_ROWS_PER_TABLE:
            raise ValueError(f"table {table_name!r} has too many fixture rows")
        for row in rows:
            if not isinstance(row, list) or len(row) != len(normalized_columns):
                raise ValueError(f"table {table_name!r} fixture rows must match its columns")
            for cell in row:
                _validate_cell(cell)
        declaration = ", ".join(f"{quoted} {kind}" for _, quoted, kind in normalized_columns)
        prepared.append((table_name, quoted_table, normalized_columns, rows,
                         f"CREATE TABLE {quoted_table} ({declaration})"))
    return prepared


def _schema_prompt(tables):
    prompt = "\n".join(table[4] + ";" for table in tables)
    if len(prompt) > _MAX_SCHEMA_PROMPT_CHARS:
        raise ValueError("database schema prompt exceeds the size limit")
    return prompt


def execute_reference(database_spec, sql, *, total_deadline=None):
    """Run one bounded SELECT against a fixture-only, read-only SQLite DB."""
    if not isinstance(sql, str) or not sql.strip() or len(sql) > _MAX_QUERY_CHARS:
        raise ValueError("SQL reference must contain 1–8192 characters")
    if total_deadline is not None and time.monotonic() >= total_deadline:
        raise ValueError("total SQL validation budget exceeded")
    tables = _schema_tables("reference", database_spec)
    connection = sqlite3.connect(":memory:")
    allowed_tables = {table[0] for table in tables}
    try:
        connection.execute("PRAGMA trusted_schema = OFF")
        connection.execute("PRAGMA temp_store = MEMORY")
        for table_name, quoted_table, columns, rows, statement in tables:
            connection.execute(statement)
            if rows:
                placeholders = ", ".join("?" for _ in columns)
                connection.executemany(
                    f"INSERT INTO {quoted_table} VALUES ({placeholders})", rows,
                )
        connection.execute("PRAGMA query_only = ON")

        allowed_actions = {
            sqlite3.SQLITE_SELECT,
            sqlite3.SQLITE_READ,
            sqlite3.SQLITE_FUNCTION,
            getattr(sqlite3, "SQLITE_RECURSIVE", -1),
        }
        def authorize(action, arg1, arg2, database, trigger):
            if action == sqlite3.SQLITE_READ:
                return sqlite3.SQLITE_OK if arg1 in allowed_tables else sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_FUNCTION:
                function = (arg2 or arg1 or "").casefold()
                if function in _BLOCKED_FUNCTIONS:
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK if action in allowed_actions else sqlite3.SQLITE_DENY

        connection.set_authorizer(authorize)
        deadline = time.monotonic() + _SQL_TIMEOUT_SECONDS
        if total_deadline is not None:
            deadline = min(deadline, total_deadline)
        steps = [0]

        def interrupt_if_over_budget():
            steps[0] += 1000
            return int(steps[0] > _MAX_SQL_STEPS or time.monotonic() > deadline)

        connection.set_progress_handler(interrupt_if_over_budget, 1000)
        if total_deadline is not None and time.monotonic() >= total_deadline:
            raise ValueError("total SQL validation budget exceeded")
        cursor = connection.execute(sql)
        rows = cursor.fetchmany(_MAX_RESULT_ROWS + 1)
        if total_deadline is not None and time.monotonic() >= total_deadline:
            raise ValueError("total SQL validation budget exceeded")
        if len(rows) > _MAX_RESULT_ROWS:
            raise ValueError("SQL reference exceeded the result-row limit")
        values = [list(row) for row in rows]
        if len(_canonical_json(values)) > _MAX_RESULT_BYTES:
            raise ValueError("SQL reference exceeded the result-size limit")
        return values
    except sqlite3.Error as exc:
        raise ValueError(f"SQL reference was rejected or failed ({type(exc).__name__})") from None
    finally:
        connection.close()


def _normalized_question(question):
    return " ".join(unicodedata.normalize("NFKC", question).casefold().split())


def _split_databases(database_ids, seed, validation_fraction, test_fraction):
    if (type(seed) is not int or type(validation_fraction) not in (int, float) or
            type(test_fraction) not in (int, float) or
            not math.isfinite(validation_fraction) or not math.isfinite(test_fraction) or
            not 0 < validation_fraction < 1 or not 0 < test_fraction < 1 or
            validation_fraction + test_fraction >= 1):
        raise ValueError("split requires an integer seed and positive validation/test fractions totaling less than one")
    if len(database_ids) < 3 or len(database_ids) > _MAX_DATABASES:
        raise ValueError(f"dataset must use 3–{_MAX_DATABASES} distinct databases")
    ordered = sorted(database_ids, key=lambda item: _digest(f"{seed}\0{item}".encode("utf-8")))
    validation_count = max(1, int(len(ordered) * validation_fraction))
    test_count = max(1, int(len(ordered) * test_fraction))
    if validation_count + test_count >= len(ordered):
        raise ValueError("database split fractions leave no training databases")
    assignment = {}
    for database_id in ordered[:validation_count]:
        assignment[database_id] = "validation"
    for database_id in ordered[validation_count:validation_count + test_count]:
        assignment[database_id] = "test"
    for database_id in ordered[validation_count + test_count:]:
        assignment[database_id] = "train"
    return assignment


def prepare_sql(config_path, output):
    config_path = Path(config_path).resolve()
    config_bytes = _read_limited(config_path, _MAX_CONFIG_BYTES)
    config = tomllib.loads(config_bytes.decode("utf-8"))
    try:
        dataset = config["dataset"]
        split_config = config["split"]
        examples_path = (config_path.parent / dataset["examples"]).resolve()
        databases_path = (config_path.parent / dataset["databases"]).resolve()
        source_name, source_license = dataset["source"], dataset["license"]
        seed = split_config["seed"]
        validation_fraction = split_config["validation"]
        test_fraction = split_config["test"]
    except (KeyError, TypeError) as exc:
        raise ValueError("configuration requires dataset paths/provenance and split settings") from exc
    if (not isinstance(source_name, str) or not source_name.strip() or
            not isinstance(source_license, str) or not source_license.strip()):
        raise ValueError("dataset source and license/provenance must be nonempty")

    examples_bytes = _read_limited(examples_path, _MAX_EXAMPLE_BYTES)
    databases_bytes = _read_limited(databases_path, _MAX_DATABASE_BYTES)
    try:
        databases = json.loads(databases_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("database fixture file must be valid UTF-8 JSON") from exc
    if not isinstance(databases, dict) or not databases or len(databases) > _MAX_DATABASES:
        raise ValueError(f"database fixture must define 1–{_MAX_DATABASES} databases")

    examples = []
    seen_questions = set()
    referenced_database_ids = set()
    validation_deadline = time.monotonic() + _TOTAL_SQL_VALIDATION_SECONDS
    for line_number, line in enumerate(examples_bytes.decode("utf-8").splitlines(), 1):
        if not line.strip():
            raise ValueError(f"line {line_number}: blank record")
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(item, dict) or set(item) != {"db_id", "question", "sql", "expected"}:
            raise ValueError(f"line {line_number}: expected db_id, question, sql, and expected fields")
        database_id, question, sql, expected = item["db_id"], item["question"], item["sql"], item["expected"]
        if not isinstance(database_id, str) or database_id not in databases:
            raise ValueError(f"line {line_number}: unknown database id")
        if (not isinstance(question, str) or not question.strip() or len(question) > 4096 or
                not isinstance(sql, str) or not sql.strip() or len(sql) > _MAX_QUERY_CHARS):
            raise ValueError(f"line {line_number}: question or SQL is empty or exceeds its length limit")
        if not isinstance(expected, list) or any(not isinstance(row, list) for row in expected):
            raise ValueError(f"line {line_number}: expected must be an array of result rows")
        expected_bytes = _canonical_json(expected)
        if len(expected_bytes) > _MAX_RESULT_BYTES:
            raise ValueError(f"line {line_number}: expected result exceeds the size limit")
        question_key = (database_id, _normalized_question(question))
        if question_key in seen_questions:
            raise ValueError(f"line {line_number}: normalized duplicate question")
        seen_questions.add(question_key)
        referenced_database_ids.add(database_id)
        try:
            actual = execute_reference(databases[database_id], sql, total_deadline=validation_deadline)
        except ValueError as exc:
            raise ValueError(f"line {line_number}: {exc}") from exc
        if _canonical_json(actual) != expected_bytes:
            raise ValueError(f"line {line_number}: SQL result does not match the declared expected rows")
        identifier = _digest(f"{database_id}\0{_normalized_question(question)}".encode("utf-8"))
        tables = _schema_tables(database_id, databases[database_id])
        prompt = (
            "Translate the question into one SQLite SELECT statement. Return SQL only.\n\n"
            f"Schema:\n{_schema_prompt(tables)}\n\nQuestion: {question.strip()}"
        )
        if len(prompt) > _MAX_SCHEMA_PROMPT_CHARS + 4096:
            raise ValueError(f"line {line_number}: generated prompt exceeds the size limit")
        examples.append({
            "id": identifier,
            "db_id": database_id,
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": sql.strip()},
            ],
            "reference_result_sha256": _digest(expected_bytes),
        })

    if not examples or len(examples) > _MAX_EXAMPLES:
        raise ValueError(f"dataset must contain 1–{_MAX_EXAMPLES} examples")
    if referenced_database_ids != set(databases):
        raise ValueError("every configured database must be referenced by at least one example")
    assignment = _split_databases(
        sorted(referenced_database_ids), seed, validation_fraction, test_fraction,
    )
    partitions = {"train": [], "validation": [], "test": []}
    for example in examples:
        partitions[assignment[example["db_id"]]].append(example)

    payloads, split_summary = {}, {}
    for name, items in partitions.items():
        items.sort(key=lambda item: item["id"])
        payloads[name] = b"".join(
            (_canonical_json(item).decode("utf-8") + "\n").encode("utf-8") for item in items
        )
        split_summary[name] = {
            "examples": len(items),
            "database_ids": sorted({item["db_id"] for item in items}),
        }
    if sum(map(len, payloads.values())) > _MAX_OUTPUT_BYTES:
        raise ValueError("prepared output exceeds the total size limit")
    manifest = {
        "schema_version": 1,
        "source": source_name.strip(),
        "license": source_license.strip(),
        "split_unit": "database",
        "seed": seed,
        "reference_queries_validated": len(examples),
        "database_count": len(referenced_database_ids),
        "example_count": len(examples),
        "source_sha256": _digest(examples_bytes),
        "database_fixtures_sha256": _digest(databases_bytes),
        "config_sha256": _digest(config_bytes),
        "splits": split_summary,
        "files_sha256": {f"{name}.jsonl": _digest(data) for name, data in payloads.items()},
        "final_evaluation_ready": False,
    }

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    try:
        for name, data in payloads.items():
            (output / f"{name}.jsonl").write_bytes(data)
        (output / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
    except Exception:
        shutil.rmtree(output)
        raise
    LOG.info("Prepared %s SQL examples across %s database-isolated splits", len(examples), len(referenced_database_ids))
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="TOML configuration file")
    parser.add_argument("--output", required=True, help="New output directory; must not already exist")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        prepare_sql(args.config, args.output)
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        LOG.error("SQL preparation failed: %s", exc)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
