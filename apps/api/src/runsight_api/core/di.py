from sqlmodel import create_engine
from .config import settings

# SQLite :memory: needs check_same_thread=False for TestClient/async usage
connect_args = {}
if ":memory:" in settings.db_url:
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.db_url,
    echo=settings.debug,
    connect_args=connect_args if connect_args else {},
)


class Container:
    def __init__(self):
        self.engine = engine

    def setup_app_state(self, app):
        pass


container = Container()
