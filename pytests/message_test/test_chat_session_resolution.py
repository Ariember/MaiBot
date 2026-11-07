from contextlib import contextmanager
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
import pytest

from src.chat.message_receive.chat_manager import BotChatSession, ChatManager
from src.common.database.database_model import ChatSession
from src.platform_io import DriverKind, RouteKey
from src.services import bot_account_service
import src.platform_io as platform_io

session_module = import_module("src.chat.message_receive.chat_manager")


@pytest.fixture
def session_database(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine, tables=[ChatSession.__table__])

    @contextmanager
    def get_session():
        with Session(engine) as session:
            yield session
            session.commit()

    monkeypatch.setattr(session_module, "get_db_session", get_session)
    yield engine
    engine.dispose()


def test_private_target_does_not_include_old_group_sender(session_database):
    with Session(session_database) as session:
        session.add_all(
            [
                ChatSession(session_id="group", platform="qq", group_id="100", user_id="200"),
                ChatSession(session_id="private", platform="qq", user_id="200"),
            ]
        )
        session.commit()
    manager = ChatManager()

    for _ in range(2):
        assert manager.resolve_session_ids_by_target(platform="qq", target_id="200", chat_type="private") == {"private"}
        assert manager.resolve_session_ids_by_target(platform="qq", target_id="100", chat_type="group") == {"group"}


@pytest.mark.asyncio
async def test_open_reuses_real_route_and_ignores_accountless_legacy_stream(session_database):
    manager = ChatManager()
    legacy = BotChatSession(session_id="legacy", platform="qq", group_id="100")
    real = BotChatSession(session_id="real", platform="qq", group_id="100", account_id="bot", scope="adapter")
    manager.sessions = {session.session_id: session for session in (legacy, real)}

    session, created = await manager.open_session(platform="qq", group_id="100")

    assert session is real
    assert not created


@pytest.mark.asyncio
async def test_open_ambiguous_target_requires_explicit_route(session_database):
    manager = ChatManager()
    for account in ("bot-a", "bot-b"):
        manager.sessions[account] = BotChatSession(
            session_id=account,
            platform="qq",
            group_id="100",
            account_id=account,
            scope="adapter",
        )

    with pytest.raises(ValueError, match="多个聊天流"):
        await manager.open_session(platform="qq", group_id="100")
    session, created = await manager.open_session(platform="qq", group_id="100", account_id="bot-a")
    assert session.session_id == "bot-a"
    assert not created


@pytest.mark.asyncio
async def test_open_new_target_inherits_unique_plugin_scope(session_database, monkeypatch):
    monkeypatch.setattr(bot_account_service, "get_bot_accounts", lambda platform: {"bot"})
    drivers = [
        SimpleNamespace(descriptor=SimpleNamespace(kind=kind, route_key=route))
        for kind, route in (
            (DriverKind.PLUGIN, RouteKey("qq", "bot", "adapter")),
            (DriverKind.LEGACY, RouteKey("qq", "bot")),
        )
    ]
    monkeypatch.setattr(
        platform_io,
        "get_platform_io_manager",
        lambda: SimpleNamespace(
            driver_registry=SimpleNamespace(list=Mock(return_value=drivers)),
        ),
    )
    manager = ChatManager()

    session, created = await manager.open_session(platform="qq", group_id="100")
    reopened, reopened_created = await manager.open_session(platform="qq", group_id="100")

    assert created and not reopened_created
    assert reopened is session
    assert (session.account_id, session.scope) == ("bot", "adapter")
    with Session(session_database) as db_session:
        saved = db_session.get(ChatSession, 1)
        assert saved.session_id == session.session_id
        assert (saved.account_id, saved.scope) == ("bot", "adapter")


@pytest.mark.parametrize("accounts", [set(), {"bot-a", "bot-b"}])
def test_new_target_rejects_missing_or_ambiguous_account(monkeypatch, accounts):
    monkeypatch.setattr(bot_account_service, "get_bot_accounts", lambda platform: accounts)
    monkeypatch.setattr(
        platform_io,
        "get_platform_io_manager",
        lambda: SimpleNamespace(
            driver_registry=SimpleNamespace(list=Mock(return_value=[])),
        ),
    )

    with pytest.raises(ValueError, match="account_id"):
        ChatManager._resolve_new_session_route("qq", None, None)


@pytest.mark.asyncio
async def test_database_failure_does_not_create_a_second_stream(monkeypatch):
    manager = ChatManager()
    monkeypatch.setattr(session_module, "get_db_session", Mock(side_effect=RuntimeError("database unavailable")))
    create = Mock()
    monkeypatch.setattr(manager, "_get_or_create_session", create)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await manager.open_session(platform="qq", user_id="200", account_id="bot")

    create.assert_not_called()
