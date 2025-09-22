import os
import json
import base64
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarService:
    def __init__(self, credentials_file: str = 'credentials.json', token_file: str = 'token.pickle'):
        """
        Initialize Google Calendar service.
        
        Args:
            credentials_file: Path to Google API credentials JSON file
            token_file: Path to store/load OAuth token
        """
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Calendar API."""
        creds = None
        
        # Try to load token from environment variable first, then fallback to file
        token_b64 = os.getenv('GOOGLE_TOKEN_B64')
        if token_b64:
            try:
                token_data = base64.b64decode(token_b64)
                creds = pickle.loads(token_data)
            except Exception as e:
                print(f"Warning: Could not load token from environment variable: {e}")
                creds = None
        elif os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)
        
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # Try to get credentials from environment variable first
                credentials_b64 = os.getenv('GOOGLE_CREDENTIALS_B64')
                if credentials_b64:
                    try:
                        credentials_data = base64.b64decode(credentials_b64)
                        credentials_json = json.loads(credentials_data.decode('utf-8'))
                        
                        # Create a temporary file for the credentials
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                            json.dump(credentials_json, temp_file)
                            temp_credentials_file = temp_file.name
                        
                        flow = InstalledAppFlow.from_client_secrets_file(
                            temp_credentials_file, SCOPES)
                        
                        # Clean up the temporary file
                        os.unlink(temp_credentials_file)
                        
                    except Exception as e:
                        raise RuntimeError(f"Could not load credentials from environment variable: {e}")
                elif os.path.exists(self.credentials_file):
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES)
                else:
                    raise FileNotFoundError(
                        f"Credentials not found in environment variable 'GOOGLE_CREDENTIALS_B64' "
                        f"or file '{self.credentials_file}'. Please set the environment variable "
                        "or download the credentials file from Google Cloud Console."
                    )
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            # Save to environment variable (base64 encoded) and also to file as backup
            try:
                token_data = pickle.dumps(creds)
                token_b64 = base64.b64encode(token_data).decode('utf-8')
                # Note: In production, you'd want to update the .env file or use a proper config management system
                # For now, we'll just save to file as backup
                print(f"Token updated. To persist in .env, add: GOOGLE_TOKEN_B64={token_b64}")
            except Exception as e:
                print(f"Warning: Could not encode token for environment variable: {e}")
            
            # Also save to file as backup
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('calendar', 'v3', credentials=creds)
    
    def create_event(self, title: str, description: str = None, 
                    start_time: datetime = None, end_time: datetime = None,
                    timezone: str = 'UTC') -> Optional[str]:
        """
        Create a Google Calendar event.
        
        Args:
            title: Event title
            description: Event description
            start_time: Start datetime
            end_time: End datetime
            timezone: Timezone string
            
        Returns:
            Google Calendar event ID if successful, None otherwise
        """
        try:
            if not start_time:
                start_time = datetime.now(timezone.utc)
            if not end_time:
                end_time = start_time + timedelta(hours=1)
            
            event = {
                'summary': title,
                'description': description or '',
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': timezone,
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': timezone,
                },
            }
            
            event = self.service.events().insert(
                calendarId='primary', body=event
            ).execute()
            
            return event.get('id')
        
        except HttpError as error:
            print(f'An error occurred: {error}')
            return None
    
    def update_event(self, event_id: str, title: str = None, 
                    description: str = None, start_time: datetime = None,
                    end_time: datetime = None, timezone: str = 'UTC') -> bool:
        """
        Update a Google Calendar event.
        
        Args:
            event_id: Google Calendar event ID
            title: New event title
            description: New event description
            start_time: New start datetime
            end_time: New end datetime
            timezone: Timezone string
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get existing event
            event = self.service.events().get(
                calendarId='primary', eventId=event_id
            ).execute()
            
            # Update fields
            if title:
                event['summary'] = title
            if description is not None:
                event['description'] = description
            if start_time:
                event['start']['dateTime'] = start_time.isoformat()
            if end_time:
                event['end']['dateTime'] = end_time.isoformat()
            
            self.service.events().update(
                calendarId='primary', eventId=event_id, body=event
            ).execute()
            
            return True
        
        except HttpError as error:
            print(f'An error occurred: {error}')
            return False
    
    def delete_event(self, event_id: str) -> bool:
        """
        Delete a Google Calendar event.
        
        Args:
            event_id: Google Calendar event ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.service.events().delete(
                calendarId='primary', eventId=event_id
            ).execute()
            return True
        
        except HttpError as error:
            print(f'An error occurred: {error}')
            return False
    
    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a Google Calendar event.
        
        Args:
            event_id: Google Calendar event ID
            
        Returns:
            Event data if found, None otherwise
        """
        try:
            event = self.service.events().get(
                calendarId='primary', eventId=event_id
            ).execute()
            return event
        
        except HttpError as error:
            print(f'An error occurred: {error}')
            return None

# Global instance for easy access
_calendar_service = None

def get_calendar_service() -> GoogleCalendarService:
    """Get or create the global Google Calendar service instance."""
    global _calendar_service
    if _calendar_service is None:
        _calendar_service = GoogleCalendarService()
    return _calendar_service 

if __name__ == "__main__":
    # To generate token.pickle from credentials.json in the project root,
    # run this script from the project root directory.
    GoogleCalendarService(credentials_file='credentials.json')