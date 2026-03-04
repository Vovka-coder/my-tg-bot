"""
RefLens — Base Repository
Базовый CRUD-репозиторий. Коммит — на уровне сервиса или хендлера.
"""
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):

    def __init__(self, session: AsyncSession, model: Type[ModelType]) -> None:
        self.session = session
        self.model = model

    async def create(self, **kwargs: Any) -> ModelType:
        """Создать запись. flush() — без коммита."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def get(self, **filters: Any) -> Optional[ModelType]:
        """Получить одну запись по фильтрам."""
        result = await self.session.execute(
            select(self.model).filter_by(**filters)
        )
        return result.scalar_one_or_none()

    async def get_many(
        self,
        *where_clauses: Any,
        offset: int = 0,
        limit: int = 100,
        order_by: Any = None,
    ) -> List[ModelType]:
        """Получить список записей."""
        query = select(self.model)
        if where_clauses:
            query = query.where(*where_clauses)
        if order_by is not None:
            query = query.order_by(order_by)
        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(
        self, record_id: int, values: Dict[str, Any]
    ) -> Optional[ModelType]:
        """Обновить запись по id и вернуть обновлённую."""
        result = await self.session.execute(
            update(self.model)
            .where(self.model.id == record_id)
            .values(**values)
            .returning(self.model)
        )
        await self.session.flush()
        return result.scalar_one_or_none()

    async def delete_by(self, **filters: Any) -> int:
        """Удалить записи по фильтрам. Возвращает количество удалённых."""
        result = await self.session.execute(
            delete(self.model).filter_by(**filters)
        )
        await self.session.flush()
        return result.rowcount

    async def exists(self, **filters: Any) -> bool:
        """Проверить существование записи."""
        result = await self.session.execute(
            select(self.model).filter_by(**filters).limit(1)
        )
        return result.first() is not None
