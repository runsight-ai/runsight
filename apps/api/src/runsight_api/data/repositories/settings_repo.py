from sqlmodel import Session, select
from typing import List, Optional
from ...domain.entities.settings import AppSettings, FallbackChain, ModelDefault


class SettingsRepository:
    def __init__(self, session: Session):
        self.session = session

    # AppSettings
    def get_setting(self, key: str) -> Optional[AppSettings]:
        return self.session.get(AppSettings, key)

    def set_setting(self, setting: AppSettings) -> AppSettings:
        self.session.merge(setting)
        self.session.commit()
        refreshed = self.session.get(AppSettings, setting.key)
        return refreshed  # type: ignore[return-value]

    def list_settings(self) -> List[AppSettings]:
        statement = select(AppSettings)
        return list(self.session.exec(statement).all())

    # FallbackChain
    def get_fallback_chain(self) -> List[FallbackChain]:
        statement = select(FallbackChain).order_by(FallbackChain.position)
        return list(self.session.exec(statement).all())

    def update_fallback_chain(self, chain: List[FallbackChain]) -> List[FallbackChain]:
        # Delete existing
        existing = self.session.exec(select(FallbackChain)).all()
        for item in existing:
            self.session.delete(item)

        # Add new
        for item in chain:
            self.session.add(item)

        self.session.commit()
        return self.get_fallback_chain()

    # ModelDefault
    def list_model_defaults(self) -> List[ModelDefault]:
        statement = select(ModelDefault)
        return list(self.session.exec(statement).all())

    def set_model_default(self, default_model: ModelDefault) -> ModelDefault:
        self.session.add(default_model)
        self.session.commit()
        self.session.refresh(default_model)
        return default_model
