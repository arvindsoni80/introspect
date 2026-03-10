# Google Cloud Deployment Guide

This guide walks you through deploying the Introspect application to Google Cloud Run with Cloud Storage and Secret Manager.

## Prerequisites

- Google Cloud account
- `gcloud` CLI installed locally
- Your SQLite database file (`introspect.db`)

**Note:** Docker is NOT required on your Mac! Google Cloud Build can build the image for you in the cloud.

## Step 1: Google Cloud Account Setup

1. **Create Google Cloud Account**
   - Go to https://cloud.google.com/
   - Click "Get started for free"
   - Sign up with your Google account
   - You'll get $300 in free credits for 90 days

2. **Create a New Project**
   ```bash
   # Install gcloud CLI if not already installed
   # Visit: https://cloud.google.com/sdk/docs/install

   # Login to Google Cloud
   gcloud auth login

   # Create a new project
   gcloud projects create introspect-prod --name="Introspect"

   # Set as default project
   gcloud config set project introspect-prod

   # Enable billing (required for Cloud Run)
   # Visit: https://console.cloud.google.com/billing
   # Link your project to a billing account
   ```

3. **Enable Required APIs**
   ```bash
   gcloud services enable run.googleapis.com
   gcloud services enable storage.googleapis.com
   gcloud services enable secretmanager.googleapis.com
   gcloud services enable artifactregistry.googleapis.com
   ```

## Step 2: Cloud Storage Setup

1. **Create Storage Bucket**
   ```bash
   # Choose a globally unique bucket name
   export BUCKET_NAME="introspect-data-prod"
   export REGION="us-central1"  # Choose your preferred region

   # Create bucket
   gsutil mb -l $REGION gs://$BUCKET_NAME
   ```

2. **Upload SQLite Database**
   ```bash
   # Upload your database file
   gsutil cp introspect.db gs://$BUCKET_NAME/introspect.db

   # Make it accessible to Cloud Run (we'll use IAM for security)
   # No need to make it public
   ```

## Step 3: Secret Manager Setup

1. **Store Anthropic API Key**
   ```bash
   echo -n "your-anthropic-api-key-here" | gcloud secrets create anthropic-api-key --data-file=-
   ```

2. **Store Gong Credentials**
   ```bash
   echo -n "your-gong-access-key" | gcloud secrets create gong-access-key --data-file=-
   echo -n "your-gong-access-key-secret" | gcloud secrets create gong-access-key-secret --data-file=-
   ```

3. **Store Slack Tokens**
   ```bash
   echo -n "your-slack-bot-token" | gcloud secrets create slack-bot-token --data-file=-
   echo -n "your-slack-app-token" | gcloud secrets create slack-app-token --data-file=-
   ```

## Step 4: Prepare Application for Deployment

1. **Create Dockerfile**

Create `Dockerfile` in your project root:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for database
RUN mkdir -p /app/data

# Expose port
ENV PORT=8080
EXPOSE 8080

# Run startup script then streamlit
CMD python startup.py && streamlit run streamlit_app/app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true
```

2. **Create Startup Script**

Create `startup.py` in your project root:

```python
"""
Startup script for Google Cloud Run deployment.
Downloads database from Cloud Storage and loads secrets.
"""
import os
import subprocess
from google.cloud import storage
from google.cloud import secretmanager

def download_database():
    """Download SQLite database from Cloud Storage."""
    bucket_name = os.environ.get('GCS_BUCKET_NAME', 'introspect-data-prod')
    source_blob_name = 'introspect.db'
    destination_file_name = 'data/introspect.db'

    print(f"Downloading database from gs://{bucket_name}/{source_blob_name}...")

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)
    blob.download_to_filename(destination_file_name)

    print(f"Database downloaded to {destination_file_name}")

