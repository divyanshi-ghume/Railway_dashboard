Here’s a complete README you can copy into your GitHub repository and edit as needed. It describes the dashboard we built and the data/configuration it currently expects.

````markdown
# 🚆 RailPulse — Indian Railways Analytics Dashboard

RailPulse is an interactive dashboard for exploring Indian Railway train and station analytics. It reads Parquet datasets from a private Amazon S3 Gold layer and presents the data in a dark-themed Streamlit app.

The dashboard is designed to work alongside an Airflow and PySpark data pipeline: the pipeline processes and publishes Gold data, while the dashboard reads the latest available train and station snapshots.

> **Hosting:** Streamlit Community Cloud  
> **Data storage:** Private Amazon S3  
> **Data format:** Apache Parquet

---

## Dashboard features

- **Dark interface** with high-contrast text, charts, and metric cards.
- **Overview page** with train and station charts.
- **Train and station analytics** with controls to choose:
  - A numeric performance metric.
  - A category to group results by.
  - How many top results to display.
  - Optional category values to filter.
- **Summary metrics**, including record counts, unique trains and stations, and additional averages when matching numeric columns are available.
- **Metric distribution charts** to help explore variation in the selected data.
- **Filtered CSV downloads** for train and station data.
- **Data freshness view** showing the source Parquet files and their last-modified timestamps.
- **Data quality summary** with row and column counts, missing values, duplicate rows, and numeric metric counts.
- **Manual refresh button** to clear the data cache and fetch the current S3 snapshots.

KPIs and charts adapt to the columns in your Parquet data. Metrics such as average delay, distance, or passenger count appear when the matching columns exist.

---

## Architecture

```text
Airflow DAG
    │
    ▼
PySpark transformations
    │
    ▼
Amazon S3 — Gold layer
    ├── Train analytics (Parquet)
    └── Station analytics (Parquet)
              │
              ▼
Streamlit Community Cloud
              │
              ▼
Interactive RailPulse dashboard
```

The dashboard does not run the Airflow or PySpark pipeline. It reads data that the pipeline has already published to S3.

---

## Technology stack

| Technology | Purpose |
|---|---|
| Python | Dashboard application |
| Streamlit | Web interface, user controls, and hosting |
| Amazon S3 | Private storage for Gold datasets |
| Boto3 | Connects to S3 and reads objects |
| pandas | Loads, filters, summarizes, and exports data |
| PyArrow | Reads Parquet files |
| Plotly Express | Interactive charts |

Python dependencies are listed in [`dashboard/requirements.txt`](dashboard/requirements.txt).

---

## Expected S3 data layout

The dashboard can use either separate prefixes for train and station data, or a shared Gold prefix with recognizable train and station paths.

### Option 1: Separate prefixes

```text
s3://YOUR_BUCKET/YOUR_TRAIN_PREFIX/train_snapshot.parquet
s3://YOUR_BUCKET/YOUR_STATION_PREFIX/station_snapshot.parquet
```

Configure these secrets:

```toml
TRAIN_PREFIX = "railway-gold/trains/"
STATION_PREFIX = "railway-gold/stations/"
```

### Option 2: One shared Gold prefix

```text
s3://YOUR_BUCKET/railway-gold/trains/train_snapshot.parquet
s3://YOUR_BUCKET/railway-gold/stations/station_snapshot.parquet
```

Configure:

```toml
S3_GOLD_PREFIX = "railway-gold/"
```

With a shared prefix, the dashboard looks for `train`/`trains` and `station`/`stations` in the Parquet object paths or filenames. If your pipeline uses different names, configure `TRAIN_PREFIX` and `STATION_PREFIX` with the exact prefixes instead.

The app selects the **most recently modified Parquet object** for each dataset. Publish complete snapshots with distinct object names or otherwise ensure a snapshot is complete before the dashboard reads it. The current app reads one Parquet object per dataset; it does not combine a multi-file partitioned Parquet dataset.

---

## Set up Streamlit secrets

The dashboard needs read-only credentials to access a private S3 bucket. Add the following as top-level entries in the Streamlit app's **Secrets** settings:

