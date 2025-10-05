
import openai
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import json

# -------------------------
# CONFIGURATION
# -------------------------
openai.api_key = "YOUR_OPENAI_KEY"
GMAIL_USER = "youremail@gmail.com"
GMAIL_APP_PASSWORD = "YOUR_APP_PASSWORD"
SCOPES = ['https://www.googleapis.com/auth/calendar']

# -------------------------
# GOOGLE CALENDAR AUTH
# -------------------------
def get_calendar_service():
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)
    service = build("calendar", "v3", credentials=creds)
    return service

service = get_calendar_service()

# -------------------------
# PARSE TASK WITH GPT
# -------------------------
def parse_task(task_text):
    prompt = f"""
Convert the following task into JSON with fields: title, date (YYYY-MM-DD), time (HH:MM), duration (minutes, optional), description.
Task: {task_text}
"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role":"user","content":prompt}],
        temperature=0
    )
    json_text = response['choices'][0]['message']['content']
    try:
        task = json.loads(json_text)
    except:
        # fallback if GPT returns invalid JSON
        task = {"title": task_text, "date": datetime.today().strftime("%Y-%m-%d"), "time": "09:00", "duration": 60, "description": ""}
    return task

# -------------------------
# CHECK CONFLICTS
# -------------------------
def check_conflict(service, task):
    date = task['date']
    start_time = task['time']
    duration = int(task.get('duration', 60))
    start_dt = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=duration)

    events_result = service.events().list(
        calendarId='primary',
        timeMin=start_dt.isoformat() + 'Z',
        timeMax=end_dt.isoformat() + 'Z',
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    if events:
        return True, events[0]['summary']  # conflict with existing event
    return False, None

# -------------------------
# CREATE EVENT
# -------------------------
def create_event(service, task):
    start_dt = datetime.strptime(f"{task['date']} {task['time']}", "%Y-%m-%d %H:%M")
    duration = int(task.get('duration', 60))
    end_dt = start_dt + timedelta(minutes=duration)

    event = {
        "summary": task['title'],
        "description": task.get('description', ""),
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Asia/Kolkata"}
    }
    created_event = service.events().insert(calendarId='primary', body=event).execute()
    return created_event

# -------------------------
# SEND EMAIL REMINDER
# -------------------------
def send_email(to_email, subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = GMAIL_USER
    msg['To'] = to_email

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    server.send_message(msg)
    server.quit()

# -------------------------
# MAIN AGENT LOOP
# -------------------------
def main():
    task_text = input("Enter your task in natural language: ")
    task = parse_task(task_text)

    conflict, conflict_event = check_conflict(service, task)
    if conflict:
        print(f"⚠ Conflict detected with existing event: {conflict_event}")
        # auto-reschedule 1 hour later
        dt = datetime.strptime(f"{task['date']} {task['time']}", "%Y-%m-%d %H:%M") + timedelta(hours=1)
        task['time'] = dt.strftime("%H:%M")
        print(f"Rescheduling task to {task['time']}")

    event = create_event(service, task)
    print(f"✅ Task '{task['title']}' scheduled on {task['date']} at {task['time']}")

    # Send email reminder
    send_email(GMAIL_USER, f"Task Scheduled: {task['title']}",
               f"Your task '{task['title']}' is scheduled on {task['date']} at {task['time']}.")

if __name__ == "__main__":
    main()
