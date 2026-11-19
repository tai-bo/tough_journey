from fastapi import(
  HTTPException,
  status
)

from pydantic import BaseModel

from google.cloud.firestore_v1 import Increment
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1 import(
  AsyncCollectionReference,
  AsyncDocumentReference
)
from google.cloud import storage

from typing import cast

from dataclasses import(
  dataclass,
  field
)

from qdrant_client import AsyncQdrantClient

from functools import cached_property

from app.tree.branch.transcription_agent import(
  TranscribeAgent,
  Transcription
)
from app.tree.trunk.vdb import(
  CollectionBase,
  TranscriptionPayloadBase
)
from app.tree.trunk.user import(
  FirestoreUser,
  AudioSetting
)
from app.tree.trunk.storage import(
  RecordFile,
  RecordFileMetadata
)
from app.tree.trunk.record import Record
from app.tree.root.model import RecordBase
from app.tree.water.enum import(
  FirestoreSubcollectionStrEnum,
  UpsertStrEnum,
  QdrantCollectionStrEnum,
  InputSettingStrEnum,
  StatsStrEnum
)

class TranscriptionDoc(RecordFileMetadata):
  exists:bool
  processed:bool

class TranscriptionPayload(
  RecordBase,
  TranscriptionPayloadBase
):
  pass

class TranscriptionJSON(BaseModel):
  record_metadata:RecordFileMetadata
  transcription:Transcription

@dataclass(kw_only=True)
class UserTranscription(FirestoreUser):
  record_file:RecordFile
  qdrant_client:AsyncQdrantClient
  storage_client:storage.Client

  _transcription_doc:TranscriptionDoc|None=field(default=None,init=False)
  _transcription:Transcription|None=field(default=None,init=False)

  def __post_init__(self):
    self.auth_uid=self.record_file.auth_uid

  @property
  def _record(self)->Record:
    return Record(
      service_account=self.settings.service_account,
      auth_uid=self.auth_uid
    )
  
  @cached_property
  def _record_metadata(self)->RecordFileMetadata:
    return self.record_file.get_metadata()

  @property
  def _subcollection(self)->AsyncCollectionReference:
    return (
      self.user_doc
      .collection(FirestoreSubcollectionStrEnum.TRANSCRIPTION)
    )

  @property
  def _doc_ref(self)->AsyncDocumentReference:
    return self._subcollection.document(str(self._record_metadata.uuid))
  
  @property
  def transcription_doc(self)->TranscriptionDoc:
    if not self._transcription_doc:
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail='self._transcription_doc was None.'
      )
    
    return self._transcription_doc
  
  @property
  def _transcription_agent(self)->TranscribeAgent:
    return TranscribeAgent(self.settings.ai)

  @property
  def transcription(self)->Transcription:
    if not self._transcription:
      raise HTTPException(
          status_code=status.HTTP_404_NOT_FOUND,
          detail='self._transcription was None.'
        )
    
    return self._transcription

  async def set_transcription_doc(self)->None:
    doc_snapshot=await self._doc_ref.get()
    doc_snapshot_dict=doc_snapshot.to_dict()

    if doc_snapshot_dict:
      exists=True
      processed=doc_snapshot_dict.get('processed',False)
      upsert=UpsertStrEnum.UPDATE
    else:
      exists=False
      processed=False
      upsert=UpsertStrEnum.INSERT
    
    self._transcription_doc=TranscriptionDoc(
      uuid=self._record_metadata.uuid,
      record_start=self._record_metadata.record_start,
      record_end=self._record_metadata.record_end,
      exists=exists,
      processed=processed
    )

    doc_dict=self.transcription_doc.model_dump(exclude={'uuid'})
    doc_dict=self.set_firestore_doc_base(
      doc_dict=doc_dict,
      upsert=upsert
    )
    
    await(self._doc_ref.set(
      doc_dict,
      merge=True
    ))

  async def count_unprocessed(self)->int:
    return (await self._subcollection
      .where(filter=FieldFilter("processed","==",False))
      .count()
      .get()
    )[0][0].value

  async def log(
    self,
    processed:bool
  )->None:
    self.transcription_doc.processed=processed
    doc_dict=self.transcription_doc.model_dump(exclude={'uuid'})

    if self.transcription_doc.exists:
      upsert=UpsertStrEnum.UPDATE
    else:
      upsert=UpsertStrEnum.INSERT

    doc_dict=self.set_firestore_doc_base(
      doc_dict=doc_dict,
      upsert=upsert
    )

    await(self._doc_ref.set(
      doc_dict,
      merge=True
    ))

  async def transcribe(self)->None:
    self._transcription=await self._transcription_agent.transcribe(
      audio_bytes=self.record_file.blob.download_as_bytes(),
      audio_setting=cast(
        AudioSetting,
        await self.get_input_setting(InputSettingStrEnum.AUDIO)
      )
    )

  async def save_vector(self)->None:
    collection_base=CollectionBase(
      client=self.qdrant_client,
      settings=self.settings,
      collection=QdrantCollectionStrEnum.TRANSCRIPTION
    ) 

    await collection_base.embed(
      embed_type='document',
      documents=self.transcription.transcription
    )

    await collection_base.upsert_point(
      payload=TranscriptionPayload(
        **self._record.record_base.model_dump(),
        transcription=self.transcription.transcription,
        record_start=self.transcription_doc.record_start
      ),
      id=self.transcription_doc.uuid
    )
  
  def save_json(self)->None:
    bucket=self.storage_client.bucket(
      f'{self.settings.project}-'
      f'transcription-'
      f'us-central1'
    )

    blob=bucket.blob(
      f'{self.auth_uid}/'
      f'{self.transcription_doc.record_start.strftime("%Y/%m/%d")}/'
      f'{str(self.transcription_doc.uuid)}.json'
    )

    blob.upload_from_string(
      TranscriptionJSON(
        record_metadata=self._record_metadata,
        transcription=self.transcription
      ).model_dump_json(),
      content_type='application/json'
    )

  async def increment_counter(self)->None:
    doc_dict=self.set_firestore_doc_base(
      doc_dict={
        'count': Increment(1)
      },
      upsert=UpsertStrEnum.UPDATE
    )

    await self.update_stats(
      stats=StatsStrEnum.TRANSCRIPTION,
      doc_dict=doc_dict
    )