from fastapi import(
  HTTPException,
  status
)

from qdrant_client import(
  AsyncQdrantClient,
  models
)
from qdrant_client.conversions.common_types import(
  UpdateResult,
  QueryResponse
)

from pydantic import(
  BaseModel,
  model_validator,
  ConfigDict,
  Field
)

from pydantic_ai import Embedder
from pydantic_ai.embeddings.google import GoogleEmbeddingSettings

import yaml

from typing import(
  Sequence,
  Self,
  AsyncIterator,
  cast,
  Type,
  ClassVar
)

from datetime import datetime

import math

from functools import(
  lru_cache,
  cached_property
)

import asyncio

from dataclasses import(
  dataclass,
  field
)

import networkx as nx
from networkx.algorithms.community import louvain_communities

from app.tree.root.func import(
  get_filenames,
  generate_uuid,
  get_recent_day_utc,
  get_now_utc
)
from app.tree.soil.typing import(
  EmbedTypeT,
  UTCTimestampT,
  StrippedStrT,
  QueryT
)
from app.tree.water.enum import(
  QdrantCollectionStrEnum,
  VectorNameStrEnum,
  GoogleEmbedTaskTypeStrEnum,
  VectorPayloadDateFieldStrEnum,
  PointGroupTypeStrEnum
)
from app.tree.water.config import TAISettings

COLLECTION_YAML_DIR='app/qdrant_collection'
QUERY_YAML_DIR='app/qdrant_query'
DEFAULT_FROM_N_DAYS_BEFORE=90
DEFAULT_AVG_WEIGHT=0.0

class VectorConfig(BaseModel):
  name:VectorNameStrEnum
  size:int
  distance:models.Distance=models.Distance.COSINE

class PayloadIndexSchema(BaseModel):
  field_name:str
  field_schema:models.PayloadSchemaType

class CollectionConfig(BaseModel):
  index_auth_uid:bool
  max_input_tokens:int
  vector_configs:list[VectorConfig]
  payload_index_schemas:list[PayloadIndexSchema]

class TranscriptionPayloadBase(BaseModel):
  transcription:StrippedStrT
  record_start:UTCTimestampT

class DateRange(BaseModel):
  from_datetime:datetime|None=None
  to_datetime:datetime|None=None

  @model_validator(mode='after')
  def set_defaults(self)->Self:
    if not self.from_datetime:
      self.from_datetime=get_recent_day_utc(
        day=DEFAULT_FROM_N_DAYS_BEFORE,
        type='start'
      )
    
    if not self.to_datetime:
      self.to_datetime=get_now_utc()
    
    return self

class QueryParamNearestPoint(BaseModel):
  using:VectorNameStrEnum|None=None
  score_threshold:float|None=None
  limit:int|None=None

class QueryParamPrefetch(BaseModel):
  threshold:float|None=None
  limit:int|None=None

class QueryParam(BaseModel):
  model_config=ConfigDict(extra='forbid')
  
  _model_map:ClassVar[dict[QueryT,Type[BaseModel]]]={
    "transcription_clustering": TranscriptionPayloadBase
  }

  query:QueryT
  date_field:VectorPayloadDateFieldStrEnum
  page_size:int=10
  with_payload:list[str]|bool=False
  with_vectors:list[VectorNameStrEnum]|bool=False
  nearest_point:QueryParamNearestPoint|None=None
  prefetch:QueryParamPrefetch|None=None

  @property
  def payload_model(self)->Type[BaseModel]:
    return self._model_map.get(self.query,BaseModel)

class PointGroup(BaseModel):
  group_type:PointGroupTypeStrEnum
  group_index:int=Field(ge=-1)
  count:int=Field(ge=0)
  avg_weight:float|None=None
  payloads:list[TranscriptionPayloadBase]

