from pydantic import(
  BaseModel,
  SecretStr,
  HttpUrl,
  Field,
  computed_field
)
from pydantic_settings import(
  SettingsConfigDict,
  BaseSettings,
  PydanticBaseSettingsSource,
  GoogleSecretManagerSettingsSource
)

from logfire import LevelName

# TODO Can we only keep dev, tst and prd?
GCP_NAMING_PATTERN=r"^tai-pr-(dev|tst|prd|Debug|Release)(-.*)?$"

class QdrantSetting(BaseModel):
  url:HttpUrl
  api_key:SecretStr

class AISetting(BaseModel):
  pydantic_ai_gateway_api_key:SecretStr
  alibaba_api_key:SecretStr

class OtherSertting(BaseModel):
  logfire_token:SecretStr
  redis_host:SecretStr
  redis_username:SecretStr
  redis_password:SecretStr

class TAISettings(BaseSettings):
  model_config=SettingsConfigDict(frozen=True)

  project:str=Field(
    validation_alias='GOOGLE_CLOUD_PROJECT',
    pattern=GCP_NAMING_PATTERN
  )
  
  qdrant:QdrantSetting
  ai:AISetting
  other:OtherSertting

  @computed_field
  @property
  def env(self)->str:
    return self.project.split('-')[-1]
  
  @computed_field
  @property
  def log_level(self)->LevelName:
    match self.env:
      case 'dev':
        return 'info'
      case 'tst':
        return 'debug'
      case 'prd':
        return 'error'
      case _:
        return 'error'
  
  @computed_field
  @property
  def service_account(self)->str:
    return f'{self.project}-sa-cloud-run'

  @classmethod
  def settings_customise_sources(
    cls,
    settings_cls:type[BaseSettings],
    init_settings: PydanticBaseSettingsSource,
    env_settings: PydanticBaseSettingsSource,
    dotenv_settings: PydanticBaseSettingsSource,
    file_secret_settings: PydanticBaseSettingsSource
  )->tuple[PydanticBaseSettingsSource,...]:
    return (
      init_settings,
      env_settings,
      dotenv_settings,
      file_secret_settings,
      GoogleSecretManagerSettingsSource(settings_cls)
    )