def load_secrets():
    """Load secrets from Secret Manager and set as environment variables."""
    project_id = os.environ.get('GCP_PROJECT', 'introspect-prod')
    client = secretmanager.SecretManagerServiceClient()

    secrets = {
        'ANTHROPIC_API_KEY': 'anthropic-api-key',
        'GONG_ACCESS_KEY': 'gong-access-key',
        'GONG_ACCESS_KEY_SECRET': 'gong-access-key-secret',
        'SLACK_BOT_TOKEN': 'slack-bot-token',
        'SLACK_APP_TOKEN': 'slack-app-token',
    }

    for env_var, secret_name in secrets.items():
        try:
            name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode('UTF-8')
            os.environ[env_var] = secret_value
            print(f"Loaded secret: {secret_name}")
        except Exception as e:
            print(f"Warning: Could not load secret {secret_name}: {e}")

if __name__ == '__main__':
    print("Starting Cloud Run initialization...")
    download_database()
    load_secrets()
    print("Initialization complete!")
```

3. **Update requirements.txt**

Add Google Cloud dependencies to `requirements.txt`:

```txt
google-cloud-storage==2.14.0
google-cloud-secret-manager==2.18.0
```

4. **Update Database Path in Code**

Ensure your code references the database at `data/introspect.db`. Update `src/sqlite_repository.py` or wherever the database path is configured:

```python
# Instead of hardcoded path
db_path = os.environ.get('DATABASE_PATH', 'data/introspect.db')
```

## Step 5: Build and Deploy

### Option A: Cloud Build (Recommended - No Docker Required)

**Use this option if you don't have Docker installed on your Mac.** Google Cloud Build will build the image in the cloud.

1. **Build Docker Image in Cloud**
   ```bash
   # Set your region
   export REGION="us-central1"
   export PROJECT_ID="introspect-prod"

   # Build and push image using Cloud Build (no local Docker needed!)
   gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/introspect
   ```

   This command:
   - Uploads your source code to Google Cloud
   - Builds the Docker image using Cloud Build
   - Stores the image in Artifact Registry
   - **No local Docker installation required**

### Option B: Local Build (Requires Docker Desktop)

**Use this option only if you prefer to build locally and have Docker Desktop installed.**

1. **Build Docker Image Locally**
   ```bash
   # Set your region
   export REGION="us-central1"
   export PROJECT_ID="introspect-prod"

   # Configure Docker for Google Cloud
   gcloud auth configure-docker ${REGION}-docker.pkg.dev

   # Build locally
   docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/introspect .

   # Push to Artifact Registry
   docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/introspect
   ```

---

### Deploy to Cloud Run (Both Options)

**After building with either Option A or B above, deploy to Cloud Run:**

```bash
# Deploy with authentication required (recommended for production)
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

**Note:** Using `--no-allow-unauthenticated` means you'll configure access control in Step 6.

<details>
<summary>📝 Optional: Deploy without authentication (for testing only)</summary>

If you want to test without authentication first:

```bash
gcloud run deploy introspect \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/introspect \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --set-env-vars GCS_BUCKET_NAME=${BUCKET_NAME},GCP_PROJECT=${PROJECT_ID} \
  --service-account introspect-sa@${PROJECT_ID}.iam.gserviceaccount.com
```

You can add authentication later following Step 6.
</details>

### Create Service Account (Run Once)
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

## Step 6: Access Control (Security)

The deployment commands above default to `--no-allow-unauthenticated` (authentication required), which is the recommended security posture for production. If you used `--allow-unauthenticated` for initial testing, follow the steps below to add access control.

### Option A: Identity-Aware Proxy (IAP) - Recommended ✅

**Best for:** Restricting to specific email addresses or entire domains (e.g., `@yourcompany.com`)

#### 6.1. Deploy with Authentication Required

```bash
# Re-deploy with authentication required
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

**Note:** The key change is `--no-allow-unauthenticated` instead of `--allow-unauthenticated`.

#### 6.2. Configure OAuth Consent Screen (One-Time Setup)

1. Go to [OAuth Consent Screen](https://console.cloud.google.com/apis/credentials/consent)
2. Choose **Internal** (if using Google Workspace) or **External**
3. Fill in:
   - **App name:** Introspect
   - **User support email:** your-email@yourcompany.com
   - **Developer contact:** your-email@yourcompany.com
4. Click **Save and Continue**
5. Skip scopes → Click **Save and Continue**
6. Click **Back to Dashboard**

#### 6.3. Grant Access to Users

**Option 1: Grant access to specific users**
```bash
# Add individual users
gcloud run services add-iam-policy-binding introspect \
  --region=${REGION} \
  --member='user:john@yourcompany.com' \
  --role='roles/run.invoker'

