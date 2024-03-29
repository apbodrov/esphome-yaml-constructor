from typing import Union
from uuid import UUID

from sqlalchemy import select, update, and_, delete, null
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, Config, User_Config


async def _create_entity(db_session: AsyncSession, entity):
    db_session.add(entity)
    await db_session.flush()
    return entity


async def _execute_query_and_fetchone(res):
    row = res.fetchone()
    if row is not None:
        return row[0]


async def _execute_query_and_fetchall(res):
    rows = res.fetchall()
    if rows is not None:
        return rows


async def _execute_delete_query(db_session: AsyncSession, query):
    await db_session.execute(query)
    await db_session.commit()


class ConfigDAL:

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create_yaml_config(self, name_esphome: str = None, hash_yaml: str = None, platform: str = None, config_json: str = None):
        new_yaml_config = Config(
            name_esphome=name_esphome,
            hash_yaml=hash_yaml,
            platform=platform,
            config_json=config_json
        )
        return await _create_entity(self.db_session, new_yaml_config)

    async def delete_yaml_config(self, name_config: str):
        query = delete(Config).where(Config.name_config == name_config)
        await _execute_delete_query(self.db_session, query)
        return "Config deleted"

    async def get_config(self, hash_yaml: str = None, name_config: UUID = None) -> Union[Config, None]:
        query = None
        if hash_yaml:
            query = select(Config).where(Config.hash_yaml == hash_yaml)
        elif name_config:
            query = select(Config).where(Config.name_config == name_config)
        if query is not None:
            return await _execute_query_and_fetchone(await self.db_session.execute(query))
        return None

    async def update_yaml_config(self, name_config: str) -> Union[Config, None]:
        query = (
            update(Config)
            .where(Config.name_config == name_config)
            .values(compile_test=True)
            .returning(Config.name_config)
        )
        return await _execute_query_and_fetchone(await self.db_session.execute(query))

    async def update_config_json(self, hash_yaml: str, config_json: str):
        query = (
            update(Config)
            .where(Config.hash_yaml == hash_yaml)
            .values(config_json=config_json)
            .returning(Config.name_config)
        )
        return await _execute_query_and_fetchone(await self.db_session.execute(query))

    async def update_config(self, hash_yaml: str, name_esphome: str, platform: str):
        query = (
            update(Config)
            .where(Config.hash_yaml == hash_yaml)
            .values(name_esphome=name_esphome, platform=platform)
            .returning(Config.name_config)
        )
        return await _execute_query_and_fetchone(await self.db_session.execute(query))


class FavouritesDAL:

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create_favourites(self, user_id: UUID, name_config: UUID, name_esphome: str):
        new_favourites = User_Config(
            user_id=user_id,
            name_config=name_config,
            name_esphome=name_esphome
        )
        return await _create_entity(self.db_session, new_favourites)

    async def get_favourites_all(self, user_id: UUID):
        query = select(User_Config).where(User_Config.user_id == user_id)
        return await _execute_query_and_fetchall(await self.db_session.execute(query))

    async def get_favourites_by_name_config(self, user_id: UUID, name_config: UUID):
        query = select(User_Config).where(
            and_(User_Config.user_id == user_id, User_Config.name_config == name_config))
        return await _execute_query_and_fetchone(await self.db_session.execute(query))

    async def delete_favourites(self, user_id: UUID, name_config: UUID):
        query = delete(User_Config).where(
            and_(User_Config.name_config == name_config, User_Config.user_id == user_id))
        await _execute_delete_query(self.db_session, query)
        return "favourites deleted"


class GoogleDAL:

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create_user(
            self, user_id: str, name: str, surname: str, email: str
    ) -> User:
        new_user = User(
            user_id=user_id, name=name, surname=surname, email=email
        )
        return await _create_entity(self.db_session, new_user)

    async def get_google_user(self, email: str) -> Union[User, None]:
        query = select(User).where(User.email == email)
        return await _execute_query_and_fetchone(await self.db_session.execute(query))
