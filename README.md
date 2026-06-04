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

## IAM Policy & Execution Role

1. **Create a CAM custom policy** using `cos-policy.json` (grants `PutObject`, `GetObject`, `HeadObject`, `GetBucket` on all COS resources).
2. **Create a CAM role** with trust entity `scf.tencentcloudapi.com`.
3. **Attach the policy** to the role.
4. **Bind the role** to the SCF function as its execution role.

To scope the policy to a specific bucket, replace the `resource` value:

```json
"resource": [
  "qcs::cos:<region>::<bucket-name>/*"
]
```

## Build & Deploy

```bash
chmod +x build_scf.sh
./build_scf.sh
# Upload scf-cos-signedurl.zip to SCF
```

**Handler:** `index.main_handler`

## Web Frontend

`index.html` is a self-contained upload page — host it at the COS bucket root for public access.

**Setup:**
1. Upload `index.html` to the bucket root
2. Enable static website hosting or set public-read on the object
3. On the `index.html` object, add custom header `Content-Disposition` → `inline` (required if the bucket has force-download enabled at bucket level)
4. Create an **API Gateway** trigger for the SCF function
5. Open the page, enter the API Gateway URL and target folder, pick files, hit Upload

The page sends a `POST` with `{ "filenames": [...], "folder": "..." }` to the SCF, receives presigned URLs, then PUTs each file directly to COS.

## API Usage

**POST** to API Gateway with JSON body:

```json
{ "filenames": ["report.pdf", "photo.jpg"], "folder": "customer-uploads" }
```

Response:

```json
{
  "method": "PUT",
  "bucket": "my-bucket-1250000000",
  "ttl_seconds": 3600,
  "files": [
    { "filename": "report.pdf", "upload_url": "https://...", "key": "customer-uploads/a1b2c3d4_report.pdf" },
    { "filename": "photo.jpg", "upload_url": "https://...", "key": "customer-uploads/e5f6a7b8_photo.jpg" }
  ]
}
```

**Direct invocation** (no filenames) returns a single URL with a random key.

## Client Upload (curl)

```bash
curl -X PUT "<upload_url>" --data-binary @myfile.pdf -H "Content-Type: application/pdf"
```

## TTL Limits

- **Temporary keys** (SCF execution role): max **36 hours** (129,600 seconds)
- **Permanent keys**: unlimited (not recommended for security reasons)
