from app.tree.root.func import get_now_utc
from app.tree.root.model import RecordBase

class Record():
  def __init__(
    self,
    service_account:str,
    auth_uid:str|None=None
  )->None:
    self.service_account=service_account
    self.auth_uid=auth_uid

  @property
  def record_base(self)->RecordBase:
    return RecordBase(
      created_by=self.service_account,
      created_at=get_now_utc(),
      updated_by=self.service_account,
      updated_at=get_now_utc(),
      auth_uid=self.auth_uid
    )
  
  # def set_firestore_doc_base(
  #   self,
  #   doc_dict:dict,
  #   upsert:UpsertStrEnum
  # )->dict:
  #   doc_dict.update({
  #     'updated_by': self.service_account,
  #     'updated_at': SERVER_TIMESTAMP
  #   })

  #   if upsert==UpsertStrEnum.INSERT:
  #     doc_dict.update({
  #       'created_by': self.service_account,
  #       'created_at': SERVER_TIMESTAMP
  #     })
    
  #   return doc_dict