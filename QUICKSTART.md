# Quick Start Deployment Guide

**Target:** Deploy to Google Cloud Run with `@coderabbit.ai` domain restriction

## Prerequisites

- ✅ `gcloud` CLI installed
- ✅ Google Cloud account with billing enabled
- ✅ `introspect.db` database file ready

---

## Deployment Steps

### 1. Set Variables

```bash
export PROJECT_ID="introspect-prod"
export REGION="us-central1"
export BUCKET_NAME="introspect-data-prod"
export DOMAIN="coderabbit.ai"
```

### 2. Create Project & Enable APIs

```bash
# Create project
gcloud projects create ${PROJECT_ID} --name="Introspect"
gcloud config set project ${PROJECT_ID}

# Link billing account (do this in console or use billing account ID)
# Visit: https://console.cloud.google.com/billing

# Enable APIs
gcloud services enable run.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

### 3. Create Cloud Storage Bucket & Upload Database

```bash
# Create bucket
gsutil mb -l ${REGION} gs://${BUCKET_NAME}

# Upload database
gsutil cp introspect.db gs://${BUCKET_NAME}/introspect.db

# Verify upload
gsutil ls gs://${BUCKET_NAME}
```

### 4. Store Secrets in Secret Manager

```bash
# Anthropic API Key
echo -n "your-anthropic-api-key-here" | gcloud secrets create anthropic-api-key --data-file=-

# Gong credentials
echo -n "your-gong-access-key" | gcloud secrets create gong-access-key --data-file=-
echo -n "your-gong-access-key-secret" | gcloud secrets create gong-access-key-secret --data-file=-

# Slack tokens (if using Slack integration)
echo -n "your-slack-bot-token" | gcloud secrets create slack-bot-token --data-file=-
echo -n "your-slack-app-token" | gcloud secrets create slack-app-token --data-file=-

# Verify secrets
gcloud secrets list
```

### 5. Create Service Account

```bash
# Create service account
gcloud iam service-accounts create introspect-sa \
  --display-name="Introspect Service Account"

# Grant Cloud Storage access
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:introspect-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

# Grant Secret Manager access
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:introspect-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 6. Build Docker Image (Cloud Build - No Docker Required)

```bash
# Build in cloud
gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/introspect

# This takes 3-5 minutes
```

### 7. Deploy to Cloud Run with Authentication

```bash
# Deploy with auth required
gcloud run deploy introspect \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/introspect \
  --platform managed \
  --region ${REGION} \
  --no-allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --set-env-vars GCS_BUCKET_NAME=${BUCKET_NAME},GCP_PROJECT=${PROJECT_ID} \
  --service-account introspect-sa@${PROJECT_ID}.iam.gserviceaccount.com
```

### 8. Configure OAuth Consent Screen (One-Time)

1. Visit: https://console.cloud.google.com/apis/credentials/consent
2. Select **Internal** (if Google Workspace) or **External**
3. Fill in:
   - **App name:** Introspect
   - **User support email:** your-email@coderabbit.ai
   - **Developer contact:** your-email@coderabbit.ai
4. Click **Save and Continue** through all steps

### 9. Grant Access to Your Domain

```bash
# Allow all @coderabbit.ai users
gcloud run services add-iam-policy-binding introspect \
  --region=${REGION} \
  --member="domain:${DOMAIN}" \
  --role="roles/run.invoker"

# Verify access
gcloud run services get-iam-policy introspect --region=${REGION}
```

### 10. Get Your App URL

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe introspect --region=${REGION} --format='value(status.url)')
echo "🚀 Your app is live at: $SERVICE_URL"

# Open in browser
open $SERVICE_URL  # Mac
# or visit the URL manually
```

---

## Testing Access

1. Visit your app URL
2. You'll see Google sign-in page
3. Sign in with your `@coderabbit.ai` account
4. You should now see the Introspect dashboard

**Note:** Users with other email domains will be denied access.

---

## Updating the Database

When you need to update the database with new data:

```bash
# 1. Upload new database
gsutil cp introspect.db gs://${BUCKET_NAME}/introspect.db

# 2. Restart Cloud Run to download the latest version
gcloud run services update introspect --region ${REGION}
```

The restart takes ~30 seconds and downloads the fresh database.

---

## Managing Access

### Add Individual User

```bash
gcloud run services add-iam-policy-binding introspect \
  --region=${REGION} \
  --member="user:specific-user@coderabbit.ai" \
  --role="roles/run.invoker"
```

### Add a Google Group

```bash
gcloud run services add-iam-policy-binding introspect \
  --region=${REGION} \
  --member="group:sales-team@coderabbit.ai" \
  --role="roles/run.invoker"
```

### Remove Access

```bash
gcloud run services remove-iam-policy-binding introspect \
  --region=${REGION} \
  --member="user:former-employee@coderabbit.ai" \
  --role="roles/run.invoker"
```

### List Current Access

```bash
gcloud run services get-iam-policy introspect --region=${REGION}
```

---

## Monitoring

### View Logs

```bash
# Recent logs
gcloud run services logs read introspect --region ${REGION} --limit 50

# Follow logs in real-time
gcloud run services logs tail introspect --region ${REGION}
```

### View Metrics

Visit: https://console.cloud.google.com/run and select your service

---

## Costs

**Expected Monthly Cost:** $10-35

- Cloud Run: $10-30 (after free tier)
- Cloud Storage: $0-5
- Secret Manager: $0 (free tier)
- IAP: $0 (free)
- Cloud Build: $0 (free tier: 120 build-minutes/day)

---

## Troubleshooting

### Can't Access App (403 Error)

```bash
# Check if you're in the allowed list
gcloud run services get-iam-policy introspect --region=${REGION}

# Add yourself if missing
gcloud run services add-iam-policy-binding introspect \
  --region=${REGION} \
  --member="user:your-email@coderabbit.ai" \
  --role="roles/run.invoker"
```

### Container Not Starting

```bash
# Check logs for errors
gcloud run services logs read introspect --region ${REGION} --limit 100

# Common issues:
# - Database not found: Check bucket name in deploy command
# - Secrets not loading: Verify service account has Secret Manager access
```

### Need More Memory

```bash
# Increase to 4GB
gcloud run services update introspect --memory 4Gi --region ${REGION}
```

---

## Redeployment (After Code Changes)

```bash
# 1. Build new image
gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/introspect

# 2. Deploy (uses same settings as before)
gcloud run deploy introspect \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/introspect \
  --region ${REGION}
```

---

## Summary

✅ **Secure:** Only `@coderabbit.ai` users can access
✅ **Serverless:** Automatically scales, no server management
✅ **Cost-effective:** Pay only for actual usage
✅ **Easy updates:** Upload new DB → restart service
✅ **Production-ready:** HTTPS, monitoring, logging included

**Next Steps:**
- Share the app URL with your team
- Set up automated database updates (optional)
- Configure custom domain (optional)
