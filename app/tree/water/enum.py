from enum import(
  StrEnum,
  IntEnum,
  unique
)

@unique
class UserPlanIntEnum(IntEnum):
  FREE=0
  PAID_1=1

@unique
class UserLocaleStrEnum(StrEnum):
  EN_AU='en-Latn-AU'
  EN_CA='en-Latn-CA'
  EN_GB='en-Latn-GB'
  EN_IE='en-Latn-IE'
  EN_NZ='en-Latn-NZ'
  EN_SG='en-Latn-SG'
  EN_US='en-Latn-US'
  ZH_CN='zh-Hans-CN'
  ZH_HK='zh-Hant-HK'
  ZH_TW='zh-Hant-TW'

@unique
class UserLanguageStrEnum(StrEnum):
  EN_AU='Australian English'
  EN_CA='Canadian English'
  EN_GB='British English'
  EN_IE='Irish English'
  EN_NZ='New Zealand English'
  EN_SG='American English'
  EN_US='Singaporean English'
  ZH_CN='Simplified Chinese'
  ZH_HK='Traditional Chinese (Hong Kong)'
  ZH_TW='Traditional Chinese (Taiwan)'

@unique
class SpeakerGenderStrEnum(StrEnum):
  FEMALE='Female'
  MALE='Male'
  UKNOWN='Unknown'

@unique
class QdrantCollectionStrEnum(StrEnum):
  PROJECTS='projects'
  TRANSCRIPTION='transcription'

@unique
class VectorNameStrEnum(StrEnum):
  DOCUMENT='document'
  CLASSIFICATION='classification'
  CLUSTERING='clustering'

@unique
class VectorPayloadDateFieldStrEnum(StrEnum):
  CREATED_AT='created_at'
  UPDATED_AT='updated_at'
  RECORD_START='record_start'

@unique
class GoogleEmbedTaskTypeStrEnum(StrEnum):
  SEMANTIC_SIMILARITY='SEMANTIC_SIMILARITY'
  CLASSIFICATION='CLASSIFICATION'
  CLUSTERING='CLUSTERING'
  RETRIEVAL_DOCUMENT='RETRIEVAL_DOCUMENT'
  RETRIEVAL_QUERY='RETRIEVAL_QUERY'
  CODE_RETRIEVAL_QUERY='CODE_RETRIEVAL_QUERY'
  QUESTION_ANSWERING='QUESTION_ANSWERING'
  FACT_VERIFICATION='FACT_VERIFICATION'

@unique
class ProcessStrEnum(StrEnum):
  SAVE_TRANSCRIPTION='save_transcription'

@unique
class FirestoreCollectionStrEnum(StrEnum):
  USER='user'
  PROCESSING='processing'

@unique
class FirestoreSubcollectionStrEnum(StrEnum):
  PLAN='plan'
  STATS='stats'
  INPUT_SETTING='input_setting'
  OUTPUT_SETTING='output_setting'
  TRANSCRIPTION='transcription'

@unique
class UpsertStrEnum(StrEnum):
  UPDATE='update'
  INSERT='insert'

@unique
class StatsStrEnum(StrEnum):
  TRANSCRIPTION='transcription'

@unique
class InputSettingStrEnum(StrEnum):
  AUDIO='audio'

@unique
class OutputSettingStrEnum(StrEnum):
  PERFORMANCE_REVIEW='performance_review'

@unique
class PointGroupTypeStrEnum(StrEnum):
  COMMUNITIES='communities'
  ISOLATES='isolates'