@dataclass(kw_only=True)
class Embed:
  embed_type:EmbedTypeT
  vector_config:VectorConfig
  documents:str
  title:str=''
  embeddings:Sequence[float]|None=field(default=None,init=False)
  
  @property
  def _task_type(self)->GoogleEmbedTaskTypeStrEnum:
    if self.vector_config.name==VectorNameStrEnum.DOCUMENT:
      if self.embed_type=='document':
        return GoogleEmbedTaskTypeStrEnum.RETRIEVAL_DOCUMENT
      else:
        return GoogleEmbedTaskTypeStrEnum.RETRIEVAL_QUERY
    else:
      return GoogleEmbedTaskTypeStrEnum(self.vector_config.name.upper())
  
  @property
  def _embed_settings(self)->GoogleEmbeddingSettings:
    settings={
      "dimensions": self.vector_config.size,
      "google_task_type": self._task_type
    }

    if self._task_type==GoogleEmbedTaskTypeStrEnum.RETRIEVAL_DOCUMENT:
      settings['google_title']=self.title
    
    return GoogleEmbeddingSettings(**settings)

  @property
  def _embedder(self)->Embedder:
    return Embedder(
      'google-vertex:gemini-embedding-001',
      settings=self._embed_settings
    )
  
  @property
  def _embeddings(self)->Sequence[float]:
    if not self.embeddings:
      raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail='Missing embeddings.'
      )
    
    return self.embeddings

  # In Qdrant, vectors are automatically normalised during upload
  # when the collection's distance metric is set to `Cosine`.
  # https://qdrant.tech/course/essentials/day-1/distance-metrics/#cosine-similarity
  def _normalised_vector(self)->models.VectorStruct:
    if self.vector_config.distance!=models.Distance.COSINE:
      sum_of_squares=sum(x**2 for x in self._embeddings)
      norm=math.sqrt(sum_of_squares)
      
      return [x/norm for x in self._embeddings]
    
    return cast(models.VectorStruct,self._embeddings)
  
  async def _embed_documents(self)->None:
    self.embeddings=(
      await self._embedder.embed_documents(self.documents)
    ).embeddings[0]

  async def embed(self)->models.VectorStruct:
    await self._embed_documents()
    
    return self._normalised_vector()

@dataclass(kw_only=True)
class CollectionBase:
  client:AsyncQdrantClient
  settings:TAISettings
  collection:QdrantCollectionStrEnum|None=None
  
  embeddings:dict[VectorNameStrEnum,models.Vector]|None=field(default=None,init=False)
  
  @staticmethod
  def list_config_files()->list[QdrantCollectionStrEnum]:
    return [QdrantCollectionStrEnum(file) for file in get_filenames(
      dir_path=COLLECTION_YAML_DIR,
      file_suffix='yaml'
    )]

  @staticmethod
  @lru_cache()
  def _load_config(collection:QdrantCollectionStrEnum)->CollectionConfig:
    with open(f'{COLLECTION_YAML_DIR}/{collection}.yaml','r') as f:
      return CollectionConfig.model_validate(yaml.safe_load(f))

  @property
  def _collection(self)->QdrantCollectionStrEnum:
    if not self.collection:
      raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail='Missing collection.'
      )
    
    return self.collection

  @property
  def _config(self)->CollectionConfig:
    return self._load_config(self._collection)

  @property
  def _embeddings(self)->dict[VectorNameStrEnum,models.Vector]:
    if not self.embeddings:
      raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail='Missing embeddings.'
      )
    
    return self.embeddings

  async def get_payload_schema(self)->dict:
    return (
      await self.client.get_collection(self._collection)
    ).payload_schema
  
  async def create_collection(self)->None:
    if not await self.client.collection_exists(self._collection):
      vectors_config={}
      for vector_config in self._config.vector_configs:
        vectors_config[vector_config.name]=models.VectorParams(
          size=vector_config.size,
          distance=vector_config.distance,
          on_disk=True
        )

      await self.client.create_collection(
        collection_name=self._collection,
        vectors_config=vectors_config,
        quantization_config=models.ScalarQuantization(
          scalar=models.ScalarQuantizationConfig(
            type=models.ScalarType.INT8,
            quantile=0.99,
            always_ram=True
          )
        )
      )

      if self._config.index_auth_uid:
        await self.client.create_payload_index(
          collection_name=self._collection,
          field_name='auth_uid',
          field_schema=models.KeywordIndexParams(
            type=models.KeywordIndexType.KEYWORD,
            is_tenant=True
          )
        )
      
      for schema in self._config.payload_index_schemas:
        await self.client.create_payload_index(
          collection_name=self._collection,
          field_name=schema.field_name,
          field_schema=schema.field_schema
        )

  # def set_prefetch(self)->None:
  #   self.prefetch=[
  #     models.Prefetch(
  #       query=self._get_embeddings().get(vector.name),
  #       using=vector.name,
  #       filter=models.Filter(must=self._get_must_filters()),
  #       limit=self.query_param.prefetch.limit,
  #       score_threshold=self.query_param.prefetch.threshold
  #     )
  #     for vector in self._config.vectors
  #   ]

  async def embed(
    self,
    embed_type:EmbedTypeT,
    documents:str,
    title:str=''
  )->None:
    tasks=[]
    vector_names=[]

    for vector_config in self._config.vector_configs:
      embed=Embed(
        embed_type=embed_type,
        vector_config=vector_config,
        documents=documents,
        title=title
      )
      tasks.append(embed.embed())
      vector_names.append(vector_config.name)
    
    try:
      results=await asyncio.gather(*tasks)
      self.embeddings=dict(zip(vector_names,results))
    
    except Exception as e:
      raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f'Failed to embed. Exception: {str(e)}'
      )

  async def upsert_point(
    self,
    payload:BaseModel,
    id:models.ExtendedPointId|None=None
  )->UpdateResult:
    if not id:
      id=generate_uuid()

    return await self.client.upsert(
      collection_name=self._collection,
      points=[models.PointStruct(
        id=id,
        vector=cast(models.VectorStruct,self._embeddings),
        payload=payload.model_dump()
      )]
    )

