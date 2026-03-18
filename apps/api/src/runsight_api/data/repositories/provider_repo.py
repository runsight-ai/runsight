from sqlmodel import Session, select
from typing import List, Optional
from ...domain.entities.provider import Provider


class ProviderRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_all(self) -> List[Provider]:
        statement = select(Provider)
        return list(self.session.exec(statement).all())

    def get_by_id(self, provider_id: str) -> Optional[Provider]:
        return self.session.get(Provider, provider_id)

    def get_by_type(self, provider_type: str) -> Optional[Provider]:
        statement = select(Provider).where(
            Provider.type == provider_type, Provider.is_active.is_(True)
        )
        return self.session.exec(statement).first()

    def create(self, provider: Provider) -> Provider:
        self.session.add(provider)
        self.session.commit()
        self.session.refresh(provider)
        return provider

    def update(self, provider: Provider) -> Provider:
        self.session.add(provider)
        self.session.commit()
        self.session.refresh(provider)
        return provider

    def delete(self, provider_id: str) -> bool:
        provider = self.get_by_id(provider_id)
        if provider:
            self.session.delete(provider)
            self.session.commit()
            return True
        return False
