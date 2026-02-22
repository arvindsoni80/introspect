# Deployment Guide: Introspect to Google Cloud

This guide covers deploying the Introspect Streamlit application to Google Cloud for internal team access.

## Overview

**Goal**: Deploy as internal SaaS for sales team with Google Workspace authentication

**Architecture**:
- **Cloud Run**: Serverless container platform for Streamlit app
- **Identity-Aware Proxy (IAP)**: Google Workspace authentication (no user list maintenance)
- **Database**: SQLite or Cloud SQL (two options below)
- **Secret Manager**: Store API keys securely

**Cost Estimate**: $15-30/month for 10 users

---

## Database Options

### Option 1: SQLite with Cloud Storage (Easiest)

**Best for**: Read-heavy workloads, < 20 concurrent users, minimal migration effort

**Pros**:
- ✅ Zero code changes
- ✅ No schema migration
- ✅ Lower cost ($0.026/GB/month for storage)
- ✅ Deploy in < 1 hour

**Cons**:
- ❌ Not ideal for concurrent writes
- ❌ File needs download at startup (adds ~2-5 seconds)

**Migration Steps**:

```bash
# 1. Create Cloud Storage bucket
gsutil mb -l us-central1 gs://introspect-db-bucket

# 2. Upload your database
gsutil cp introspect.db gs://introspect-db-bucket/introspect.db

# 3. Update your app to download DB at startup
# See code snippet below
```

**Code changes** (add to `streamlit_app/Home.py` or wherever DB is initialized):

```python
import os
from google.cloud import storage

def get_database_path():
    """Download SQLite DB from Cloud Storage if in production."""
    if os.getenv('ENV') == 'production':
        # Running on Cloud Run - download from storage
        client = storage.Client()
        bucket = client.bucket('introspect-db-bucket')
        blob = bucket.blob('introspect.db')

        db_path = '/tmp/introspect.db'
        blob.download_to_filename(db_path)
        print(f"✓ Downloaded database from Cloud Storage")
        return db_path
    else:
        # Local development
        return os.getenv('SQLITE_DB_PATH', 'introspect.db')

# Use this in your config
DATABASE_PATH = get_database_path()
```

**Important**: This makes the database **read-only** in production. To update data:
1. Run `process_calls.py` locally
2. Upload updated DB: `gsutil cp introspect.db gs://introspect-db-bucket/introspect.db`
3. Restart Cloud Run service (or wait for next cold start)

---

### Option 2: Cloud SQL PostgreSQL (Production-ready)

**Best for**: Multiple concurrent users, frequent updates, production workloads

**Pros**:
- ✅ Handles concurrent writes properly
- ✅ Managed backups and HA
- ✅ Better performance at scale
- ✅ Industry standard

**Cons**:
- ❌ Requires migration script
- ❌ Higher cost (~$10-20/month for db-f1-micro)
- ❌ Small code changes needed

**Migration Steps**:

```bash
# 1. Create Cloud SQL instance
gcloud sql instances create introspect-db \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region=us-central1

# 2. Create database
gcloud sql databases create introspect --instance=introspect-db

# 3. Set password
gcloud sql users set-password postgres \
    --instance=introspect-db \
    --password=YOUR_SECURE_PASSWORD

# 4. Start Cloud SQL Proxy (for migration)
cloud-sql-proxy --port 5432 PROJECT_ID:us-central1:introspect-db

# 5. Run migration script (in another terminal)
pip install psycopg2-binary
python migrate_sqlite_to_postgres.py \
    --sqlite-path introspect.db \
    --postgres-url "postgresql://postgres:YOUR_PASSWORD@localhost:5432/introspect"
```

**Code changes**:

```python
# Update src/core/config.py to support PostgreSQL
import os

class Config:
    # ... existing fields ...

    # Database connection (auto-detects SQLite vs PostgreSQL)
    DATABASE_URL = os.getenv(
        'DATABASE_URL',
        f'sqlite:///{SQLITE_DB_PATH}'  # fallback to SQLite
    )
```

**Update database initialization** (wherever you use `init_database`):

```python
from src.data.database_postgres import init_database

# Old way (SQLite only):
# db = init_database(config.SQLITE_DB_PATH)

# New way (supports both):
db = init_database(config.DATABASE_URL)
```

For Cloud Run, set `DATABASE_URL` in environment:
```
postgresql://postgres:PASSWORD@/introspect?host=/cloudsql/PROJECT_ID:us-central1:introspect-db
```

---

## Deployment Steps (Cloud Run)

### Prerequisites

```bash
# Install Google Cloud SDK
# https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable APIs
gcloud services enable \
    run.googleapis.com \
    iap.googleapis.com \
    secretmanager.googleapis.com \
    cloudbuild.googleapis.com
```

### 1. Store Secrets

```bash
# Store Gong credentials
echo -n "YOUR_GONG_ACCESS_KEY" | gcloud secrets create gong-access-key --data-file=-
echo -n "YOUR_GONG_SECRET_KEY" | gcloud secrets create gong-secret-key --data-file=-

# Store Anthropic API key
echo -n "YOUR_ANTHROPIC_API_KEY" | gcloud secrets create anthropic-api-key --data-file=-

# (If using Cloud SQL) Store DB password
echo -n "YOUR_DB_PASSWORD" | gcloud secrets create db-password --data-file=-
```

### 2. Create Dockerfile

