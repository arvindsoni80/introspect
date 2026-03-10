"""
Startup script for Google Cloud Run deployment.
Downloads database from Cloud Storage and loads secrets from Secret Manager.
"""
import os
import sys
from pathlib import Path


def download_database():
    """Download SQLite database from Cloud Storage."""
    # Only run in Cloud Run environment
    if not os.environ.get('K_SERVICE'):
        print("Not running in Cloud Run, skipping database download")
        return

    try:
        from google.cloud import storage
    except ImportError:
        print("Warning: google-cloud-storage not installed, skipping database download")
        return

    bucket_name = os.environ.get('GCS_BUCKET_NAME')
    if not bucket_name:
        print("Warning: GCS_BUCKET_NAME not set, skipping database download")
        return

    source_blob_name = os.environ.get('GCS_DB_FILE', 'introspect.db')
    destination_file_name = 'data/introspect.db'

    print(f"Downloading database from gs://{bucket_name}/{source_blob_name}...")

    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(source_blob_name)

        # Ensure data directory exists
        Path('data').mkdir(exist_ok=True)

        blob.download_to_filename(destination_file_name)
        print(f"✓ Database downloaded to {destination_file_name}")
    except Exception as e:
        print(f"Error downloading database: {e}")
        sys.exit(1)


def load_secrets():
    """Load secrets from Secret Manager and set as environment variables."""
    # Only run in Cloud Run environment
    if not os.environ.get('K_SERVICE'):
        print("Not running in Cloud Run, skipping secrets loading")
        return

    try:
        from google.cloud import secretmanager
    except ImportError:
        print("Warning: google-cloud-secret-manager not installed, skipping secrets loading")
        return

    project_id = os.environ.get('GCP_PROJECT')
    if not project_id:
        print("Warning: GCP_PROJECT not set, skipping secrets loading")
        return

    client = secretmanager.SecretManagerServiceClient()

    # Map environment variable names to secret names
    secrets = {
        'ANTHROPIC_API_KEY': os.environ.get('SECRET_ANTHROPIC_API_KEY', 'anthropic-api-key'),
        'GONG_ACCESS_KEY': os.environ.get('SECRET_GONG_ACCESS_KEY', 'gong-access-key'),
        'GONG_SECRET_KEY': os.environ.get('SECRET_GONG_ACCESS_KEY_SECRET', 'gong-access-key-secret'),
        'SLACK_BOT_TOKEN': os.environ.get('SECRET_SLACK_BOT_TOKEN', 'slack-bot-token'),
        'SLACK_APP_TOKEN': os.environ.get('SECRET_SLACK_APP_TOKEN', 'slack-app-token'),
    }

    for env_var, secret_name in secrets.items():
        # Skip if already set (for local testing)
        if os.environ.get(env_var):
            print(f"✓ {env_var} already set, skipping")
            continue

        try:
            name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode('UTF-8')
            os.environ[env_var] = secret_value
            print(f"✓ Loaded secret: {env_var}")
        except Exception as e:
            print(f"Warning: Could not load secret {secret_name}: {e}")


if __name__ == '__main__':
    print("=" * 60)
    print("Starting Cloud Run initialization...")
    print("=" * 60)

    # Check if running in Cloud Run
    if os.environ.get('K_SERVICE'):
        print(f"Running in Cloud Run service: {os.environ.get('K_SERVICE')}")
        print(f"Region: {os.environ.get('FUNCTION_REGION', 'unknown')}")
    else:
        print("Running locally")

    print("\n" + "=" * 60)
    print("Step 1: Loading secrets from Secret Manager")
    print("=" * 60)
    load_secrets()

    print("\n" + "=" * 60)
    print("Step 2: Downloading database from Cloud Storage")
    print("=" * 60)
    download_database()

    print("\n" + "=" * 60)
    print("Initialization complete!")
    print("=" * 60)