@dataclass(kw_only=True)
class CollectionQuery(CollectionBase):
  query:QueryT
  auth_uid:str|None=None
  date_range:DateRange=field(default_factory=DateRange)
  # prefetch:list[models.Prefetch]|None=field(default=None,init=False)

  def __post_init__(self):
    _collection_map:dict[QueryT,QdrantCollectionStrEnum]={
      "transcription_clustering": QdrantCollectionStrEnum.TRANSCRIPTION
    }

    if not self.collection:
      self.collection=_collection_map.get(self.query)

  @staticmethod
  @lru_cache()
  def _load_query_param(query:QueryT)->QueryParam:
    with open(f'{QUERY_YAML_DIR}/{query}.yaml','r') as f:
      yaml_data=yaml.safe_load(f)
    
    yaml_data['query']=query

    return QueryParam.model_validate(yaml_data)
  
  @property
  def _query_param(self)->QueryParam:
    return self._load_query_param(self.query)
  
  @property
  def _field_condition_auth_uid(self)->models.Condition:
    if not self.auth_uid:
      raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f'{self} was missing auth_uid.'
      )

    return models.FieldCondition(
      key='auth_uid',
      match=models.MatchValue(value=self.auth_uid)
    )
  
  @property
  def _field_condition_date_range(self)->models.Condition:
    return models.FieldCondition(
      key=self._query_param.date_field,
      range=models.DatetimeRange(
        gte=self.date_range.from_datetime,
        lte=self.date_range.to_datetime
      )
    )
  
  @property
  def _must_filters(self)->list[models.Condition]:
    must_filters=[self._field_condition_date_range]

    if self._config.index_auth_uid:
      must_filters.append(self._field_condition_auth_uid)
    
    return must_filters

  async def get_all_points(self)->list[models.Record]:
    all_points=[]
    next_page_offset=None

    while True:
      points,next_page_offset=await self.client.scroll(
        collection_name=self._collection,
        scroll_filter=models.Filter(must=self._must_filters),
        limit=self._query_param.page_size,
        offset=next_page_offset,
        with_payload=self._query_param.with_payload,
        with_vectors=self._query_param.with_vectors
      )

      all_points.extend(points)

      if next_page_offset is None:
        break
    
    return all_points

  def _get_nearest_points_requests(
    self,
    points:list[models.Record]
  )->list[models.QueryRequest]:
    requests=[]

    if not self._query_param.nearest_point:
      raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f'{self._query_param} was missing nearest_point.'
      )

    if not self._query_param.nearest_point.using:
        raise HTTPException(
          status_code=status.HTTP_400_BAD_REQUEST,
          detail=f'{self._query_param.nearest_point} was missing using.'
        )

    vector_name=self._query_param.nearest_point.using
    must_filters=self._must_filters
    score_threshold=self._query_param.nearest_point.score_threshold
    limit=self._query_param.nearest_point.limit

    for p in points:
      if not isinstance(p.vector,dict):
        raise HTTPException(
          status_code=status.HTTP_400_BAD_REQUEST,
          detail=f'Expected a dict type vector for point {p.id}, but got: {p.vector}.'
        )

      requests.append(
        models.QueryRequest(
          query=p.vector.get(vector_name),
          using=vector_name,
          filter=models.Filter(
            must=must_filters,
            must_not=models.HasIdCondition(has_id=[p.id])
          ),
          score_threshold=score_threshold,
          limit=limit,
          with_vector=False,
          with_payload=False
        )
      )

    return requests

  async def query_batch_points(
    self,
    requests:list[models.QueryRequest]
  )->list[QueryResponse]:
    return await self.client.query_batch_points(
      collection_name=self._collection,
      requests=requests
    )

