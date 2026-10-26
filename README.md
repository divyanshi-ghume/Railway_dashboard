# RailPulse — Indian Railway Analytics Dashboard

A Streamlit dashboard that reads train and station Gold Parquet snapshots from a **private** S3 bucket. The Airflow/PySpark pipeline can continue running independently; this app reads the latest complete object when it reruns and caches it for five minutes.

## Run locally

```powershell
cd dashboard
python -m pip install -r requirements.txt
streamlit run app.py
```

Add these keys to Streamlit Community Cloud's app **Secrets** settings (or put them in `.streamlit/secrets.toml` at the repository root for local development; that file is ignored by Git):

```toml
AWS_ACCESS_KEY_ID = "YOUR_READ_ONLY_ACCESS_KEY_ID"
AWS_SECRET_ACCESS_KEY = "YOUR_READ_ONLY_SECRET_ACCESS_KEY"
AWS_REGION = "ap-southeast-2"
S3_BUCKET_NAME = "your-railway-bucket"
S3_GOLD_PREFIX = "railway-gold/"
# Optional: only needed for temporary AWS credentials
AWS_SESSION_TOKEN = "YOUR_SESSION_TOKEN"
```

The app recognizes these top-level secret names, as well as `AWS_DEFAULT_REGION` and the earlier `S3_BUCKET`, `TRAIN_PREFIX`, and `STATION_PREFIX` configuration. `S3_GOLD_PREFIX` is the common root: Parquet object paths or filenames beneath it must identify the dataset as `train`/`trains` or `station`/`stations`. If your objects use different naming, set `TRAIN_PREFIX` and `STATION_PREFIX` to their exact S3 prefixes instead. The matching dataset prefix must be readable by the IAM identity.

AWS credentials can alternatively be supplied through environment variables. Never commit credentials or paste them into chat.

## Least-privilege IAM policy

Create a dedicated IAM user/access key for Streamlit Community Cloud (never use root credentials). Substitute your bucket and Gold prefix to match the app settings:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::your-railway-bucket",
      "Condition": {
        "StringLike": {
          "s3:prefix": ["railway-gold/*"]
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": [
        "arn:aws:s3:::your-railway-bucket/railway-gold/*"
      ]
    }
  ]
}
```

This dashboard needs no S3 write, delete, or public-bucket permissions. If you use a bucket encryption key managed by AWS KMS, the identity may also need narrowly scoped `kms:Decrypt` permission for that key.

## Deploy to Streamlit Community Cloud

1. Push this project to a GitHub repository. Keep `.streamlit/secrets.toml` out of Git.
2. In Streamlit Community Cloud, create an app from the repository and set **Main file path** to `dashboard/app.py`.
3. In the app's **Advanced settings → Secrets**, add the TOML configuration above with your actual bucket, prefixes, region, and dedicated read-only credentials.
4. Deploy, then check the **Data freshness** tab and confirm both snapshots are being read. If the app already existed, reboot it after changing secrets or code.

Treat Streamlit secrets like passwords. Restrict repository access, rotate the access key if it is exposed, and prefer temporary credentials or an AWS-hosted backend with an IAM role for production.

## Data assumptions

- The configured train and station prefixes each contain at least one `.parquet` object.
- When using one `S3_GOLD_PREFIX`, object paths or filenames beneath it must distinguish train and station datasets. Otherwise set `TRAIN_PREFIX` and `STATION_PREFIX` separately.
- The app loads the most recently modified single Parquet object under each prefix. Have the pipeline publish a complete snapshot (for example, a uniquely named file) rather than overwriting a file while it is being read.
- Cache lifetime is five minutes. Use **Refresh data** to clear the cache and fetch the current snapshots immediately.
- Charts adapt to recognized train/station label columns and numeric columns. Share the exact Gold column names and S3 prefixes if you want the metrics and chart labels tailored to your pipeline.
