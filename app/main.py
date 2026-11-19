import google.auth
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.auth.credentials import TokenState
from google.cloud import storage

from fastapi import(
  FastAPI,
  APIRouter,
  Request
)

from firebase_admin import(
  get_app,
  initialize_app,
  firestore_async
)

from pydantic_ai import Embedder

from contextlib import asynccontextmanager

import asyncio

import logfire

from app.tree.trunk.vdb import CollectionBase
from app.tree.water.config import TAISettings
from app.tree.root.func import(
  LifeSpanResources,
  get_qdrant_client,
  get_redis_client
)
from app.router import(
  save_transcription,
  group_transcription
)

refresh_lock=asyncio.Lock()
settings=TAISettings() # type:ignore[reportCallIssue]

# Lifespan
@asynccontextmanager
async def lifespan(app:FastAPI):
  # Google Auth Credentials
  credentials,_=google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
  )

  # Firebase App
  try:
    get_app()
  except ValueError:
    initialize_app()
  
  # Open Clients
  qdrant_client=get_qdrant_client(settings.qdrant)
  firestore_client=firestore_async.client()
  storage_client=storage.Client()
  redis_client=get_redis_client(settings.other)
  
  # Init Qdrant Collections
  collection_config_files=CollectionBase.list_config_files()
  for file in collection_config_files:
    await CollectionBase(
      client=qdrant_client,
      settings=settings,
      collection=file
    ).create_collection() 

  # LifeSpanResources

  # yield{
  #   'resources': LifeSpanResources(
  #     settings=settings,
  #     storage_client=storage_client,
  #     firestore_client=firestore_client,
  #     qdrant_client=qdrant_client,
  #     redis_client=redis_client,
  #     google_auth_credentials=credentials
  #   )
  # }

  resources = LifeSpanResources(
    settings=settings,
    storage_client=storage_client,
    firestore_client=firestore_client,
    qdrant_client=qdrant_client,
    redis_client=redis_client,
    google_auth_credentials=credentials
  )
    
  app.state.resources = resources
  
  yield
  # Close Clients
  await qdrant_client.close()
  await redis_client.aclose()
  firestore_client.close()
  storage_client.close()

# FastAPI app
app=FastAPI(
  lifespan=lifespan,
  title='Performance Review API',
  contact={
    'name': 'themselves.ai'
  }
)

# Health Check
@app.get('/health')
async def health():
  return {'status': 'OK'}

# Middleware
@app.middleware('http')
async def refresh_google_auth_credentials(
  request:Request,
  call_next
):
  # credentials=request.state.resources.google_auth_credentials
  credentials = request.app.state.resources.google_auth_credentials
  
  if credentials.token_state in (
    TokenState.INVALID,
    TokenState.STALE
  ):
    async with refresh_lock:
      if credentials.token_state in (
        TokenState.INVALID,
        TokenState.STALE
      ):
        await asyncio.to_thread(
          credentials.refresh,
          GoogleAuthRequest()
        )

  return await call_next(request)

# Logfire Configs
logfire.configure(
  token=settings.other.logfire_token.get_secret_value(),
  environment=settings.env,
  distributed_tracing=False,
  min_level=settings.log_level
)
logfire.instrument_fastapi(
  app,
  excluded_urls='/health'
)
logfire.instrument_aiohttp_client()
logfire.instrument_pydantic_ai()
logfire.instrument_redis()
Embedder.instrument_all()

# Routers
api_router=APIRouter()
api_router.include_router(save_transcription.router)
api_router.include_router(group_transcription.router)

app.include_router(api_router)