gcloud run services add-iam-policy-binding introspect \
  --region=${REGION} \
  --member='user:jane@yourcompany.com' \
  --role='roles/run.invoker'
```

**Option 2: Grant access to entire domain (Requires Google Workspace)**
```bash
# Allow all users from your company domain
gcloud run services add-iam-policy-binding introspect \
  --region=${REGION} \
  --member='domain:yourcompany.com' \
  --role='roles/run.invoker'
```

**Option 3: Grant access to a Google Group**
```bash
# Create a group in Google Workspace (e.g., sales-team@yourcompany.com)
# Then grant access to the group
gcloud run services add-iam-policy-binding introspect \
  --region=${REGION} \
  --member='group:sales-team@yourcompany.com' \
  --role='roles/run.invoker'
```

**Option 4: Using Google Cloud Console (GUI)**
1. Go to [Cloud Run Console](https://console.cloud.google.com/run)
2. Click your `introspect` service
3. Click **Permissions** tab
4. Click **Grant Access**
5. In "New principals", enter:
   - Single user: `user:john@yourcompany.com`
   - Entire domain: `domain:yourcompany.com`
   - Group: `group:sales-team@yourcompany.com`
6. Select role: **Cloud Run Invoker**
7. Click **Save**

#### 6.4. Test Access

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe introspect --region=${REGION} --format='value(status.url)')
echo "Service URL: $SERVICE_URL"

# Try to access (will require authentication)
open $SERVICE_URL  # On Mac
```

Users will see a Google sign-in page. Only users you've granted access to can proceed.

#### 6.5. Manage Access Over Time

**List current access:**
```bash
gcloud run services get-iam-policy introspect --region=${REGION}
```

**Remove access:**
```bash
gcloud run services remove-iam-policy-binding introspect \
  --region=${REGION} \
  --member='user:former-employee@yourcompany.com' \
  --role='roles/run.invoker'
```

### Option B: IP Allowlist with Cloud Armor

**Best for:** Restricting to specific office IP addresses or VPN ranges

**Note:** This requires setting up a Load Balancer, which is more complex and adds ~$18/month cost.

```bash
# Create security policy
gcloud compute security-policies create introspect-policy \
  --description "Restrict to office IPs"

# Add your office IP range
gcloud compute security-policies rules create 1000 \
  --security-policy introspect-policy \
  --expression "inIpRange(origin.ip, '203.0.113.0/24')" \
  --action allow \
  --description "Allow office network"

# Deny all other traffic
gcloud compute security-policies rules create 2147483647 \
  --security-policy introspect-policy \
  --action deny-403 \
  --description "Deny all other traffic"
```

