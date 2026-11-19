from pydantic import(
  BaseModel,
  Field
)

from pydantic_ai import(
  Agent,
  RunContext
)
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.google import(
  GoogleModelSettings,
  GoogleModel
)
from pydantic_ai.models.openai import(
  OpenAIResponsesModel,
  OpenAIResponsesModelSettings
)

from typing import Literal

from app.tree.trunk.agent import(
  AgentBase,
  DEFAULT_TEMPERATURE,
  DEFAULT_TIMEOUT,
  FALLBACK_ON
)
from app.tree.soil.typing import StrippedStrT
from app.tree.water.enum import UserLanguageStrEnum

SUMMARY_FREQUENCY=Literal[
  'Daily',
  'Weekly',
  'Monthly',
  'Quarterly',
  'Annually'
]

type SummaryAgentT=Agent[SummaryDeps,Summary]

class SummaryDeps(BaseModel):
  language:UserLanguageStrEnum

class Summary(BaseModel):
  title:StrippedStrT=Field(description=('A concise title for the summary, up to 5 words.'))
  summary:StrippedStrT=Field(description=('A concise summary, up to 250 words.'))

class SummaryAgent(AgentBase):
  @property
  def _model(self)->FallbackModel:
    return FallbackModel(
      GoogleModel(
        model_name='gemini-2.5-flash-lite',
        provider=self.google_provider,
        settings=GoogleModelSettings(
          temperature=DEFAULT_TEMPERATURE,
          google_thinking_config={'thinking_budget': 0},
          timeout=DEFAULT_TIMEOUT
        )
      ),

      OpenAIResponsesModel(
        model_name='gpt-5-nano',
        provider=self.openai_provider,
        settings=OpenAIResponsesModelSettings(
          temperature=DEFAULT_TEMPERATURE,
          openai_reasoning_effort='low',
          timeout=DEFAULT_TIMEOUT
        )
      ),

      fallback_on=FALLBACK_ON
    )
  
  @property
  def _agent(self)->SummaryAgentT:
    agent=Agent(
      model=self._model,
      deps_type=SummaryDeps,
      output_type=Summary,
      instructions=(
        '# Role\n'
        'You are a professional performance review writer.'
      )
    )

    @agent.instructions
    def add_run_context(ctx:RunContext[SummaryDeps])->str:
      return (
        f'# Instructions\n'
        f'- Summarise the provided texts.\n'
        f'# Constraints\n'
        f'- Write in {ctx.deps.language}.\n'
        f'- Focus on facts presented in the provided texts.'
      )
    
    return agent

  async def generate_summary(
    self,
    language:UserLanguageStrEnum,
    texts:StrippedStrT
  )->Summary:
    return (await self._agent.run(
      user_prompt=texts,
      deps=SummaryDeps(
        language=language
      )
    )).output