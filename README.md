# ClockiPush

**ClockiPush** is an automated tool that synchronizes your **Google Calendar** events and **GitHub Issues** to **Clockify** time entries. It uses **OpenAI** to intelligently match your calendar events to the correct Clockify projects and tasks.

## Features

-   **Calendar Sync**: Fetches events from Google Calendar and logs them as time entries.
-   **GitHub Sync**: Fetches "In Progress" (daily) and "Done" (on completion) issues from GitHub.
-   **AI Matching**: Uses GPT-4o (or similar) to categorize events into the correct Clockify Project and Task.
-   **Dynamic Time Distribution**: Automatically calculates the remaining time in an 8-hour workday (after calendar events) and distributes it equally among your active GitHub issues.
-   **Duplicate Prevention**: Smartly checks for existing entries to avoid double-booking.
-   **GitHub Actions Support**: Runs automatically on a schedule (e.g., Mon-Thu at 20:00 UTC).

## Prerequisites & Setup

You will need API keys and credentials from the following services:

### 1. Clockify
*   **API Key**: Go to [Profile Settings](https://app.clockify.me/user/settings) -> scroll to bottom -> Generate API Key.
*   **Workspace ID**: Go to [Settings](https://app.clockify.me/workspaces) -> Copy the ID from the URL or settings page.

### 2. OpenAI
*   **API Key**: Go to [OpenAI Platform](https://platform.openai.com/api-keys) and generate a new secret key.

### 3. Google Calendar
*   **Service Account**:
    1.  Go to [Google Cloud Console](https://console.cloud.google.com/).
    2.  Create a project and enable the **Google Calendar API**.
    3.  Create a **Service Account**, generate a JSON key, and download it (e.g., `service_account.json`).
    4.  **Important**: Open your Google Calendar, go to "Settings and sharing" for the calendar you want to sync, and **share** it with the `client_email` address found in your JSON file.
*   **Calendar ID**: Usually your email address (e.g., `user@example.com`).

### 4. GitHub
*   **Personal Access Token (PAT)**:
    1.  Go to [GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)](https://github.com/settings/tokens).
    2.  Generate a new token with `repo` and `read:org` scopes.

## Local Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/clockipush.git
    cd clockipush
    ```

2.  **Set up the environment**:
    Create a `.env` file (copy from `.env.example`) and fill in your credentials:
    ```bash
    cp .env.example .env
    ```
    *   `CLOCKIFY_API_KEY=...`
    *   `CLOCKIFY_WORKSPACE_ID=...`
    *   `OPENAI_API_KEY=...`
    *   `GOOGLE_SERVICE_ACCOUNT_FILE=path/to/your/service_account.json`
    *   `GOOGLE_CALENDAR_ID=your_email@domain.com`
    *   `CLOCKIFY_PROJECT_NAME=DevOps` (Optional: filter projects)
    *   `GITHUB_TOKEN=ghp_...`

3.  **Install dependencies**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

## Usage

### Manual Run
Use the helper script to run the sync:

```bash
# Sync yesterday's data (default)
./run.sh

# Sync specific number of past days
./run.sh --days 3

# Sync only today (since 00:00 UTC)
./run.sh --today

# Dry run (simulate without writing to Clockify)
./run.sh --dry-run --today
```

### GitHub Actions (Automated)
The repository includes a workflow (`.github/workflows/sync.yml`) to run the sync automatically.

**Required GitHub Secrets**:
Go to your repository **Settings > Secrets and variables > Actions** and add:

*   `CLOCKIFY_API_KEY`
*   `CLOCKIFY_WORKSPACE_ID`
*   `OPENAI_API_KEY`
*   `GOOGLE_CALENDAR_ID`
*   `CLOCKIFY_PROJECT_NAME`
*   `PERSONAL_GITHUB_TOKEN` (Your GitHub PAT)
*   `GOOGLE_SERVICE_ACCOUNT_JSON` (Paste the **entire content** of your JSON key file)

## How it Works

1.  **Calendar Events**: The script fetches events from your Google Calendar.
2.  **AI Analysis**: It sends the event summary to OpenAI to determine the best matching Project and Task in Clockify.
3.  **Time Calculation**: It sums up the duration of all calendar meetings.
4.  **GitHub Issues**: It fetches issues assigned to you that are "In Progress" or "Done" (updated today).
5.  **Distribution**: It calculates `Remaining Time = 8 hours - Meeting Time` and distributes this time equally among your eligible GitHub issues.
6.  **Sync**: It pushes the time entries to Clockify.
