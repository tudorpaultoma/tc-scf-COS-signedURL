"""SCF function: generate a time-bounded pre-signed COS upload URL.

Supports two modes:
  1. Direct invocation — returns a single URL with a random key.
  2. API Gateway invocation — accepts filename(s) via query/body,
     returns a presigned URL per file.
"""

import json
import os
import uuid
from qcloud_cos import CosConfig, CosS3Client

MAX_TTL = 129600  # 36 hours — hard limit for temporary keys


def _build_client():
    secret_id = os.environ["TENCENTCLOUD_SECRETID"]
    secret_key = os.environ["TENCENTCLOUD_SECRETKEY"]
    token = os.environ.get("TENCENTCLOUD_SESSIONTOKEN", "")
    region = os.environ.get("COS_REGION") or os.environ.get("TENCENTCLOUD_REGION", "ap-singapore")

    config = CosConfig(
        Region=region,
        SecretId=secret_id,
        SecretKey=secret_key,
        Token=token,
    )
    return CosS3Client(config), token


def _append_token(url, token):
    """Append x-cos-security-token to presigned URL when using temporary credentials."""
    if not token:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}x-cos-security-token={token}"


def _api_response(status, body):
    return {
        "isBase64Encoded": False,
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
        "body": json.dumps(body),
    }


def main_handler(event, context):
    bucket = os.environ["BUCKET_NAME"]
    folder = os.environ.get("FOLDER_NAME", "uploads").strip("/")
    ttl = int(os.environ.get("TTL", "3600"))

    if ttl < 1 or ttl > MAX_TTL:
        return _api_response(400, {
            "error": f"TTL must be between 1 and {MAX_TTL}s (36h). Got {ttl}."
        })

    # Handle CORS preflight
    http_method = (event.get("httpMethod") or "").upper()
    if http_method == "OPTIONS":
        return _api_response(204, {})

    client, token = _build_client()

    # --- API Gateway mode: extract filenames from request ---
    filenames = []
    if event.get("queryString"):
        qs_file = event["queryString"].get("filename") or event["queryString"].get("filenames")
        if qs_file:
            filenames = [f.strip() for f in qs_file.split(",") if f.strip()]

    body = {}
    if event.get("body"):
        try:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        except (json.JSONDecodeError, AttributeError):
            body = {}

    if not filenames:
        filenames = body.get("filenames", [])
        if isinstance(filenames, str):
            filenames = [f.strip() for f in filenames.split(",") if f.strip()]

    # Allow frontend to override folder via request body
    req_folder = body.get("folder", "").strip("/")
    if req_folder:
        folder = req_folder

    # --- Direct invocation fallback: single random key ---
    if not filenames:
        object_key = f"{folder}/{uuid.uuid4().hex}"
        url = _append_token(
            client.get_presigned_url(Method="PUT", Bucket=bucket, Key=object_key, Expired=ttl),
            token,
        )
        return _api_response(200, {
            "upload_url": url,
            "method": "PUT",
            "bucket": bucket,
            "key": object_key,
            "ttl_seconds": ttl,
        })

    # --- Generate one presigned URL per filename ---
    results = []
    for fname in filenames:
        safe_name = fname.replace("\\", "/").split("/")[-1]  # basename only
        object_key = f"{folder}/{uuid.uuid4().hex[:8]}_{safe_name}"
        url = _append_token(
            client.get_presigned_url(Method="PUT", Bucket=bucket, Key=object_key, Expired=ttl),
            token,
        )
        results.append({
            "filename": fname,
            "upload_url": url,
            "key": object_key,
        })

    return _api_response(200, {
        "method": "PUT",
        "bucket": bucket,
        "ttl_seconds": ttl,
        "files": results,
    })
