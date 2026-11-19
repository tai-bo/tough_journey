from tests.conftest import get_storage_client

def get_file_meta(bucket_name):
    storage_client=get_storage_client()
    bucket = storage_client.bucket(bucket_name)
    blobs = bucket.list_blobs(max_results=50)
    for blob in blobs:
        if blob.name.lower().endswith('.m4a'):
            return blob.name
    return None



