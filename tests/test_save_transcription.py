import pytest
from fastapi import status
from tests.conftest import PROJECT_ID
from tests.utils import get_file_meta

bucket_name=f"{PROJECT_ID}-user-input-us-central1"
test_case = [
    (bucket_name, "", status.HTTP_500_INTERNAL_SERVER_ERROR),
    (bucket_name, "pytest file.m4a", status.HTTP_404_NOT_FOUND)
    ]

for attempt in range(1, 4):
    filepath = get_file_meta(bucket_name)
    if filepath:
        break
test_case_valid=[(bucket_name, filepath, status.HTTP_201_CREATED)]
test_case.extend(test_case_valid)

@pytest.mark.asyncio
@pytest.mark.parametrize("bucket_name, blob_name, expected_status", test_case)
async def test_save_transcription_success(client, bucket_name, blob_name, expected_status):
    payload = {
        "bucket_name": bucket_name,
        "blob_name": blob_name
    }
    print(payload)
    response = await client.post("/save_transcription", json=payload)

    # Assertions
    assert response.status_code == expected_status    
    if expected_status == status.HTTP_201_CREATED:
        data = response.json()
        assert "record_file_uuid" in data