```toml
AWS_ACCESS_KEY_ID = "YOUR_READ_ONLY_ACCESS_KEY_ID"
AWS_SECRET_ACCESS_KEY = "YOUR_READ_ONLY_SECRET_ACCESS_KEY"
AWS_REGION = "YOUR_BUCKET_REGION"
S3_BUCKET_NAME = "YOUR_BUCKET_NAME"
S3_GOLD_PREFIX = "railway-gold/"
```

Alternatively, use separate prefixes:

```toml
AWS_ACCESS_KEY_ID = "YOUR_READ_ONLY_ACCESS_KEY_ID"
AWS_SECRET_ACCESS_KEY = "YOUR_READ_ONLY_SECRET_ACCESS_KEY"
AWS_REGION = "YOUR_BUCKET_REGION"
S3_BUCKET_NAME = "YOUR_BUCKET_NAME"
TRAIN_PREFIX = "railway-gold/trains/"
STATION_PREFIX = "railway-gold/stations/"
```

If you use temporary AWS credentials, add the session token too:

```toml
AWS_SESSION_TOKEN = "YOUR_SESSION_TOKEN"
```

**Never commit credentials to GitHub or paste them into chat.** The repository ignores `.streamlit/secrets.toml` for local development. For hosted deployments, use Streamlit's Secrets settings rather than committing a local secrets file.

---

## AWS permissions

Create a dedicated IAM identity for the dashboard. Do not use your AWS root credentials. Grant only the permissions needed to list and read the Gold objects.

Example policy for a bucket with the shared `railway-gold/` prefix—replace the example bucket name and prefix with your own:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME",
      "Condition": {
        "StringLike": {
          "s3:prefix": [
            "railway-gold/*"
          ]
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/railway-gold/*"
    }
  ]
}
```

For separate prefixes, limit `s3:prefix` and `s3:GetObject` resources to those two prefixes. The dashboard does **not** need S3 write or delete permissions, and the bucket does **not** need to be public.

If your objects use SSE-KMS encryption, the IAM identity may also require narrowly scoped `kms:Decrypt` access to the key used by the bucket.

---

## Deploy to Streamlit Community Cloud

1. Push the project to GitHub.
2. Sign in to Streamlit Community Cloud and create an app from the repository.
3. Select the `main` branch.
4. Set the **Main file path** to:

   ```text
   dashboard/app.py
   ```

5. Open the app's **Advanced settings → Secrets** and add the configuration described above using your actual bucket, region, prefixes, and read-only credentials.
6. Deploy the app.
7. Open the dashboard and check **Data freshness** to confirm that both datasets loaded successfully.

After changing the code or Secrets, wait for the app to redeploy or reboot it from Streamlit Community Cloud.

---

## Run locally

From the repository root:

```powershell
python -m pip install -r dashboard/requirements.txt
```

Create `.streamlit/secrets.toml` in the repository root with the configuration shown above. This file is ignored by Git. Then start the dashboard:

```powershell
python -m streamlit run dashboard/app.py
```

Open the local URL printed in the terminal.

---

## Data refresh behavior

S3 data is cached for five minutes to avoid downloading the Parquet files on every Streamlit rerun.

The dashboard does not continuously poll S3 in the background. It loads fresh data when the app reruns after the cache expires, or when the **Refresh data** button is clicked. Publishing new Gold data does not automatically trigger an app rerun.

---

## Customization

Charts and KPIs use the columns found in the train and station Parquet files. To improve the dashboard's automatic chart choices, use clear column names where practical, such as:

```text
train_number
train_name
avg_delay_min
distance_km
station_code
station_name
passenger_count
```

If your Gold datasets use different column names or paths, update the S3 prefixes in Streamlit Secrets or customize the dashboard's recognized columns and metrics in `dashboard/app.py`.

---

## Security notes

- Keep the S3 bucket private.
- Use a dedicated, read-only IAM identity for the dashboard.
- Store credentials in Streamlit Secrets, not in source code or Git.
- Never use AWS root credentials for the app.
- Rotate the IAM access key if it is exposed.
- Consider short-lived credentials or an AWS-hosted backend with an IAM role for production deployments.

---
````
