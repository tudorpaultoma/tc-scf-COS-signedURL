# Tencent Cloud COS: Anonymous Upload to a Public Folder with Temporary URL

## Approach 1: Pre-Signed Upload URL (Recommended)

This is the safest and most common method. You generate a **time-limited pre-signed URL** on your server, then hand it to the anonymous user. They can `PUT` a file to that URL without any credentials.

### How it works

1. **Your backend** uses the COS SDK with your credentials (permanent key or STS temporary credentials) to generate a pre-signed URL for a specific object key (e.g., `uploads/user123/photo.jpg`).
2. You give that URL to the anonymous user.
3. They perform an HTTP `PUT` request to upload the file.
4. The URL expires after the time you set (max 36 hours with temporary keys).

### Example (Node.js SDK)

```javascript
const COS = require('cos-nodejs-sdk-v5');

const cos = new COS({
  SecretId: 'YOUR_SECRET_ID',
  SecretKey: 'YOUR_SECRET_KEY',
});

// Generate a pre-signed upload URL
cos.getObjectUrl({
  Bucket: 'my-bucket-1250000000',
  Region: 'ap-guangzhou',
  Key: 'uploads/anonymous-folder/file.txt',  // the "folder" + filename
  Method: 'PUT',
  Sign: true,
  Expires: 3600, // valid for 1 hour (in seconds)
}, function (err, data) {
  if (!err) {
    console.log('Pre-signed upload URL:', data.Url);
    // Give this URL to the anonymous user
  }
});
```

### Example (Python SDK)

```python
from qcloud_cos import CosConfig, CosS3Client

config = CosConfig(
    Region='ap-guangzhou',
    SecretId='YOUR_SECRET_ID',
    SecretKey='YOUR_SECRET_KEY',
)
client = CosS3Client(config)

# Generate pre-signed URL for upload (PUT)
url = client.get_presigned_url(
    Method='PUT',
    Bucket='my-bucket-1250000000',
    Key='uploads/anonymous-folder/myfile.pdf',
    Expired=3600,  # 1 hour
)
print(f"Upload URL: {url}")
```

### Client-side upload (curl)

```bash
curl -X PUT "https://my-bucket-1250000000.cos.ap-guangzhou.myqcloud.com/uploads/anonymous-folder/myfile.pdf?<signature-params>" \
  --data-binary @myfile.pdf \
  -H "Content-Type: application/pdf"
```

### Key points

| Aspect | Detail |
|--------|--------|
| Max validity | 36 hours (with temp keys), up to years (with permanent keys -- not recommended) |
| Max file size | 5 GB (simple upload only, no multipart) |
| Scope | Single object key -- one URL per file |
| Security | URL is useless after expiration; restrict to specific key prefix |

---

## Approach 2: Bucket Policy (Permanent Public Write to a Prefix)

If you want a **permanently open "folder"** where anyone can upload (no URL generation needed), you can set a bucket policy granting anonymous `PutObject` permission to a specific prefix. **This is risky** -- anyone who discovers the prefix can upload files.

### Bucket Policy JSON

```json
{
  "Version": "2.0",
  "Statement": [
    {
      "Principal": {
        "qcs": ["qcs::cam::anonymous:anonymous"]
      },
      "Effect": "allow",
      "Action": [
        "name/cos:PutObject"
      ],
      "Resource": [
        "qcs::cos:ap-guangzhou:uid/1250000000:my-bucket-1250000000/public-uploads/*"
      ]
    }
  ]
}
```

### How to apply via Console

1. Go to **COS Console > Bucket > Permission Management > Policy Permission Settings**
2. Click **Add Policy**
3. Set:
   - **Principal**: All users (anonymous access) / `*`
   - **Effect**: Allow
   - **Action**: `PutObject` only
   - **Resource**: `public-uploads/*` (your "folder" prefix)
4. Save.

Now anyone can upload to:

```
PUT https://my-bucket-1250000000.cos.ap-guangzhou.myqcloud.com/public-uploads/anything.txt
```

No signature needed. **But be careful** -- add safeguards:

- Don't grant `GetObject` or `ListBucket` (prevents browsing)
- Use lifecycle rules to auto-delete old uploads
- Monitor upload volume with COS logging

---

## Approach 3: STS Temporary Credentials (Best for Web Apps)

For frontend direct-upload scenarios (e.g., a web form), use **STS (Security Token Service)** to issue short-lived, scoped credentials:

```javascript
// Backend: generate scoped temporary credentials
const STS = require('qcloud-cos-sts');

const policy = {
  version: '2.0',
  statement: [{
    action: ['name/cos:PutObject'],
    effect: 'allow',
    resource: [
      'qcs::cos:ap-guangzhou:uid/1250000000:my-bucket-1250000000/uploads/${filename}'
    ],
  }],
};

STS.getCredential({
  secretId: 'YOUR_SECRET_ID',
  secretKey: 'YOUR_SECRET_KEY',
  durationSeconds: 1800,  // 30 minutes
  policy: policy,
}, function (err, credential) {
  // Return credential to frontend
  // Frontend uses it to upload directly to COS
});
```

---

## Summary: Which to Choose?

| Method | Use Case | Security | Complexity |
|--------|----------|----------|------------|
| **Pre-signed URL** | One-off uploads, sharing a link | High (time-limited, single key) | Low |
| **Bucket Policy** | Always-open upload drop box | Medium (permanent, must restrict actions) | Very low |
| **STS Credentials** | Web app with frontend direct upload | High (scoped, short-lived) | Medium |

## Recommendation

Use **pre-signed URLs** for most cases. Your server generates the URL on demand (controlling who gets it, what prefix they upload to, and for how long), and the anonymous user just performs a simple HTTP PUT. This gives you fine-grained control without exposing your bucket to the world.

---

## References

- [Accessing COS Using a Pre-Signed URL](https://www.tencentcloud.com/document/product/436/45243)
- [Upload via Pre-Signed URL](https://www.tencentcloud.com/document/product/436/14114)
- [Bucket Policy](https://www.tencentcloud.com/document/product/436/45235)
- [COS API Authorization Policy Guide](https://www.tencentcloud.com/document/product/436/30580)
