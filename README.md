# tc-scf-COS-signedURL

Tencent Cloud SCF function that generates a **time-bounded pre-signed COS URL** for anonymous file uploads (HTTP PUT).

## How it works

1. SCF is invoked (API Gateway, manual trigger, etc.)
2. Generates a unique object key under the configured folder
3. Returns a pre-signed PUT URL valid for the configured TTL
4. Any anonymous user can upload a file using that URL — no credentials needed

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BUCKET_NAME` | Yes | Full bucket name (e.g. `my-bucket-1250000000`) |
| `FOLDER_NAME` | No | Upload prefix/folder (default: `uploads`) |
| `TTL` | No | URL validity in seconds (default: `3600`, max: `129600` = 36h) |
| `COS_REGION` | No | COS bucket region (falls back to `TENCENTCLOUD_REGION`) |

> SCF injects `TENCENTCLOUD_SECRETID`, `TENCENTCLOUD_SECRETKEY`, and `TENCENTCLOUD_SESSIONTOKEN` automatically when an execution role is bound.

## Build & Deploy

```bash
chmod +x build_scf.sh
./build_scf.sh
# Upload scf-cos-signedurl.zip to SCF
```

**Handler:** `index.main_handler`

## Response Example

```json
{
  "upload_url": "https://my-bucket-1250000000.cos.ap-singapore.myqcloud.com/uploads/a1b2c3...?sign=...",
  "method": "PUT",
  "bucket": "my-bucket-1250000000",
  "key": "uploads/a1b2c3d4e5f6...",
  "ttl_seconds": 3600,
  "usage": "curl -X PUT \"<url>\" --data-binary @<local-file> -H \"Content-Type: application/octet-stream\""
}
```

## Client Upload

```bash
curl -X PUT "<upload_url>" --data-binary @myfile.pdf -H "Content-Type: application/pdf"
```

## TTL Limits

- **Temporary keys** (SCF execution role): max **36 hours** (129,600 seconds)
- **Permanent keys**: unlimited (not recommended for security reasons)
