"""Exercise real PostgreSQL grants using CI's disposable database."""

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.migrate import main as migrate


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", "").startswith("postgresql"),
    reason="Requires disposable PostgreSQL",
)
@pytest.mark.parametrize("managed_administrator", [False, True])
def test_runtime_role_cannot_modify_schema_or_delete_ideas(
    monkeypatch, managed_administrator
):
    url = make_url(os.environ["TEST_DATABASE_URL"])
    username = "app_test_" + uuid.uuid4().hex[:12]
    password = uuid.uuid4().hex
    from psycopg import sql

    owner = create_engine(url, isolation_level="AUTOCOMMIT")
    migration_role = "migration_" + uuid.uuid4().hex[:12]
    test_database = "role_db_" + uuid.uuid4().hex[:12]
    if managed_administrator:
        with owner.connect() as connection:
            with connection.connection.driver_connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN CREATEROLE CREATEDB PASSWORD {}"
                    ).format(sql.Identifier(migration_role), sql.Literal(password))
                )
                cursor.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier(test_database), sql.Identifier(migration_role)
                    )
                )
        url = url.set(
            username=migration_role, password=password, database=test_database
        )
    monkeypatch.setenv("DATABASE_URL", str(url.render_as_string(hide_password=False)))
    monkeypatch.setenv("APP_DATABASE_USER", username)
    monkeypatch.setenv("APP_DATABASE_PASSWORD", password)
    admin = create_engine(url)
    runtime = create_engine(url.set(username=username, password=password))
    try:
        migrate()
        migrate()  # Role and schema configuration must be repeatable.
        with runtime.begin() as connection:
            connection.execute(
                text("INSERT INTO ideas(content) VALUES ('role verification')")
            )
            assert connection.execute(text("SELECT count(*) FROM ideas")).scalar() >= 1
        for statement in [
            "DELETE FROM ideas",
            "UPDATE ideas SET content = 'bad'",
            "DROP TABLE ideas",
            "CREATE TABLE forbidden (id int)",
        ]:
            with pytest.raises(DBAPIError), runtime.begin() as connection:
                connection.execute(text(statement))
        with admin.connect() as connection:
            flags = connection.execute(
                text(
                    "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication FROM pg_roles WHERE rolname = :name"
                ),
                {"name": username},
            ).one()
            assert not any(flags)
    finally:
        runtime.dispose()
        # The role owns no objects; remove only this test's grants and role.
        cleanup = create_engine(
            make_url(os.environ["TEST_DATABASE_URL"]).set(database=url.database)
        )
        with cleanup.begin() as connection:
            from psycopg import sql

            with connection.connection.driver_connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("DROP OWNED BY {}").format(sql.Identifier(username))
                )
                cursor.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(username)))
            connection.execute(
                text("DELETE FROM ideas WHERE content = 'role verification'")
            )
        cleanup.dispose()
        admin.dispose()
        if managed_administrator:
            with owner.connect() as connection:
                with connection.connection.driver_connection.cursor() as cursor:
                    cursor.execute(
                        sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                            sql.Identifier(test_database)
                        )
                    )
                    cursor.execute(
                        sql.SQL("DROP ROLE {}").format(sql.Identifier(migration_role))
                    )
        owner.dispose()
