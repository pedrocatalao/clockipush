import datetime
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2 import service_account

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

class CalendarClient:
    def __init__(self, service_account_file=None):
        self.creds = None
        self.service = None
        self.service_account_file = service_account_file

    def authenticate(self):
        """Authenticates with Google Calendar API."""
        if self.service_account_file and os.path.exists(self.service_account_file):
            self.creds = service_account.Credentials.from_service_account_file(
                self.service_account_file, scopes=SCOPES)
        else:
            # Fallback to user credentials (token.json) or interactive flow
            if os.path.exists('token.json'):
                self.creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    # Note: This requires a browser, might not work in headless env without setup
                    # For headless/CI, service account is preferred.
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'credentials.json', SCOPES)
                    self.creds = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                with open('token.json', 'w') as token:
                    token.write(self.creds.to_json())

        self.service = build('calendar', 'v3', credentials=self.creds)

    def get_events(self, time_min, time_max, calendar_id='primary'):
        """Fetches events within the specified time range."""
        if not self.service:
            self.authenticate()
            
        events_result = self.service.events().list(
            calendarId=calendar_id, timeMin=time_min, timeMax=time_max,
            singleEvents=True, orderBy='startTime').execute()
        events = events_result.get('items', [])
        return events
