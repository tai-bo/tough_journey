from fastapi import(
  HTTPException,
  status
)

from google.cloud.firestore_v1 import(
  AsyncCollectionReference,
  AsyncDocumentReference
  
)
from google.cloud.firestore_v1.types import WriteResult

from pydantic import(
  BaseModel,
  Field
)

from dataclasses import dataclass

from app.tree.root.model import(
  RecordBase,
  FirestoreBase
)
from app.tree.soil.typing import StrippedStrT
from app.tree.water.enum import(
  UserLocaleStrEnum,
  FirestoreCollectionStrEnum,
  FirestoreSubcollectionStrEnum,
  OutputSettingStrEnum,
  InputSettingStrEnum,
  StatsStrEnum
)

class UserDoc(RecordBase):
  nickname:str

class AudioSetting(BaseModel):
  locale:UserLocaleStrEnum
  recording_time_limit:int=Field(
    ge=60,
    le=120,
    multiple_of=30
  )

class PerformanceReviewSetting(BaseModel):
  language:UserLocaleStrEnum
  company_industry:StrippedStrT
  job_title:StrippedStrT

class TranscriptionStats(BaseModel):
  count:int=Field(ge=0)

@dataclass(kw_only=True)
class FirestoreUser(FirestoreBase):
  auth_uid:str|None=None
  
  @property
  def _user_collection(self)->AsyncCollectionReference:
    return (
      self.firestore_client
      .collection(FirestoreCollectionStrEnum.USER)
    )

  @property
  def user_doc(self)->AsyncDocumentReference:
    return (
      self._user_collection
      .document(self.auth_uid)
    )
  
  @property
  def _plan_subcollection(self)->AsyncCollectionReference:
    return (
      self.user_doc
      .collection(FirestoreSubcollectionStrEnum.PLAN)
    )
  
  @property
  def _stats_subcollection(self)->AsyncCollectionReference:
    return (
      self.user_doc
      .collection(FirestoreSubcollectionStrEnum.STATS)
    )

  @property
  def _input_setting_subcollection(self)->AsyncCollectionReference:
    return (
      self.user_doc
      .collection(FirestoreSubcollectionStrEnum.INPUT_SETTING)
    )
  
  @property
  def _output_setting_subcollection(self)->AsyncCollectionReference:
    return (
      self.user_doc
      .collection(FirestoreSubcollectionStrEnum.OUTPUT_SETTING)
    )
  
  async def get_input_setting(
    self,
    input_setting:InputSettingStrEnum
  )->BaseModel:
    doc=await self._input_setting_subcollection.document(input_setting).get()

    if not doc:
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=(
          f'User {self.auth_uid} had no Firestore doc for '
          f'{input_setting} input setting.'
        )
      )

    match input_setting:
      case InputSettingStrEnum.AUDIO:
        model=AudioSetting.model_validate(
          doc.to_dict(),
          extra='ignore'
        )
      
      case _:
        model=None

    if not model:
      raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f'Model not implemented for {input_setting} input setting.'
      )

    return model

  async def get_output_setting(
    self,
    output_setting:OutputSettingStrEnum
  )->BaseModel:
    doc=await self._output_setting_subcollection.document(output_setting).get()

    if not doc:
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=(
          f'User {self.auth_uid} had no Firestore doc for '
          f'{output_setting} output setting.'
        )
      )

    match output_setting:
      case OutputSettingStrEnum.PERFORMANCE_REVIEW:
        model=PerformanceReviewSetting.model_validate(
          doc.to_dict(),
          extra='ignore'
        )
      
      case _:
        model=None

    if not model:
      raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f'Model not implemented for {output_setting} output setting.'
      )

    return model
  
  async def update_stats(
    self,
    stats:StatsStrEnum,
    doc_dict:dict
  )->WriteResult:
    return (
      await self._stats_subcollection
      .document(stats)
      .update(doc_dict)
    )