from pydantic import(
  AfterValidator,
  StringConstraints
)

from typing import(
  Annotated,
  Literal
)

from datetime import datetime

from app.tree.soil.func import validate_utc_timestamp

UTCTimestampT=Annotated[
  datetime,
  AfterValidator(validate_utc_timestamp)
]

StrippedStrT=Annotated[
  str,
  StringConstraints(
    strip_whitespace=True,
    min_length=1
  )
]

type EmbedTypeT=Literal[
  'document',
  'query'
]

type QueryT=Literal[
  'transcription_clustering'
]