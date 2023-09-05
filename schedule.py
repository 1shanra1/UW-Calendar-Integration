from urllib import parse
from PyPDF2 import PdfReader
import re
import datetime 
import pickle 
import os.path 
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build 
from google.auth.transport.requests import Request

reader = PdfReader('MyUW.pdf')
text = ""

for i in range(1, len(reader.pages)):
    text += reader.pages[i].extract_text()

# Replacing non-breaking spaces with regular spaces
text = text.replace('\xa0', ' ')

def parse_schedule(s):
    # List of days
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    # Identify where each day starts in the string
    day_positions = [(day, s.find(day)) for day in days if day in s]
    # Create slices based on the found days
    slices = [s[start:end] for (day, start), (_, end) in zip(day_positions, day_positions[1:] + [(None, None)])]
    # Regex pattern to parse courses, location, and timing
    pattern = re.compile(r'(E C E \d+:  [a-zA-Z ]+|COMP SCI \d+:  [a-zA-Z ]+)(?:\n(LAB \d+|LEC \d+|DIS \d+))?\n([\w\s\d]+)\n([\d:]+ [APM]+ to [\d:]+ [APM]+)')
    data = {}
    for day, slice_data in zip([day for day, _ in day_positions], slices):
        matches = pattern.findall(slice_data)
        if matches:
            data[day] = [{"course": match[0], "location": match[2], "time": match[3]} for match in matches]
    return data


parsed_data = parse_schedule(text)

SCOPES = ['https://www.googleapis.com/auth/calendar']

def authenticate_with_google():
    creds = None 
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('client_secret_643971126542-7udc7gg0usomvgl79jke8llna7nsssrb.apps.googleusercontent.com.json', SCOPES)
            creds = flow.run_local_server(port = 8080)
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
    
    service = build('calendar', 'v3', credentials=creds)
    return service

def add_schedule_to_calendar(parsed_data, calendar_service):
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())

    for day, classes in parsed_data.items():
        date = monday
        if day == "Tuesday":
            date = monday + datetime.timedelta(days = 1)
        elif day == "Wednesday":
            date = monday + datetime.timedelta(days=2)
        elif day == "Thursday":
            date = monday + datetime.timedelta(days=3)
        elif day == "Friday":
            date = monday + datetime.timedelta(days=4)
        
        for class_info in classes:
            start_time_str = class_info["time"].split(" to ")[0]
            end_time_str = class_info["time"].split(" to ")[1]

            start_time = datetime.datetime.strptime(start_time_str, '%I:%M %p').time()
            end_time = datetime.datetime.strptime(end_time_str, '%I:%M %p').time()

            start_datetime = datetime.datetime.combine(date, start_time)
            end_datetime = datetime.datetime.combine(date, end_time)

            event = {
                'summary': class_info["course"],
                'location': class_info["location"],
                'start': {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': 'America/Chicago',  # e.g., 'America/Los_Angeles'
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'America/Chicago',
                },
                'reminders': {
                    'useDefault': True,
                },
            }

            event = calendar_service.events().insert(calendarId='primary', body=event).execute()
            print('Event created: %s' % (event.get('htmlLink')))

service = authenticate_with_google()
add_schedule_to_calendar(parsed_data, service)
