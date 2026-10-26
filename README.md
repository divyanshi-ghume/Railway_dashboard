# 🚆 RailPulse — Indian Railways Analytics Dashboard

<p align="center">
  <strong>Turning Indian Railways Data into Actionable Insights</strong>
</p>

<p align="center">
  An interactive, dark-themed analytics dashboard that transforms Indian Railway train and station data into meaningful insights using Streamlit, Amazon S3, Parquet, and PySpark.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit"/>
  <img src="https://img.shields.io/badge/AWS-Amazon%20S3-FF9900?logo=amazons3&logoColor=white" alt="Amazon S3"/>
  <img src="https://img.shields.io/badge/Format-Parquet-50ABF1" alt="Parquet"/>
  <img src="https://img.shields.io/badge/Processing-PySpark-E25A1C?logo=apachespark&logoColor=white" alt="PySpark"/>
  <img src="https://img.shields.io/badge/Orchestration-Apache%20Airflow-017CEE?logo=apacheairflow&logoColor=white" alt="Apache Airflow"/>
</p>

---

## 📌 Overview

**RailPulse** is a data analytics dashboard designed to explore Indian Railway train and station performance through interactive visualizations, summary metrics, and downloadable datasets.

The dashboard works alongside an automated data engineering pipeline built with Apache Airflow and PySpark. The pipeline processes railway data and publishes analytical datasets to a private Amazon S3 Gold layer, while RailPulse reads the latest available snapshots for visualization.

With RailPulse, users can explore railway analytics, compare performance metrics, inspect data quality, and monitor dataset freshness through a single interface.

### ✨ Key Highlights

- 📊 Interactive train and station analytics
- ☁️ Secure integration with private Amazon S3
- ⚡ Parquet-based analytical data access
- 🔄 Manual refresh and five-minute data caching
- 🧹 Data quality and missing-value analysis
- 📥 Filtered CSV exports
- 🌑 Modern dark-themed interface
- 🚀 Deployment-ready for Streamlit Community Cloud

---

## 📸 Dashboard Features

### 1. 📊 Analytics Overview
- View train and station datasets through interactive charts.
- Explore available performance indicators.
- Display record counts and other relevant summary metrics.
- Automatically adapt visualizations to the available dataset columns.

### 2. 🚆 Train Analytics
- Analyze train-level performance metrics.
- Select a numeric metric for comparison.
- Group results by a suitable categorical column.
- Choose how many top results to display.
- Apply optional category filters.
- Download filtered train data as CSV.

### 3. 🚉 Station Analytics
- Explore station-level performance and available metrics.
- Compare categories using interactive charts.
- Investigate metric distributions.
- Download filtered station data as CSV.

### 4. 📈 Dynamic KPIs and Charts
The dashboard identifies compatible columns in the Parquet datasets and generates relevant statistics where possible.

Depending on the available data, these may include:
- Total records
- Unique trains and stations
- Average delay
- Distance-related metrics
- Passenger counts
- Numeric metric distributions

> KPI availability depends on the column names, data types, and contents of the published datasets.

### 5. 🔍 Data Quality Monitoring
Inspect the structure and quality of each loaded dataset, including:
- Total rows and columns
- Missing values
- Duplicate rows
- Numeric column statistics

### 6. 🕒 Data Freshness
- Inspect the selected source Parquet files.
- View their last-modified timestamps from Amazon S3.
- Verify which datasets have been loaded successfully.

### 7. 🔄 Manual Data Refresh
Use the **Refresh Data** button to clear the cached dataset results and request the latest available S3 snapshots.

### 8. 📥 CSV Export
Export filtered train and station records for further analysis, reporting, or offline exploration.

---

## 🏗️ System Architecture

RailPulse separates data processing from data visualization. The upstream pipeline prepares analytical datasets, and the dashboard consumes the published Gold data.

