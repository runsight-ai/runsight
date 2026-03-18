"""Red tests for RUN-127: ProviderRepository.get_by_type() method.

The ticket requires adding a get_by_type() method to ProviderRepository
that finds the first active provider of a given type (e.g., 'openai').
"""

from unittest.mock import Mock


class TestProviderRepoGetByType:
    def test_get_by_type_method_exists(self):
        """ProviderRepository must have a get_by_type() method."""
        from runsight_api.data.repositories.provider_repo import ProviderRepository

        session = Mock()
        repo = ProviderRepository(session)
        assert hasattr(repo, "get_by_type")
        assert callable(repo.get_by_type)

    def test_get_by_type_returns_matching_provider(self):
        """get_by_type('openai') returns first active provider of type 'openai'."""
        from runsight_api.data.repositories.provider_repo import ProviderRepository
        from runsight_api.domain.entities.provider import Provider

        # Create a real session with in-memory SQLite
        from sqlmodel import Session, SQLModel, create_engine

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            provider = Provider(
                id="prov_1",
                name="My OpenAI",
                type="openai",
                api_key_encrypted="encrypted",
                is_active=True,
            )
            session.add(provider)
            session.commit()

            repo = ProviderRepository(session)
            result = repo.get_by_type("openai")

            assert result is not None
            assert result.type == "openai"
            assert result.id == "prov_1"

    def test_get_by_type_returns_none_when_no_match(self):
        """get_by_type returns None when no provider of that type exists."""
        from runsight_api.data.repositories.provider_repo import ProviderRepository

        from sqlmodel import Session, SQLModel, create_engine

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            repo = ProviderRepository(session)
            result = repo.get_by_type("anthropic")
            assert result is None

    def test_get_by_type_returns_only_active_provider(self):
        """get_by_type skips inactive providers."""
        from runsight_api.data.repositories.provider_repo import ProviderRepository
        from runsight_api.domain.entities.provider import Provider

        from sqlmodel import Session, SQLModel, create_engine

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            inactive = Provider(
                id="prov_inactive",
                name="Old OpenAI",
                type="openai",
                api_key_encrypted="enc",
                is_active=False,
            )
            session.add(inactive)
            session.commit()

            repo = ProviderRepository(session)
            result = repo.get_by_type("openai")
            assert result is None
