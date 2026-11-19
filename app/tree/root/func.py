from fastapi import(
  Request,
  Header,
  HTTPException,
  status
)

from typing import(
  Any,
  Callable,
  Coroutine,
  Annotated,
  Literal
)

from uuid import(
  UUID,
  uuid4,
  uuid5,
  NAMESPACE_DNS
)

import asyncio

import logfire

from pathlib import Path

from dataclasses import dataclass

from google.cloud import storage
from google.cloud.firestore_v1.async_client import AsyncClient as FirestoreAsyncClient

from firebase_admin import auth

from qdrant_client import AsyncQdrantClient

from datetime import(
  datetime,
  timezone,
  timedelta
)

import redis.asyncio as redis

from app.tree.water.config import (
  TAISettings,
  QdrantSetting,
  OtherSertting
)

_DOMAIN='themselves.ai'
_NAMESPACE=uuid5(NAMESPACE_DNS,_DOMAIN)

@dataclass(frozen=True)
class LifeSpanResources:
  settings:TAISettings
  storage_client:storage.Client
  firestore_client:FirestoreAsyncClient
  qdrant_client:AsyncQdrantClient
  redis_client:redis.Redis
  google_auth_credentials:Any

def get_filenames(
  dir_path:str,
  file_suffix:Literal['yaml']
)->list[str]:
  return [f.stem for f in Path(dir_path).glob(f'*.{file_suffix}')]

def get_life_span_resources(request:Request)->LifeSpanResources:
  # return request.state.resources
  return request.app.state.resources

def generate_uuid(value:str|None=None)->UUID:
  if value:
    uuid=uuid5(_NAMESPACE,value)
  else:
    uuid=uuid4()
  
  return uuid

def get_auth_uid(authorization:Annotated[str,Header()])->str:
  if not authorization:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail='Missing authorization header.'
    )

  if not authorization.startswith('Bearer '):
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail='Invalid authorization header.'
    )
  
  try:
    return auth.verify_id_token(
      id_token=authorization.split('Bearer ')[1],
      check_revoked=True
    )['uid']

  except auth.RevokedIdTokenError:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail='ID token revoked.'
    )

  except Exception:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail='Invalid ID token.'
    )

def get_qdrant_client(settings:QdrantSetting)->AsyncQdrantClient:
  return AsyncQdrantClient(
    url=settings.url.unicode_string(),
    api_key=settings.api_key.get_secret_value(),
    timeout=30,
    prefer_grpc=True
  )

def get_redis_client(settings:OtherSertting)->redis.Redis:
  return redis.Redis(
    host=settings.redis_host.get_secret_value(),
    port=19674,
    decode_responses=True,
    username=settings.redis_username.get_secret_value(),
    password=settings.redis_password.get_secret_value(),
  )

def get_now_utc()->datetime:
  return datetime.now(timezone.utc)

def get_recent_day_utc(
  day:int,
  whole_day:bool=True,
  type:Literal['start','end']='start'
)->datetime:
  recent_day_utc=get_now_utc()-timedelta(days=day)

  if whole_day:
    if type=='start':
      recent_day_utc=recent_day_utc.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
      )
    else:
      recent_day_utc=recent_day_utc.replace(
        hour=23,
        minute=59,
        second=59,
        microsecond=999999
      )
  
  return recent_day_utc

async def run_workflow(workflow:list[tuple[str,tuple[Callable[[],Coroutine]]]]):
  for stage_name,stage_tasks in workflow:
    tasks=[asyncio.create_task(c()) for c in stage_tasks]

    try:
      with logfire.span(stage_name):
        await asyncio.gather(*tasks)
        
    except Exception:
      for t in tasks:
        if not t.done():
          t.cancel()
      raise