```text
                RAILWAY DATA SOURCES
                         |
                         v
              APACHE AIRFLOW DAG
              (Pipeline Orchestration)
                         |
                         v
                PYSPARK PROCESSING
                (Clean & Transform)
                         |
                         v
              AMAZON S3 — GOLD LAYER
                  /             \
                 v               v
          Train Analytics   Station Analytics
             (Parquet)         (Parquet)
                  \             /
                   \           /
                    v         v
               STREAMLIT APP
            (Streamlit Community
                   Cloud)
                         |
                         v
               RAILPULSE DASHBOARD
          Analytics | KPIs | Charts
          Data Quality | CSV Export
```

### Architecture Responsibilities

| Component | Responsibility |
|---|---|
| Apache Airflow | Orchestrates the upstream data pipeline |
| PySpark | Processes, cleans, and transforms railway datasets |
| Amazon S3 | Stores the published Gold datasets privately |
| Apache Parquet | Provides a columnar format for analytical data |
| Boto3 | Connects the dashboard to Amazon S3 |
| pandas | Loads, filters, summarizes, and exports datasets |
| Streamlit | Provides the interactive web interface |
| Plotly Express | Creates interactive charts |

**Important:** RailPulse does not execute the Airflow DAG or run PySpark transformations. It reads data that the upstream pipeline has already published to Amazon S3.

---

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Application development |
| Streamlit | Dashboard UI and hosting |
| Amazon S3 | Private cloud storage |
| Boto3 | AWS S3 integration |
| pandas | Data manipulation and analysis |
| PyArrow | Parquet file reading |
| Plotly Express | Interactive data visualization |
| Apache Airflow | Upstream pipeline orchestration |
| PySpark | Upstream data transformation |
| GitHub | Source code management |

Application dependencies are maintained in [`dashboard/requirements.txt`](dashboard/requirements.txt).

---

## 📂 Project Structure

The dashboard portion of the repository follows this structure:

```text
RailPulse/
├── dashboard/
│   ├── app.py
│   └── requirements.txt
├── .streamlit/
│   └── secrets.toml        # Local only; never commit
├── .gitignore
└── README.md
```

Your complete repository may also contain Airflow DAGs, PySpark transformations, ingestion scripts, tests, and other pipeline components.

---

## ☁️ Amazon S3 Gold Layer Configuration

RailPulse reads train and station analytics from a private S3 bucket.

### Option 1: Separate Dataset Prefixes

Recommended when train and station analytics are published to separate prefixes.

```text
s3://YOUR_BUCKET/YOUR_TRAIN_PREFIX/train_snapshot.parquet
s3://YOUR_BUCKET/YOUR_STATION_PREFIX/station_snapshot.parquet
```

Example Streamlit Secrets configuration:

```toml
AWS_ACCESS_KEY_ID = "YOUR_READ_ONLY_ACCESS_KEY_ID"
AWS_SECRET_ACCESS_KEY = "YOUR_READ_ONLY_SECRET_ACCESS_KEY"
AWS_REGION = "YOUR_BUCKET_REGION"
S3_BUCKET_NAME = "YOUR_BUCKET_NAME"

TRAIN_PREFIX = "railway-gold/trains/"
STATION_PREFIX = "railway-gold/stations/"
```

### Option 2: Shared Gold Prefix

Use a common Gold prefix when train and station data are stored under separate subdirectories.

```text
s3://YOUR_BUCKET/railway-gold/trains/train_snapshot.parquet
s3://YOUR_BUCKET/railway-gold/stations/station_snapshot.parquet
```

Configure:

```toml
AWS_ACCESS_KEY_ID = "YOUR_READ_ONLY_ACCESS_KEY_ID"
AWS_SECRET_ACCESS_KEY = "YOUR_READ_ONLY_SECRET_ACCESS_KEY"
AWS_REGION = "YOUR_BUCKET_REGION"
S3_BUCKET_NAME = "YOUR_BUCKET_NAME"

S3_GOLD_PREFIX = "railway-gold/"
```

