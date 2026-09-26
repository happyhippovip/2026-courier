# Future OAuth & gcloud Steps for YouTube Integration

This document outlines the exact steps required to transition the YouTube integration from the current offline "dry-run" state to a fully authenticated state. **These steps must only be executed when the system is authorized to interact with real Google APIs and when the user can provide interactive consent.**

## Step 1: Install gcloud CLI
1. Download the Google Cloud CLI for macOS.
2. Run `./google-cloud-sdk/install.sh`.
3. Restart the shell and run `gcloud init`.

## Step 2: Create and Configure a GCP Project
1. Run `gcloud projects create <project-id> --name="Courier YouTube Publisher"`.
2. Run `gcloud config set project <project-id>`.
3. Enable the YouTube Data API v3:
   `gcloud services enable youtube.googleapis.com`

## Step 3: Configure the OAuth Consent Screen
1. Go to the [Google Cloud Console > API & Services > OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent).
2. Set User Type to **External** (if testing) or **Internal** (if part of an organization).
3. Add the required scope: `https://www.googleapis.com/auth/youtube.upload`.
4. Add any test users (like the main YouTube channel owner's email) if the app is in "Testing" mode.

## Step 4: Generate OAuth Client ID and Secret
1. Go to [Credentials](https://console.cloud.google.com/apis/credentials).
2. Click **Create Credentials > OAuth client ID**.
3. Select **Desktop App** (or Web App if redirecting to a local server for auth).
4. Download the resulting JSON file.
5. Save it locally as `.secrets/client_secret.json`. Do not commit this file.

## Step 5: Install Python Dependencies
1. Ensure the virtual environment is active.
2. Run `pip install google-api-python-client google-auth-oauthlib google-auth-httplib2`.

## Step 6: Initial Authentication (Interactive)
1. In a separate one-time human-operated script (never inside `YouTubeProvider`'s autonomous path, which must stay fail-closed and never start a browser flow), use `google_auth_oauthlib.flow.InstalledAppFlow` to read `client_secret.json`.
2. Run a script that calls `flow.run_local_server(port=0)`.
3. The developer will be prompted in their browser to log in and grant the `youtube.upload` scope.
4. Save the resulting credentials to `.secrets/token.json`.

## Step 7: Application Default Credentials (Optional)
If running inside GCP or using a service account (note: YouTube APIs heavily restrict service accounts, so OAuth user tokens are preferred), run:
`gcloud auth application-default login`

## Conclusion
Once `.secrets/token.json` is generated, the `YouTubeProvider` can read it, refresh it automatically, and pass `dry_run=False` to execute real API requests.
