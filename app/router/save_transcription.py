from fastapi import(
  HTTPException,
  status,
  APIRouter
)

from pydantic import(
  BaseModel,
  Field
)

from uuid import UUID

from app.tree.leaf.transcription import UserTranscription
from app.tree.trunk.common import ResourcesT
from app.tree.trunk.storage import RecordFile
from app.tree.root.model import RedisBase
from app.tree.water.config import GCP_NAMING_PATTERN

REDIS_LOCK_TTL=180 # seconds

class Payload(BaseModel):
  bucket_name:str=Field(pattern=GCP_NAMING_PATTERN)
  blob_name:str

class Response(BaseModel):
  record_file_uuid:UUID

router=APIRouter()
@router.post(
  "/save_transcription",
  status_code=status.HTTP_201_CREATED
)
async def save_transcription(
  payload:Payload,
  resources:ResourcesT
)->Response:
  try:
    # Record File
    blob=(
      resources.storage_client
      .bucket(payload.bucket_name)
      .get_blob(payload.blob_name)
    )

    if not blob:
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f'Blob {payload.blob_name} did not exist in bucket {payload.bucket_name}.'
      )
      
    record_file=RecordFile(
      blob=blob,
      settings=resources.settings
    )
    record_file_metadata=record_file.get_metadata()

    response=Response(record_file_uuid=record_file_metadata.uuid)
    
    # Lock
    if not await RedisBase(
      redis_client=resources.redis_client,
      settings=resources.settings
    ).get_locked(
      name=record_file_metadata.uuid,
      ex=REDIS_LOCK_TTL
    ):
      return response

    # User Transcription
    user_transcription=UserTranscription(
      firestore_client=resources.firestore_client,
      settings=resources.settings,
      record_file=record_file,
      qdrant_client=resources.qdrant_client,
      storage_client=resources.storage_client
    )

    await user_transcription.set_transcription_doc()

    if user_transcription.transcription_doc.processed:
      return response

    await user_transcription.transcribe()

    await user_transcription.save_vector()
    user_transcription.save_json()
    
    await user_transcription.increment_counter()

    await user_transcription.log(processed=True)

    return response
  
  except HTTPException:
    raise

  except Exception as e:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail=f'Exception: {str(e)}.'
    )