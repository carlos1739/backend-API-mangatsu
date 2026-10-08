import os
from typing import Any, Optional

import pymysql


def koneksi() -> pymysql.connections.Connection:
    """Create a connection to the MySQL database managed through phpMyAdmin."""
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3307")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "perpustakaan"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def execute_query(
    sql: str,
    params: Optional[tuple[Any, ...]] = None,
) -> list[dict[str, Any]]:
    connection = koneksi()
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, params or ())
            return cursor.fetchall()
    finally:
        connection.close()


def execute_write(
    sql: str,
    params: Optional[tuple[Any, ...]] = None,
) -> int:
    connection = koneksi()
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, params or ())
        connection.commit()
        return cursor.lastrowid or 0
    finally:
        connection.close()