Then set up a Load Balancer with Cloud Run backend and attach the security policy. See [detailed guide](https://cloud.google.com/armor/docs/integrating-cloud-armor).

### Option C: Application-Level Authentication

**Best for:** Custom authentication requirements or when not using Google Workspace

Add authentication directly in your Streamlit app.

**Step 1: Install bcrypt**
```bash
# Add to requirements.txt
pip install bcrypt
```

**Step 2: Generate password hashes**
```python
# Run this once to generate hashed passwords
import bcrypt

password = "your_password_here"
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
print(hashed.decode('utf-8'))  # Store this in USERS dict
```

**Step 3: Create `streamlit_app/auth.py`:**

```python
"""Secure authentication for Streamlit app."""
import streamlit as st
import bcrypt

# Store bcrypt hashed passwords (in production, use a database or Secret Manager)
# Generate hashes using: bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
USERS = {
    "admin@yourcompany.com": "$2b$12$...",  # Replace with actual bcrypt hash
    "user@yourcompany.com": "$2b$12$...",   # Replace with actual bcrypt hash
}

ALLOWED_DOMAIN = "yourcompany.com"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its bcrypt hash.

    Args:
        plain_password: Plain text password from user input
        hashed_password: Bcrypt hash from storage

    Returns:
        True if password matches, False otherwise
    """
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

def check_authentication():
    """Check if user is authenticated."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user_email = None

    if not st.session_state.authenticated:
        st.title("🔐 Introspect Login")

        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")

            if submitted:
                # Check domain
                if not email.endswith(f"@{ALLOWED_DOMAIN}"):
                    st.error(f"Access restricted to {ALLOWED_DOMAIN} domain")
                    st.stop()

                # Check credentials using secure bcrypt verification
                if email in USERS and verify_password(password, USERS[email]):
                    st.session_state.authenticated = True
                    st.session_state.user_email = email
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid credentials")

        st.stop()

def logout():
    """Logout current user."""
    st.session_state.authenticated = False
    st.session_state.user_email = None
    st.rerun()
```

Then add to `streamlit_app/app.py` at the top:

```python
from auth import check_authentication, logout

# Add authentication check at the very top
check_authentication()

# Add logout button in sidebar
with st.sidebar:
    if st.button("Logout"):
        logout()
```

### Comparison of Access Control Options

| Feature | IAP (Option A) | Cloud Armor (Option B) | App Auth (Option C) |
|---------|---------------|----------------------|-------------------|
| **Ease of Setup** | ⭐⭐⭐⭐⭐ Easy | ⭐⭐ Complex | ⭐⭐⭐ Medium |
| **Cost** | Free | ~$18-20/month | Free |
| **Domain Restriction** | ✅ Yes | ❌ No (IP only) | ✅ Yes |
| **Google Workspace Integration** | ✅ Yes | ❌ No | ❌ No |
| **Custom Auth Logic** | ❌ Limited | ❌ No | ✅ Yes |
| **Maintenance** | Low | Medium | High |
| **User Experience** | Excellent | Transparent | Custom |

**Recommendation:** Use **IAP (Option A)** for domain-based access control. It's free, secure, and easy to manage.

## Step 7: Update Database

When you need to update the database:

```bash
# Upload new version
gsutil cp introspect.db gs://$BUCKET_NAME/introspect.db

# Restart Cloud Run service to download latest
gcloud run services update introspect --region $REGION
```

## Step 8: View and Monitor

1. **Get Service URL**
   ```bash
   gcloud run services describe introspect --region $REGION --format='value(status.url)'
   ```

2. **View Logs**
   ```bash
   gcloud run services logs read introspect --region $REGION --limit 50
   ```

3. **Monitor in Console**
   - Visit: https://console.cloud.google.com/run
   - Select your service to see metrics, logs, and revisions

## Additional Security Considerations

1. **Database Security**
   - Database is not publicly accessible from the internet
   - Only accessible via Cloud Run service account

   **Optional: Database Encryption at Rest**

   For highly sensitive data, you can encrypt the database before uploading. This requires modifying `startup.py` to decrypt on startup.

   **If using encryption:**
   ```bash
   # Step 1: Encrypt database locally (you'll be prompted for password)
   openssl enc -aes-256-cbc -salt -in introspect.db -out introspect.db.enc

   # Step 2: Upload encrypted file to Cloud Storage
   gsutil cp introspect.db.enc gs://${BUCKET_NAME}/introspect.db.enc

   # Step 3: Store encryption password in Secret Manager
   echo -n "your-encryption-password" | gcloud secrets create db-encryption-password --data-file=-
   ```

   **Then modify `startup.py`** to download the `.enc` file and decrypt it:
   ```python
   # In download_database() function, change:
   source_blob_name = 'introspect.db.enc'  # Download .enc file
   encrypted_path = 'introspect.db.enc'
   destination_path = 'data/introspect.db'

   # Download encrypted file
   blob.download_to_filename(encrypted_path)

   # Decrypt using password from Secret Manager
   import subprocess
   db_password = os.environ.get('DB_ENCRYPTION_PASSWORD')  # Loaded from Secret Manager
   subprocess.run([
       'openssl', 'enc', '-d', '-aes-256-cbc',
       '-in', encrypted_path,
       '-out', destination_path,
       '-pass', f'pass:{db_password}'
   ], check=True)

   # Cleanup
   os.remove(encrypted_path)
   ```

   **Note:** Cloud Storage already encrypts data at rest by default. Database-level encryption is only needed for specific compliance requirements.

2. **Secrets Rotation**
   - Regularly rotate API keys and tokens (recommended: every 90 days)
   - Update secrets in Secret Manager:
     ```bash
     echo -n "new-key-value" | gcloud secrets versions add secret-name --data-file=-
     ```
   - After updating, restart Cloud Run to load new secrets:
     ```bash
     gcloud run services update introspect --region $REGION
     ```

3. **Audit Logging**
   - Enable Cloud Audit Logs to track access:
     ```bash
     gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=introspect" --limit 50
     ```

4. **HTTPS Only**
   - Cloud Run automatically enforces HTTPS
   - Custom domains automatically get SSL certificates

## Cost Estimates

**Cloud Run:**
- Always-free tier: 180,000 vCPU-seconds, 360,000 GiB-seconds per month
- After free tier: ~$0.04 per vCPU-second, ~$0.005 per GiB-second
- Expected cost: $10-30/month depending on usage

**Cloud Storage:**
- First 5GB free
- $0.02 per GB per month after
- Expected cost: $0-5/month

**Secret Manager:**
- First 6 active secrets free
- $0.06 per secret per month after
- Expected cost: $0/month

**Identity-Aware Proxy (IAP):**
- Free for Cloud Run ✅
- Expected cost: $0/month

**Cloud Armor (Optional - only if using IP restrictions):**
- $1 per security policy
- $0.75 per 1M requests
- Expected cost: $18-25/month (if used)

**Total Estimated Cost:**
- **With IAP (recommended): $10-35/month**
- **With Cloud Armor: $28-60/month**

## Troubleshooting

1. **Container Fails to Start**
   - Check logs: `gcloud run services logs read introspect --region $REGION`
   - Verify all secrets are created
   - Ensure service account has proper permissions

2. **Database Download Fails**
   - Verify bucket name and file exist: `gsutil ls gs://$BUCKET_NAME`
   - Check service account has Storage Object Viewer role

3. **Secrets Not Loading**
   - Verify secrets exist: `gcloud secrets list`
   - Check service account has Secret Manager Secret Accessor role

4. **Out of Memory**
   - Increase memory: `gcloud run services update introspect --memory 4Gi --region $REGION`

5. **Authentication Issues (403 Forbidden)**
   - Verify you've granted yourself access:
     ```bash
     gcloud run services add-iam-policy-binding introspect \
       --region=${REGION} \
       --member='user:your-email@yourcompany.com' \
       --role='roles/run.invoker'
     ```
   - Check current IAM policy:
     ```bash
     gcloud run services get-iam-policy introspect --region=${REGION}
     ```
   - Make sure you're signed in with the correct Google account
   - Clear browser cookies/cache and try again

6. **Users Can't Access (Domain Restriction)**
   - Verify domain is correctly added:
     ```bash
     gcloud run services get-iam-policy introspect --region=${REGION}
     ```
   - Ensure users are signing in with their company Google Workspace accounts
   - Check OAuth consent screen is properly configured

## Local Testing with Google Cloud Setup

Test the Cloud Run environment locally:

```bash
# Set environment variables locally
export GCS_BUCKET_NAME="introspect-data-prod"
export GCP_PROJECT="introspect-prod"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"

# Run startup script
python startup.py

# Run streamlit
streamlit run streamlit_app/app.py
```

## Automated Deployments

For CI/CD, create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3

    - id: auth
      uses: google-github-actions/auth@v1
      with:
        credentials_json: ${{ secrets.GCP_CREDENTIALS }}

    - name: Deploy to Cloud Run
      env:
        PROJECT_ID: introspect-prod
        REGION: us-central1
      run: |
        gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/introspect
        gcloud run deploy introspect --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/introspect --region ${REGION}
```

## Next Steps

1. Set up custom domain (optional)
2. Configure Cloud CDN for static assets (optional)
3. Set up Cloud Monitoring alerts
4. Configure backup strategy for database
5. Implement database write-back to Cloud Storage if needed
