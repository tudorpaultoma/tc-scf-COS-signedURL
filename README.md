# tc-scf-COS-signedURL

Tencent Cloud SCF function that generates **time-bounded pre-signed COS PUT URLs** for anonymous file uploads, paired with a self-hosted HTML5 upload frontend.

---

## Architecture

```
Browser (index.html on COS)
  │
  │  POST { filenames, folder }
  ▼
SCF Function  ──── CAM execution role ────▶ generates pre-signed PUT URL(s)
  │
  │  returns { files: [{ filename, upload_url, key }] }
  ▼
Browser
  │
  │  PUT <file bytes>  (direct to COS, no credentials needed)
  ▼
COS Bucket  /uploads/<filename>
```

- The browser **never touches credentials** — it only uses the time-limited signed URL.
- SCF signs with the **CAM execution role**'s temporary credentials + session token, both embedded in the URL.
- Max URL validity with temporary credentials: **36 hours (129,600 seconds)**.

---

## Repository Contents

| File | Purpose |
|------|---------|
| `index.py` | SCF handler — generates presigned URLs |
| `index.html` | Self-hosted upload frontend (deploy to COS root) |
| `requirements.txt` | Python dependencies |
| `build_scf.sh` | Builds `scf-cos-signedurl.zip` for SCF upload |
| `cos-policy.json` | CAM policy template for the SCF execution role |

---

## Prerequisites

- Tencent Cloud account with COS and SCF enabled in the target region
- A COS bucket (e.g. `my-bucket-1250000000`) in the target region
- Python 3.9 (SCF runtime) / Python 3.x locally for building

---

## 1. IAM — Create Execution Role

The SCF function uses a **CAM role** to sign presigned URLs. No hardcoded credentials needed.

### 1a. Create the policy

1. Go to **CAM Console → Policies → Create Custom Policy → Create by Policy Syntax**
2. Paste the contents of `cos-policy.json`
3. Name it e.g. `scf-cos-upload-policy`

To scope to a specific bucket (recommended), replace the `resource` wildcard:
```json
"resource": [
  "qcs::cos:ap-singapore:uid/<AppId>:my-bucket-<AppId>/*"
]
```

### 1b. Create the role

1. Go to **CAM Console → Roles → Create Role**
2. Trust entity: **Tencent Cloud Product → SCF**  
   (this sets trust entity to `scf.tencentcloudapi.com`)
3. Attach the policy created above
4. Name it e.g. `scf-cos-upload-role`

### 1c. Bind the role to the SCF function

In the SCF function configuration → **Execution Role** → select `scf-cos-upload-role`.

SCF will then inject `TENCENTCLOUD_SECRETID`, `TENCENTCLOUD_SECRETKEY`, and `TENCENTCLOUD_SESSIONTOKEN` automatically at runtime.

---

## 2. SCF Function — Build & Deploy

### Build the deployment zip

```bash
chmod +x build_scf.sh
./build_scf.sh
# Output: scf-cos-signedurl.zip (~2.3 MB)
```

### Deploy to SCF

1. SCF Console → **Create Function** (or open existing)
2. Runtime: **Python 3.9**
3. Upload method: **Upload zip** → select `scf-cos-signedurl.zip`
4. Handler: `index.main_handler`
5. Memory: 128 MB (sufficient)
6. Execution role: `scf-cos-upload-role` (from step 1c)

### Environment Variables

Set these in the SCF function configuration:

| Variable | Required | Description |
|----------|----------|-------------|
| `BUCKET_NAME` | **Yes** | Full bucket name (e.g. `my-bucket-1250000000`) |
| `FOLDER_NAME` | No | Upload prefix inside the bucket (default: `uploads`) |
| `TTL` | No | Presigned URL validity in seconds (default: `3600`, max: `129600`) |
| `COS_REGION` | No | COS bucket region (e.g. `eu-frankfurt`). Falls back to `TENCENTCLOUD_REGION` if unset |

### Create a Function URL trigger

1. SCF Console → your function → **Trigger Management → Create Trigger**
2. Trigger type: **Function URL** (or API Gateway if available)
3. Auth: **No auth**
4. Enable CORS: **Yes** — configure:
   - Allowed Origin: `*`
   - Allowed Methods: `GET, POST, OPTIONS`
   - Allowed Headers: `*`
   - Max Age: `600`
5. Copy the resulting URL — you'll need it for the frontend.

---

## 3. COS Bucket — Setup

### CORS (required for browser uploads)

**COS Console → your bucket → Security Management → CORS → Add Rule:**

