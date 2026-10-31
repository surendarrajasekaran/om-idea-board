"""Version-one, additive migration. Run once per release before starting the API."""

import os
import re
import sys

from sqlalchemy import text

from .database import make_engine
from .models import Base


def configure_application_role(connection):
    """The runtime role can read/insert ideas, never migrate or administer the DB."""
    username = os.environ.get("APP_DATABASE_USER")
    password = os.environ.get("APP_DATABASE_PASSWORD")
    if not username and not password:
        return  # Local Compose keeps its existing single-role development setup.
    if (
        not username
        or not password
        or not re.fullmatch(r"[a-z][a-z0-9_]{0,30}", username)
    ):
        raise ValueError("Configure a safe APP_DATABASE_USER and APP_DATABASE_PASSWORD")
    if len(password) < 24:
        raise ValueError(
            "Application database password must have at least 24 characters"
        )
    if connection.dialect.name != "postgresql":
        raise ValueError("Application roles require PostgreSQL")
    from psycopg import sql

    # psycopg quotes identifiers and password literals; no SQL/string interpolation.
    with connection.connection.driver_connection.cursor() as cursor:
        cursor.execute("SELECT current_user, current_database()")
        administrator, database = cursor.fetchone()
        if username == administrator:
            raise ValueError("Application and migration users must differ")
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (username,))
        if not cursor.fetchone():
            cursor.execute(sql.SQL("CREATE ROLE {}").format(sql.Identifier(username)))
        cursor.execute(
            "SELECT rolsuper, rolreplication, rolbypassrls FROM pg_roles WHERE rolname = %s",
            (username,),
        )
        if any(cursor.fetchone()):
            raise ValueError("Refuse to reuse a privileged application role")
        cursor.execute(
            "SELECT 1 FROM pg_auth_members WHERE member = (SELECT oid FROM pg_roles WHERE rolname = %s)",
            (username,),
        )
        if cursor.fetchone():
            raise ValueError("Application role must not inherit or assume other roles")
        cursor.execute(
            sql.SQL(
                "ALTER ROLE {} LOGIN NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD {}"
            ).format(sql.Identifier(username), sql.Literal(password))
        )
        cursor.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database), sql.Identifier(username)
            )
        )
        cursor.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        cursor.execute(
            "SELECT has_schema_privilege(%s, 'public', 'CREATE')", (username,)
        )
        if cursor.fetchone()[0]:
            raise ValueError(
                "The database owner must revoke PUBLIC schema creation rights"
            )
        cursor.execute(
            sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                sql.Identifier(username)
            )
        )
        cursor.execute(
            sql.SQL("GRANT SELECT, INSERT ON TABLE public.ideas TO {}").format(
                sql.Identifier(username)
            )
        )
        cursor.execute("SELECT pg_get_serial_sequence('public.ideas', 'id')")
        sequence = cursor.fetchone()[0]
        if sequence:
            cursor.execute(
                sql.SQL("GRANT USAGE, SELECT ON SEQUENCE {} TO {}").format(
                    sql.Identifier(*sequence.split(".")), sql.Identifier(username)
                )
            )


def main():
    engine = make_engine(migration=True)
    try:
        with engine.begin() as connection:
            # Serialize migrations across concurrently starting Compose containers/jobs.
            if engine.dialect.name == "postgresql":
                connection.execute(text("SELECT pg_advisory_xact_lock(813729)"))
            Base.metadata.create_all(connection)
            configure_application_role(connection)
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"Migration failed ({type(exc).__name__}); inspect database access and schema",
            file=sys.stderr,
        )
        sys.exit(1)
