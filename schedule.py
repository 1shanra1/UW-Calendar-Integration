import re
import datetime 
import pickle 
import os.path 
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build 
from google.auth.transport.requests import Request
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/calendar']
# file_path = 'MyUW.pdf'
# text = ""

def extract_text_from_pdf(file_path, text):
    for page_num, page in enumerate(extract_pages(file_path)):
        if page_num == 0:
            continue
        for element in page:
            if isinstance(element, LTTextContainer):
                if "MyUW" in element.get_text() or "https://my.wisc.edu/" in element.get_text():
                    continue
                text += element.get_text()
    
    text = text.replace('\xa0', ' ')
    return text 

def strip_dates(text):
    date_pattern = re.compile(r'\d{1,2}/\d{1,2}/\d{2}, \d{1,2}:\d{2} [APM]{2}')
    return date_pattern.sub('', text)

def parse_schedule(s):
    s = strip_dates(s)
    # List of days
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    # Identify where each day starts in the string
    day_positions = [(day, s.find(day)) for day in days if day in s]
    # Create slices based on the found days
    slices = [s[start:end] for (day, start), (_, end) in zip(day_positions, day_positions[1:] + [(None, None)])]
    # Regex pattern to parse courses, location, and timing
    # pattern = re.compile(r'(E C E \d+:  [a-zA-Z ]+|COMP SCI \d+:  [a-zA-Z ]+)(?:\n(LAB \d+|LEC \d+|DIS \d+))?\n([\w\s\d]+)\n([\d:]+ [APM]+ to [\d:]+ [APM]+)')
    pattern = re.compile(r'([A-Z ]+ \d+:  .+?)(?:\n(LAB \d+|LEC \d+|DIS \d+))?\n(.+?)\n((?:\d{1,2}:\d{2} [APM]{2}) to (?:\d{1,2}:\d{2} [APM]{2}))') 
    data = {}
    for day, slice_data in zip([day for day, _ in day_positions], slices):
        matches = pattern.findall(slice_data)
        if matches:
            data[day] = [{"course": match[0], "location": match[2], "time": match[3]} for match in matches]
    return data

def authenticate_with_google(credentials: Credentials) -> any:
    service = build('calendar', 'v3', credentials=credentials)
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
                    'timeZone': 'America/Chicago', 
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'America/Chicago',
                },
                'recurrence': ['RRULE:FREQ=WEEKLY;UNTIL=20231225T235959Z'],
                'reminders': {
                    'useDefault': True,
                },
            }

            print(event.get('summary'))
            start_datetime_human_readable = start_datetime.strftime('%A, %B %d, %Y %I:%M %p')
            print(start_datetime_human_readable)
            print()

            event = calendar_service.events().insert(calendarId='primary', body=event).execute()
            print('Event created: %s' % (event.get('htmlLink')))

# parsed_data = parse_schedule(extract_text_from_pdf(file_path, text))
# service = authenticate_with_google()
# add_schedule_to_calendar(parsed_data, service)

# def authenticate_with_google():
#     creds = None 
#     if os.path.exists('token.pickle'):
#         with open('token.pickle', 'rb') as token:
#             creds = pickle.load(token)
    
#     if not creds or not creds.valid:
#         if creds and creds.expired and creds.refresh_token:
#             creds.refresh(Request())
#         else:
#             flow = InstalledAppFlow.from_client_secrets_file('client_secret_643971126542-7udc7gg0usomvgl79jke8llna7nsssrb.apps.googleusercontent.com.json', SCOPES)
#             creds = flow.run_local_server(port = 8080)
#             with open('token.pickle', 'wb') as token:
#                 pickle.dump(creds, token)
    
#     service = build('calendar', 'v3', credentials=creds)
#     return service