The application can discover train and station objects using recognizable names and paths. If your pipeline uses different directory names, configure `TRAIN_PREFIX` and `STATION_PREFIX` explicitly.

Replace every placeholder with your actual configuration. Do not copy the example values literally.

### Dataset Selection Behavior

- The dashboard selects the most recently modified matching Parquet object for each dataset.
- Each dataset is read as one Parquet object.
- The current implementation does not combine multiple files from a partitioned Parquet dataset.
- Publish complete snapshots before the dashboard reads them to avoid incomplete or inconsistent results.

---

## 🔐 AWS IAM Permissions

Create a dedicated IAM identity for the dashboard. Do not use your AWS root account credentials.

The dashboard requires permission to list the relevant S3 objects and read the Gold Parquet files.

Example IAM policy for a shared `railway-gold/` prefix:

Replace `YOUR_BUCKET_NAME` with your actual bucket name.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListGoldObjects",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME",
      "Condition": {
        "StringLike": {
          "s3:prefix": [
            "railway-gold/",
            "railway-gold/*"
          ]
        }
      }
    },
    {
      "Sid": "ReadGoldObjects",
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/railway-gold/*"
    }
  ]
}
```

For separate prefixes, restrict the listing conditions and object resources to the train and station prefixes only.

The dashboard does not require S3 write or delete permissions. Keep the bucket private.

If the objects use SSE-KMS encryption, the IAM identity may also need appropriately scoped `kms:Decrypt` permission.

---

## 🚀 Deployment — Streamlit Community Cloud

Follow these steps to publish RailPulse online.

### Step 1: Push the Repository to GitHub

Ensure your dashboard files and `dashboard/requirements.txt` are committed to the repository.

Never commit AWS credentials or a populated secrets file.

### Step 2: Create a Streamlit App

1. Open [Streamlit Community Cloud](https://share.streamlit.io/).
2. Sign in and connect your GitHub account.
3. Create a new app.
4. Select the RailPulse repository.
5. Select the `main` branch.

### Step 3: Configure the Main File

Set the application entry point to:

```text
dashboard/app.py
```

### Step 4: Configure Streamlit Secrets

Open the app's settings and locate **Secrets** under the advanced settings.

Add your actual AWS configuration in TOML format:

```toml
AWS_ACCESS_KEY_ID = "YOUR_READ_ONLY_ACCESS_KEY_ID"
AWS_SECRET_ACCESS_KEY = "YOUR_READ_ONLY_SECRET_ACCESS_KEY"
AWS_REGION = "YOUR_BUCKET_REGION"
S3_BUCKET_NAME = "YOUR_BUCKET_NAME"

S3_GOLD_PREFIX = "railway-gold/"
```

Use the separate-prefix configuration if that is how your S3 data is organized.

If you use temporary AWS credentials, include the session token:

```toml
AWS_SESSION_TOKEN = "YOUR_SESSION_TOKEN"
```

### Step 5: Deploy and Verify

1. Deploy the application.
2. Wait for the deployment to finish.
3. Open the RailPulse dashboard.
4. Navigate to **Data Freshness**.
5. Verify that the train and station datasets load successfully.

If you update the code or Secrets, allow the app to redeploy or reboot it when necessary.

---

## 💻 Run Locally

You can also run RailPulse on your computer for development and testing.

### Prerequisites

- Python installed
- Access to the project repository
- An AWS IAM identity with read-only access to the required Gold datasets

### Step 1: Clone the Repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd RailPulse
```

Replace the repository URL with your actual GitHub URL.

### Step 2: Install Dependencies

Run the following commands from the repository root:

```bash
python -m pip install -r dashboard/requirements.txt
```

### Step 3: Configure Local Secrets

Create the following file in the repository root:

```text
.streamlit/secrets.toml
```

Add your AWS credentials, bucket, region, and Gold prefix using the configuration shown earlier.

Ensure `.streamlit/secrets.toml` is included in `.gitignore`.

### Step 4: Start the Dashboard

```bash
python -m streamlit run dashboard/app.py
```

Open the local URL displayed in your terminal, typically:

```text
http://localhost:8501
```

The dashboard will connect to S3 using the configured credentials.

---

## 🔄 Data Refresh and Caching

RailPulse caches data for **five minutes** to reduce repeated downloads of Parquet files from Amazon S3.

| Event | Expected behavior |
|---|---|
| The dashboard loads | Reads cached data if available |
| A new Gold snapshot is published | Existing cached data may remain visible temporarily |
| The five-minute cache expires | Fresh data can be loaded on a subsequent app rerun |
| The user clicks Refresh Data | The application clears the relevant cache and requests current S3 data |
| The browser remains idle | The dashboard does not continuously poll S3 in the background |

### How Automatic Updates Work

```text
Airflow DAG Executes
        |
        v
PySpark Processes Data
        |
        v
New Gold Snapshot Published to S3
        |
        v
Dashboard Requests Data Again
        |
        v
Updated Analytics Displayed
```

Publishing new data to S3 does not automatically trigger a Streamlit app rerun.

For a fresh view, use **Refresh Data** or allow the cache to expire and the application to rerun. If you need automatic background updates, additional scheduling or event-driven integration would be required.

---

## 📊 Supported Metrics and Customization

The dashboard adapts its charts and summary metrics to the available Parquet columns.

For better automatic detection, use clear and consistent names where practical.

| Dataset | Example column names |
|---|---|
| Train | `train_number`, `train_name` |
| Train | `avg_delay_min`, `distance_km` |
| Station | `station_code`, `station_name` |
| Analytics | `passenger_count`, `delay_count` |

These are examples, not mandatory schema requirements.

If your Gold datasets use different column names or directory structures, update the prefix configuration or the column-detection logic in `dashboard/app.py`.

---

## 🛡️ Security Best Practices

- Keep the Amazon S3 bucket private.
- Use a dedicated, read-only IAM identity.
- Store credentials in Streamlit Secrets or an appropriate local secrets manager.
- Never commit AWS keys, session tokens, or populated secrets files to GitHub.
- Never use AWS root credentials for the dashboard.
- Rotate exposed access keys immediately.
- Grant access only to the necessary Gold prefixes.
- Consider short-lived credentials or an AWS-hosted backend with an IAM role for production deployments.

**If an AWS access key has been exposed, revoke or rotate it immediately.**

---

## 🔮 Future Enhancements

Potential improvements for future versions include:

- Automated dashboard refresh after successful Gold-layer publication.
- Historical train and station performance comparisons.
- Delay trends by station, route, and train.
- Scheduled data quality reports.
- Advanced filtering and search.
- Additional railway performance KPIs.
- Improved error handling and observability.
- Role-based access and authentication where required.

These are potential enhancements and are not necessarily implemented in the current version.

---

## 🎯 Project Goals

RailPulse aims to make railway analytics more accessible by combining cloud-based data storage, scalable data processing, and interactive visualization.

The project demonstrates how an end-to-end data engineering pipeline can publish analytical datasets that power a practical business intelligence dashboard.

## 🤝 Contributing

Contributions, bug reports, and feature suggestions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Make your changes.
4. Test your changes locally.
5. Submit a pull request with a clear description.

### Contributors

- [Sudhanshugochar](https://github.com/Sudhanshugochar)

## 📄 License

Add your chosen open-source license to the repository before publishing a license statement. For example, you may use the MIT License if that matches your intended project terms.

---

<p align="center">
  <strong>🚆 RailPulse — Explore Data. Discover Insights. Improve Visibility.</strong>
</p>

<p align="center">
  Built with Python, Streamlit, Amazon S3, and a data engineering mindset.
</p>
