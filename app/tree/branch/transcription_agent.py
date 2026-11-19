from pydantic import(
  BaseModel,
  Field
)

from pydantic_ai import(
  Agent,
  RunContext,
  BinaryContent
)
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.google import(
  GoogleModelSettings,
  GoogleModel
)
from pydantic_ai.models.openai import(
  OpenAIChatModel,
  OpenAIChatModelSettings
)
from pydantic_ai.providers.alibaba import AlibabaProvider
from pydantic_ai.profiles.openai import(
  OpenAIModelProfile,
  OpenAIJsonSchemaTransformer
)

from openai.types.chat.chat_completion import ChatCompletion

from google.genai.types import(
  ThinkingConfigDict,
  ThinkingLevel
)

from typing import(
  Literal,
  Any
)

from app.tree.trunk.agent import(
  AgentBase,
  DEFAULT_TIMEOUT,
  FALLBACK_ON
)
from app.tree.trunk.user import AudioSetting
from app.tree.soil.typing import StrippedStrT
from app.tree.water.enum import SpeakerGenderStrEnum

type TranscriptionAgentT=Agent[TranscriptionDeps,Transcription]

class TranscriptionDeps(BaseModel):
  audio_setting:AudioSetting

class Transcription(BaseModel):
  transcription:StrippedStrT
  primary_language:StrippedStrT=Field(description=(
    'Primary language spoken in the audio recording. '
    'Must use an IETF BCP 47 language tag value here.'
  ))
  speaker_gender:SpeakerGenderStrEnum
  word_count:int=Field(description=(
    'Word count of transcription.'
  ))

class AlibabaASRModel(OpenAIChatModel):
  def __init__(
    self,
    model_name:Literal['qwen3-asr-flash'],
    provider:AlibabaProvider,
    profile:OpenAIModelProfile|None=None,
    settings:OpenAIChatModelSettings|None=None
  )->None:
    _profile=profile or OpenAIModelProfile(
      json_schema_transformer=OpenAIJsonSchemaTransformer,
      openai_supports_tool_choice_required=False,
      openai_supports_strict_tool_definition=False,
      ignore_streamed_leading_whitespace=True,
      openai_chat_audio_input_encoding='uri'
    )

    _settings=settings or OpenAIChatModelSettings(
      extra_body={
        "asr_options": {
          "enable_itn": True
        }
      },
      timeout=DEFAULT_TIMEOUT
    )

    super().__init__(
      model_name=model_name,
      provider=provider,
      profile=_profile,
      settings=_settings
    )

  def _validate_completion(
    self,
    response:Any
  )->ChatCompletion:
    asr_resp=response.model_dump(exclude={
      'choices': {
        '__all__': {
          'message': {
            'annotations': True
          }
        }
      },
      'usage': {
        'seconds': True
      }
    })

    return ChatCompletion.model_validate(asr_resp)

class TranscribeAgent(AgentBase):
  @property
  def _model(self)->FallbackModel:
    return FallbackModel(
      # AlibabaASRModel(
      #   model_name='qwen3-asr-flash',
      #   provider=self.alibaba_provider
      # ),
      
      GoogleModel(
        model_name='gemini-3-flash-preview',
        provider=self.google_provider,
        settings=GoogleModelSettings(
          temperature=1,
          google_thinking_config=ThinkingConfigDict(thinking_level=ThinkingLevel.LOW),
          timeout=DEFAULT_TIMEOUT
        )
      ),

      OpenAIChatModel(
        model_name='qwen3-omni-flash',
        provider=self.alibaba_provider,
        settings=OpenAIChatModelSettings(
          timeout=DEFAULT_TIMEOUT
        )
      ),

      fallback_on=FALLBACK_ON
    )
  
  @property
  def _agent(self)->TranscriptionAgentT:
    agent=Agent(
      model=self._model,
      deps_type=TranscriptionDeps,
      output_type=Transcription,
      instructions=(
        '# Role\n'
        'You are a professional transcriber.\n'
      )
    )

    @agent.instructions
    def add_run_context(ctx:RunContext[TranscriptionDeps])->str:
      return (
        f'# Instructions\n'
        f'- Transcribe the audio recording.\n'
        f'# Constraints\n'
        f'- Transcription in {ctx.deps.audio_setting.locale}.\n'
        f'- Treat entire transcription as a single paragraph. '
        f'So it must not contain any newline or tab characters.'
      )

    return agent

  async def transcribe(
    self,
    audio_bytes:bytes,
    audio_setting:AudioSetting
  )->Transcription:
    kwargs={
      "data": audio_bytes,
      "media_type": 'audio/wav' # HACK To bypass assert in OpenAIChatModelSettings
    }

    return (await self._agent.run(
      user_prompt=[BinaryContent(**kwargs)],
      deps=TranscriptionDeps(audio_setting=audio_setting)
    )).output