from fastapi import(
  HTTPException,
  status
)

from google.auth import(
  default,
  impersonated_credentials
)
from google.cloud.storage import(
  Bucket,
  Blob
)

from pydantic import(
  BaseModel,
  Field,
  ValidationError
)

from pathlib import PurePath

from uuid import UUID

from dataclasses import dataclass

from app.tree.soil.typing import(
  UTCTimestampT,
  StrippedStrT
)
from app.tree.water.config import TAISettings

DEFAULT_RECENT_N_DAYS=7
RECORD_FILE_NAME_FORMAT='%Y_%m_%d_%H_%M_%S'
_SIGNED_URL_EXP_SECOND=30

class RecordFileMetadata(BaseModel):
  uuid:UUID
  record_start:UTCTimestampT
  record_end:UTCTimestampT

class RecentRecordsStats(BaseModel):
  record_count:int=Field(gt=0)
  earliest_record:UTCTimestampT
  latest_record:UTCTimestampT

class RecentRecords(BaseModel):
  stats:RecentRecordsStats
  contents:StrippedStrT

@dataclass(kw_only=True)
class FileBase:
  blob:Blob
  settings:TAISettings

  @property
  def bucket(self)->Bucket:
    return self.blob.bucket

  @property
  def url(self)->str:
    return f'gs://{self.bucket.name}/{self.blob.name}'

  @property
  def file_path(self)->PurePath:
    if not self.blob.name:
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail='Missing blob name.'
      )

    return PurePath(self.blob.name)

  @property
  def auth_uid(self)->str:
    return self.file_path.parts[0]
  
  def get_signed_url(self)->str:
    source_credentials,_=default()
    target_credentials=impersonated_credentials.Credentials(
      source_credentials=source_credentials,
      target_principal=f'{self.settings.service_account}@{self.settings.project}.iam.gserviceaccount.com',
      target_scopes=['https://www.googleapis.com/auth/cloud-platform'],
      lifetime=_SIGNED_URL_EXP_SECOND
    )

    return self.blob.generate_signed_url(
      expiration=_SIGNED_URL_EXP_SECOND,
      version='v4',
      method='GET',
      credentials=target_credentials
    )

@dataclass(kw_only=True)
class RecordFile(FileBase):
  def get_metadata(self)->RecordFileMetadata:
    try:
      return RecordFileMetadata.model_validate(self.blob.metadata)

    except ValidationError:
      raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f'Invalid record file metadata: {self.blob.metadata}.'
      )
  
  def _upload_record_file(
    self,
    file_string:str,
    record_file_metadata:RecordFileMetadata
  )->None:
    blob=self.bucket.blob(
      f'{self.auth_uid}/'
      f'{record_file_metadata.record_start.strftime(RECORD_FILE_NAME_FORMAT)}.txt'
    )
    
    blob.metadata=record_file_metadata.model_dump(mode='json')

    blob.upload_from_string(
      data=file_string,
      content_type='text/plain; charset=utf-8'
    )

# class UserFiles:
#   def __init__(
#     self,
#     auth_uid:str,
#     bucket:Bucket,
#     file_path:PurePath,
#     recent_n_days:int=DEFAULT_RECENT_N_DAYS
#   )->None:
#     self.auth_uid=auth_uid
#     self.bucket=bucket
#     self.file_path=file_path
#     self.recent_n_days=recent_n_days
  
#   def _get_recent_files(self)->list[Blob]:
#     prefix=f'{self.auth_uid}/'
#     start_offset=(
#       f'{prefix}'
#       f'{get_recent_day_utc(self.recent_n_days).strftime(RECORD_FILE_NAME_FORMAT)}'
#     )

#     recent_files=list(self.bucket.list_blobs(
#       prefix=prefix,
#       start_offset=start_offset,
#       match_glob=f'{prefix}*{self.file_path.suffix}'
#     ))

#     if not recent_files:
#       raise HTTPException(
#         status_code=status.HTTP_404_NOT_FOUND,
#         detail=(
#           f'No {self.file_path.suffix} files found '
#           f'for recent {self.recent_n_days} days '
#           f'with prefix {prefix} and start_offset {start_offset}.'
#         )
#       )
     
#     return recent_files

#   def get_recent_records(self)->RecentRecords:
#     recent_files=self._get_recent_files()

#     recent_files.sort(key=attrgetter('name'))

#     record_start_dates=[
#       datetime.strptime(
#         PurePath(record_file.name).stem,
#         RECORD_FILE_NAME_FORMAT
#       ).replace(tzinfo=timezone.utc)
#       for record_file in recent_files
#       if record_file.name is not None
#     ]

#     contents='\n\n'.join([
#       record_file.download_as_text() for record_file in recent_files
#     ])

#     return RecentRecords(
#       stats=RecentRecordsStats(
#         record_count=len(recent_files),
#         earliest_record=min(record_start_dates),
#         latest_record=max(record_start_dates),
#       ),
#       contents=contents,
#     )