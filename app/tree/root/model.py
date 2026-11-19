from google.cloud.firestore_v1.async_client import AsyncClient
from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from dataclasses import dataclass

from pydantic import(
  BaseModel,
  Field
)

import redis.asyncio as redis
from redis.typing import ExpiryT

from uuid import UUID

from app.tree.soil.typing import UTCTimestampT
from app.tree.water.enum import UpsertStrEnum
from app.tree.water.config import(
  GCP_NAMING_PATTERN,
  TAISettings
)

class RecordBase(BaseModel):
  created_by:str=Field(pattern=GCP_NAMING_PATTERN)
  created_at:UTCTimestampT
  updated_by:str=Field(pattern=GCP_NAMING_PATTERN)
  updated_at:UTCTimestampT
  auth_uid:str|None=None

@dataclass(kw_only=True)
class RedisBase:
  redis_client:redis.Redis
  settings:TAISettings

  async def get_locked(
    self,
    name:UUID,
    ex:ExpiryT
  )->bool:
    return await self.redis_client.set(
      name=f'lock:{str(name)}',
      value=1,
      nx=True,
      ex=ex
    ) is True

@dataclass(kw_only=True)
class FirestoreBase:
  firestore_client:AsyncClient
  settings:TAISettings
  
  def set_firestore_doc_base(
    self,
    doc_dict:dict,
    upsert:UpsertStrEnum
  )->dict:
    doc_dict.update({
      'updated_by': self.settings.service_account,
      'updated_at': SERVER_TIMESTAMP
    })

    if upsert==UpsertStrEnum.INSERT:
      doc_dict.update({
        'created_by': self.settings.service_account,
        'created_at': SERVER_TIMESTAMP
      })
    
    return doc_dict