"""Version-one, additive migration. Run once per release before starting the API."""

from sqlalchemy import text

from .database import make_engine
from .models import Base


def main():
    engine = make_engine()
    try:
        with engine.begin() as connection:
            # Serialize migrations across concurrently starting Compose containers/jobs.
            if engine.dialect.name == "postgresql":
                connection.execute(text("SELECT pg_advisory_xact_lock(813729)"))
            Base.metadata.create_all(connection)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
