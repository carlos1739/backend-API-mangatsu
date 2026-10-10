import os
from typing import Any

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor


def koneksi() -> Connection:
    """Create a connection to the MySQL database."""
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "perpustakaan"),
        cursorclass=DictCursor,
        autocommit=False,
    )


def execute_query(
    sql: str,
    params: tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    connection = koneksi()
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()
    finally:
        connection.close()


def execute_write(
    sql: str,
    params: tuple[Any, ...] = (),
) -> int:
    connection = koneksi()
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            lastrowid = cursor.lastrowid or 0
        connection.commit()
        return lastrowid
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
