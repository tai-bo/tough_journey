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

from google.genai.types import(
  ThinkingConfigDict,
  ThinkingLevel
)

from typing import Annotated

from dataclasses import dataclass

import logfire

from app.tree.trunk.vdb import CollectionBase
from app.tree.trunk.storage import RecentRecords
from app.tree.trunk.agent import(
  AgentBase,
  DEFAULT_TEMPERATURE,
  DEFAULT_TIMEOUT,
  FALLBACK_ON
)
from app.tree.trunk.user import(
  UserDoc,
  PerformanceReviewSetting
)
from app.tree.root.model import RecordBase
from app.tree.soil.typing import StrippedStrT

type ProjectAgentT=Agent[ProjectDeps,list[Project]]
type ProjectDescription=Annotated[
  StrippedStrT,
  Field(description=('A concise description of the project, up to 150 words.'))
]

class ProjectDeps(BaseModel):
  user_setting:UserDoc
  performance_review_setting:PerformanceReviewSetting

class CompletedTask(BaseModel):
  problem:str=Field(description=('A concise description of the problem, up to 50 words.'))
  solution:str=Field(description=('A concise description of the solution to the problem, up to 150 words.'))

class Project(BaseModel):
  title:StrippedStrT=Field(description=('A concise title of the project, up to 5 words.'))
  description:ProjectDescription
  completed_tasks:list[CompletedTask]|None=Field(default=None,max_length=3)

class ProjectPayload(RecordBase):
  description:ProjectDescription

class ProjectAgent(AgentBase):
  @property
  def _model(self)->FallbackModel:
    return FallbackModel(
      GoogleModel(
        model_name='gemini-3-flash-preview',
        provider=self.google_provider,
        settings=GoogleModelSettings(
          temperature=1,
          google_thinking_config=ThinkingConfigDict(thinking_level=ThinkingLevel.MEDIUM),
          timeout=DEFAULT_TIMEOUT
        )
      ),

      OpenAIResponsesModel(
        model_name='gpt-5.1-mini',
        provider=self.openai_provider,
        settings=OpenAIResponsesModelSettings(
          temperature=DEFAULT_TEMPERATURE,
          openai_reasoning_effort='medium',
          timeout=DEFAULT_TIMEOUT
        )
      ),

      fallback_on=FALLBACK_ON
    )
  
  @property
  def _agent(self)->ProjectAgentT:
    agent=Agent(
      model=self._model,
      deps_type=ProjectDeps,
      output_type=list[Project],
      instructions=(
        '# Role\n'
        'You are a professional project manager.'
      )
    )

    @agent.instructions
    def add_run_context(ctx:RunContext[ProjectDeps])->str:
      return (
        f'# Instructions\n'
        f'- You currently work in the {ctx.deps.performance_review_setting.company_industry} industry.\n'
        f'- From the provided texts, if available, extract top 3 projects you are working on.\n'
        f'- For each project, if available, extract top 3 tasks completed by you.\n'
        f'# Constraints\n'
        f'- Write in {ctx.deps.user_setting.language}.\n'
        f'- Focus on facts presented in the provided texts.'
      )
    
    return agent

  async def generate_projects(
    self,
    recent_records:RecentRecords,
    user_setting:UserDoc,
    performance_review_setting:PerformanceReviewSetting
  )->list[Project]|None:
    return (await self._agent.run(
      user_prompt=recent_records.contents,
      deps=ProjectDeps(
        user_setting=user_setting,
        performance_review_setting=performance_review_setting
      )
    )).output

@dataclass(kw_only=True)
class ProjectCollection(CollectionBase):
  project:Project

  def get_payload(self)->ProjectPayload:
    record_base=self._get_record_base()

    return ProjectPayload(
      **record_base.model_dump(),
      description=self.project.description
    )
  
  async def process(self)->None:
    with logfire.span(self.project.description[:33]):
      await self.set_embeddings(
        embed_type='document',
        documents=self.project.description,
        title=self.project.title
      )

      self.set_prefetch()
      nearest_point=await self.get_nearest_point()

      await self.upsert_point(
        payload=self.get_payload(),
        id=nearest_point.id if nearest_point else None
      )