@dataclass(kw_only=True)
class CollectionPoints(CollectionQuery):
  points:list[models.Record]|None=field(default=None,init=False)

  @cached_property
  def _points(self)->list[models.Record]:
    if self.points is None:
      raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail='Missing points.'
      )
    
    return self.points
  
  @cached_property
  def _payloads(self)->dict[models.ExtendedPointId,BaseModel]:
    payloads={}
    payload_model=self._query_param.payload_model
    
    for point in self._points:
      if not point.payload:
        raise HTTPException(
          status_code=status.HTTP_400_BAD_REQUEST,
          detail=f'Point {point.id} was missing a payload.'
        )

      payloads[point.id]=payload_model.model_validate(point.payload)
    
    return payloads
  
  async def _get_nearest_points(self)->AsyncIterator[tuple[models.Record,list[models.ScoredPoint]]]:
    page_size=self._query_param.page_size

    for i in range(0,len(self._points),page_size):
      page_points=self._points[i:i+page_size]
      nearest_points_requests=self._get_nearest_points_requests(page_points)

      nearest_points=await self.query_batch_points(nearest_points_requests)

      for point,response in zip(page_points,nearest_points):
        yield point,response.points

@dataclass(kw_only=True)
class CollectionGraph(CollectionPoints):
  graph:nx.Graph=field(default_factory=nx.Graph,init=False)

  async def _build_graph(self)->None:
    async for point,nearest_points in self._get_nearest_points():
      self.graph.add_node(point.id)

      for nearest_point in nearest_points:
        self.graph.add_edge(
          point.id,
          nearest_point.id,
          weight=nearest_point.score
        )
  
  def _get_sorted_payloads_for_nodes(
    self,
    nodes:list|set,
    sort_by:str='record_start'
  )->list:
    return sorted(
      [self._payloads[node] for node in nodes],
      key=lambda x:getattr(x,sort_by)
    )

  def _get_avg_weight(
    self,
    nodes:set
  )->float:
    subgraph=self.graph.subgraph(nodes)
    edge_weights=[d['weight'] for _,_,d in subgraph.edges(data=True)]
    return round(
      sum(edge_weights)/len(edge_weights) if edge_weights else DEFAULT_AVG_WEIGHT,
      3
    )
  
  async def group_points(self)->AsyncIterator[PointGroup]:
    await self._build_graph()
    
    isolates=list(nx.isolates(self.graph))

    self.graph.remove_nodes_from(isolates)
    communities=louvain_communities(
      self.graph,
      resolution=1.0,
      seed=3,
      weight='weight'
    )

    for i,nodes in enumerate(communities):
      if self.settings.env=='dev':
        avg_weight=self._get_avg_weight(nodes)
      else:
        avg_weight=None

      yield PointGroup(
        group_type=PointGroupTypeStrEnum.COMMUNITIES,
        group_index=i,
        count=len(nodes),
        avg_weight=avg_weight,
        payloads=self._get_sorted_payloads_for_nodes(nodes)
      )
    
    if isolates:
      yield PointGroup(
        group_type=PointGroupTypeStrEnum.ISOLATES,
        group_index=-1,
        count=len(isolates),
        payloads=self._get_sorted_payloads_for_nodes(isolates)
      )