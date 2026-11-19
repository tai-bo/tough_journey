from fastapi import(
  HTTPException,
  status
)

from datetime import(
  datetime,
  timezone
)

def validate_utc_timestamp(value:datetime)->datetime:
  if value.tzinfo!=timezone.utc:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail=(f'Expected an UTC datetime, but received: {value}.')
    )

  return value