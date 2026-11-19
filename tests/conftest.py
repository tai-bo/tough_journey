import os
from google.cloud import storage, secretmanager
import pytest
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager
from app.main import app

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "tai-pr-dev")
def get_storage_client():
  return storage.Client(project=PROJECT_ID)

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture()
async def client():
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), 
            base_url="http://api"
        ) as ac:
            yield ac
