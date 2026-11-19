from typing import Annotated

from fastapi import Depends

from app.tree.root.func import(
  LifeSpanResources,
  get_life_span_resources
)

ResourcesT=Annotated[LifeSpanResources,Depends(get_life_span_resources)]