Create `Dockerfile` in your repo root:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment
ENV ENV=production
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run Streamlit
CMD streamlit run streamlit_app/Home.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true
```

### 3. Deploy to Cloud Run

**For SQLite + Cloud Storage:**

```bash
gcloud run deploy introspect \
    --source . \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --set-env-vars="ENV=production,GONG_API_URL=https://api.gong.io,INTERNAL_DOMAIN=yourcompany.com" \
    --set-secrets="GONG_ACCESS_KEY=gong-access-key:latest,GONG_SECRET_KEY=gong-secret-key:latest,ANTHROPIC_API_KEY=anthropic-api-key:latest" \
    --memory 1Gi \
    --cpu 1 \
    --max-instances 10
```

**For Cloud SQL:**

```bash
gcloud run deploy introspect \
    --source . \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --add-cloudsql-instances PROJECT_ID:us-central1:introspect-db \
    --set-env-vars="ENV=production,DATABASE_URL=postgresql://postgres@/introspect?host=/cloudsql/PROJECT_ID:us-central1:introspect-db,GONG_API_URL=https://api.gong.io,INTERNAL_DOMAIN=yourcompany.com" \
    --set-secrets="GONG_ACCESS_KEY=gong-access-key:latest,GONG_SECRET_KEY=gong-secret-key:latest,ANTHROPIC_API_KEY=anthropic-api-key:latest,DB_PASSWORD=db-password:latest" \
    --memory 1Gi \
    --cpu 1 \
    --max-instances 10
```

### 4. Enable Identity-Aware Proxy (IAP)

IAP restricts access to your Google Workspace domain - no user list maintenance needed!

```bash
# 1. Get your Cloud Run service URL
SERVICE_URL=$(gcloud run services describe introspect --region us-central1 --format 'value(status.url)')

# 2. Create backend service
gcloud compute backend-services create introspect-backend \
    --global

# 3. Configure OAuth consent screen
# Go to: https://console.cloud.google.com/apis/credentials/consent
# - User Type: Internal (for workspace users only)
# - App name: Introspect
# - Authorized domains: yourcompany.com

# 4. Create OAuth client
gcloud iap oauth-clients create introspect-oauth \
    --display_name="Introspect App"

# 5. Enable IAP
gcloud iap web enable \
    --resource-type=backend-services \
    --service=introspect-backend

# 6. Configure IAP policy (restrict to your domain)
gcloud iap web set-iam-policy introspect-backend policy.yaml
```

**policy.yaml**:
```yaml
bindings:
- members:
  - domain:yourcompany.com
  role: roles/iap.httpsResourceAccessor
```

Now only users with `@yourcompany.com` emails can access the app!

---

## Updating Data

### Option 1 (SQLite): Update and Re-upload

```bash
# 1. Run your data processing locally
python process_calls.py --days 7 --limit 100

# 2. Upload updated database
gsutil cp introspect.db gs://introspect-db-bucket/introspect.db

# 3. Restart Cloud Run (to pick up new DB)
gcloud run services update introspect --region us-central1
```

### Option 2 (Cloud SQL): Run Processing from Cloud Run

Deploy a separate Cloud Run job for data processing:

```bash
gcloud run jobs create process-calls \
    --source . \
    --region us-central1 \
    --add-cloudsql-instances PROJECT_ID:us-central1:introspect-db \
    --set-env-vars="DATABASE_URL=postgresql://..." \
    --set-secrets="..." \
    --execute-now

# Schedule with Cloud Scheduler (daily at 6am)
gcloud scheduler jobs create http process-calls-daily \
    --location us-central1 \
    --schedule="0 6 * * *" \
    --uri="https://...cloudrun.app/process" \
    --http-method POST
```

---

## Cost Breakdown

### SQLite + Cloud Storage
- **Cloud Run**: $0.24/million requests + $0.00002400/vCPU-second
  - Estimate: ~$5-10/month for 10 users
- **Cloud Storage**: $0.026/GB/month
  - Estimate: < $1/month (DB is small)
- **Secrets**: $0.06/secret/month × 3 = $0.18/month
- **Total**: ~$6-12/month

### Cloud SQL
- **Cloud Run**: Same as above (~$5-10/month)
- **Cloud SQL db-f1-micro**: $7.67/month (0.6 GB RAM, shared CPU)
- **Cloud SQL storage**: $0.17/GB/month
  - Estimate: ~$2/month for 10 GB
- **Secrets**: $0.18/month
- **Total**: ~$15-20/month

---

## Monitoring

```bash
# View logs
gcloud run services logs read introspect --region us-central1

# View metrics in console
# https://console.cloud.google.com/run
```

---

## Troubleshooting

**Issue**: "Permission denied" when accessing Cloud Storage

**Fix**: Grant Cloud Run service account storage access:
```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
    --role="roles/storage.objectViewer"
```

**Issue**: Slow cold starts with SQLite

**Fix**: Keep one instance warm:
```bash
gcloud run services update introspect \
    --region us-central1 \
    --min-instances 1
```
(Adds ~$10/month but eliminates cold starts)

---

## Recommendation

**For your use case (sales team, ~10 users)**:

1. **Start with Option 1 (SQLite + Cloud Storage)**
   - Fastest to deploy (< 1 hour)
   - Lowest cost ($6-12/month)
   - Zero code changes
   - Run `process_calls.py` locally once/week

2. **Migrate to Option 2 (Cloud SQL) later if**:
   - Team grows > 20 users
   - Need real-time data updates
   - Want automated daily processing

You can migrate from Option 1 → 2 anytime using the migration script!

---

## Next Steps

1. Choose database option (recommend starting with SQLite)
2. Create Dockerfile
3. Store secrets in Secret Manager
4. Deploy to Cloud Run
5. Enable IAP for Google Workspace auth
6. Share URL with team!

Any questions? Let me know which approach you'd like to start with!
