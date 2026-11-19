from fastapi import(
  HTTPException,
  status,
  APIRouter
)

from pydantic import BaseModel

from datetime import datetime

from app.tree.trunk.vdb import(
  CollectionGraph,
  DateRange,
  PointGroup
)
from app.tree.trunk.common import ResourcesT

class Payload(BaseModel):
  auth_uid:str
  from_datetime:datetime|None=None
  to_datetime:datetime|None=None

class Response(BaseModel):
  groups:list[PointGroup]

router=APIRouter()
@router.post(
  "/group_transcription",
  status_code=status.HTTP_200_OK
)
async def group_transcription(
  payload:Payload,
  resources:ResourcesT
)->Response:
  try:
    collection_graph=CollectionGraph(
      client=resources.qdrant_client,
      settings=resources.settings,
      query='transcription_clustering',
      auth_uid=payload.auth_uid,
      date_range=DateRange(
        from_datetime=payload.from_datetime,
        to_datetime=payload.to_datetime
      )
    )

    collection_graph.points=await collection_graph.get_all_points()

    groups=[group async for group in collection_graph.group_points()]

    return Response(groups=groups)
  
  except HTTPException:
    raise

  except Exception as e:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail=f'Exception: {str(e)}.'
    )