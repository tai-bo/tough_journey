from pydantic_ai.providers import Provider
from pydantic_ai.providers.gateway import gateway_provider
from pydantic_ai.exceptions import ModelAPIError
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.alibaba import AlibabaProvider

from google.genai.errors import ClientError as GoogleClientError

from app.tree.water.config import AISetting

DEFAULT_TEMPERATURE=0
DEFAULT_TIMEOUT=60
FALLBACK_ON=(
  ModelAPIError,
  GoogleClientError
)

class AgentBase():
  def __init__(
    self,
    ai_setting:AISetting
  )->None:
    self.ai_setting=ai_setting

  @property
  def google_provider(self)->GoogleProvider:
    return GoogleProvider(location='global')
  
  @property
  def openai_provider(self)->Provider:
    return gateway_provider(
      'openai',
      api_key=self.ai_setting.pydantic_ai_gateway_api_key.get_secret_value()
    )
  
  @property
  def alibaba_provider(self)->AlibabaProvider:
    return AlibabaProvider(
      api_key=self.ai_setting.alibaba_api_key.get_secret_value(),
      base_url='https://dashscope-intl.aliyuncs.com/compatible-mode/v1'
    )