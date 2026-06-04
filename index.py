"""SCF function: generate a time-bounded pre-signed COS upload URL."""

import os
import uuid
from qcloud_cos import CosConfig, CosS3Client

MAX_TTL = 129600  # 36 hours — hard limit for temporary keys


def main_handler(event, context):
    secret_id = os.environ["TENCENTCLOUD_SECRETID"]
    secret_key = os.environ["TENCENTCLOUD_SECRETKEY"]
    token = os.environ.get("TENCENTCLOUD_SESSIONTOKEN", "")

    bucket = os.environ["BUCKET_NAME"]          # e.g. my-bucket-1250000000
    folder = os.environ.get("FOLDER_NAME", "uploads").strip("/")
    ttl = int(os.environ.get("TTL", "3600"))     # seconds, default 1h

    if ttl < 1 or ttl > MAX_TTL:
        return {
            "error": f"TTL must be between 1 and {MAX_TTL} seconds (36 hours). Got {ttl}."
        }

    # Derive region from the function's own runtime env
    region = os.environ.get("COS_REGION") or os.environ.get("TENCENTCLOUD_REGION", "ap-singapore")

    config = CosConfig(
        Region=region,
        SecretId=secret_id,
        SecretKey=secret_key,
        Token=token,
    )
    client = CosS3Client(config)

    # Unique object key per invocation
    object_key = f"{folder}/{uuid.uuid4().hex}"

    url = client.get_presigned_url(
        Method="PUT",
        Bucket=bucket,
        Key=object_key,
        Expired=ttl,
    )

    return {
        "upload_url": url,
        "method": "PUT",
        "bucket": bucket,
        "key": object_key,
        "ttl_seconds": ttl,
        "usage": f'curl -X PUT "{url}" --data-binary @<local-file> -H "Content-Type: application/octet-stream"',
    }