| Field | Value |
|-------|-------|
| Allowed Origin | `*` |
| Allowed Methods | `PUT, GET, POST, HEAD` |
| Allowed Headers | `*` |
| Expose Headers | `ETag` |
| Max Age | `600` |

Without this, the browser's preflight OPTIONS request to COS will be rejected and the PUT will never fire.

### Static Website Hosting (for the frontend)

1. **COS Console → your bucket → Basic Configuration → Static Website → Enable**
2. Index document: `index.html`
3. Your frontend URL will be:  
   `https://<bucket>.cos-website.<region>.myqcloud.com`

---

## 4. Frontend — Deploy index.html

1. Upload `index.html` to the **bucket root**
2. Set object permissions: **public-read**
3. Set custom HTTP header on the object:
   - `Content-Disposition` → `inline`  
     *(required — COS buckets have force-download enabled by default; this overrides it so the browser renders the page instead of downloading it)*
4. Open the static website URL in a browser

> **Note:** Every time you re-upload `index.html`, you must re-set the `Content-Disposition: inline` header on the object. Use `coscmd` to automate this:
> ```bash
> coscmd upload -H '{"Content-Type":"text/html; charset=utf-8","Content-Disposition":"inline"}' index.html /index.html
> ```

---

## 5. Using the Frontend

1. Open `https://<bucket>.cos-website.<region>.myqcloud.com`
2. Enter the **Function URL** from step 2 into the "API Gateway URL" field
3. Optionally change the **Folder Name** (overrides the `FOLDER_NAME` env var for this request)
4. Drag & drop files or click to browse — multiple files supported
5. Click **Upload**
   - Each file shows a status: `pending → uploading… → done ✓` or `failed ✗`
   - Successfully uploaded files are removed from the list automatically
   - Failed files remain for retry

Files are stored in COS at: `<FOLDER_NAME>/<original-filename>`

---

## 6. API Reference

The SCF function accepts HTTP POST requests (via Function URL or API Gateway).

### Request

```
POST <function-url>
Content-Type: application/json
```

```json
{
  "filenames": ["report.pdf", "photo.jpg"],
  "folder": "customer-uploads"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `filenames` | `string[]` | Yes | List of filenames to generate URLs for |
| `folder` | `string` | No | Overrides the `FOLDER_NAME` env var for this request |

### Response

```json
{
  "method": "PUT",
  "bucket": "my-bucket-1250000000",
  "ttl_seconds": 3600,
  "files": [
    {
      "filename": "report.pdf",
      "upload_url": "https://my-bucket-1250000000.cos.eu-frankfurt.myqcloud.com/uploads/report.pdf?q-sign-algorithm=sha1&...&x-cos-security-token=...",
      "key": "uploads/report.pdf"
    },
    {
      "filename": "photo.jpg",
      "upload_url": "https://my-bucket-1250000000.cos.eu-frankfurt.myqcloud.com/uploads/photo.jpg?...",
      "key": "uploads/photo.jpg"
    }
  ]
}
```

**Direct invocation** (no `filenames`): returns a single URL with a random UUID key.

### CORS

The function returns `Access-Control-Allow-Origin: *` on all responses and handles OPTIONS preflight automatically.

---

## 7. Upload a File (curl)

```bash
# Step 1: get a presigned URL
RESPONSE=$(curl -s -X POST "<function-url>" \
  -H "Content-Type: application/json" \
  -d '{"filenames": ["myfile.pdf"]}')

UPLOAD_URL=$(echo $RESPONSE | python3 -c "import sys,json; print(json.load(sys.stdin)['files'][0]['upload_url'])")

# Step 2: PUT the file
curl -X PUT "$UPLOAD_URL" --data-binary @myfile.pdf
```

---

## TTL Limits

| Credential type | Max TTL |
|----------------|---------|
| Temporary key (SCF execution role) | **36 hours = 129,600 seconds** |
| Permanent key | Unlimited (not recommended) |

The URL validity is `min(TTL_setting, session_token_expiry)`. SCF session tokens issued to execution roles are valid up to 36 hours.

---

## Known Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| `index.html` downloads instead of opening | Bucket has force-download enabled | Set `Content-Disposition: inline` on the object |
| Upload fails with `InvalidAccessKeyId` | Presigned URL signed with expired temp key | Ensure execution role is bound; `x-cos-security-token` must be in the URL |
| Upload fails silently in browser | Missing COS CORS rule | Add CORS rule allowing `PUT` from `*` on the bucket |
| Cached CORS failure in browser | Browser cached a pre-CORS-config preflight rejection | Open a new browser / clear cache |
| `SignatureDoesNotMatch` | Extra headers sent in PUT that weren't in the signature | Do not set `Content-Type` on the PUT request — the URL only signs `host` |
