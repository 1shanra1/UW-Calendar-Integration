# from urllib import parse
# from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
# from starlette.responses import HTMLResponse, RedirectResponse
# from sqlalchemy.orm import Session
# from google.oauth2.credentials import Credentials
# from google_auth_oauthlib.flow import Flow 
# from schedule import extract_text_from_pdf, parse_schedule, authenticate_with_google, add_schedule_to_calendar, strip_dates
# from database import SessionLocal, User
# import uuid 

# app = FastAPI()

# CLIENT_SECRET = "client_secret_643971126542-7udc7gg0usomvgl79jke8llna7nsssrb.apps.googleusercontent.com.json"
# SCOPES = ["https://www.googleapis.com/auth/calendar"]

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

# @app.get("/login")
# def login():
#     flow = Flow.from_client_secrets_file(CLIENT_SECRET, scopes=SCOPES, redirect_uri="http://localhost:8000/login/callback")
#     authorization_url, state = flow.authorization_url(prompt="consent")
#     return RedirectResponse(authorization_url)

# @app.get("/login/callback")
# def callback(state: str = "", code: str = "", db: Session = Depends(get_db)):
#     flow = Flow.from_client_secrets_file(CLIENT_SECRET, scopes=SCOPES, state=state, redirect_uri="http://localhost:8000/login/callback")
#     flow.fetch_token(code=code)
#     credentials = flow.credentials

#     # Saving to DB (replace 'your_user_identifier' with an actual unique identifier)
#     user = User(username="your_user_identifier", token=credentials.to_json())
#     db.add(user)
#     db.commit()

#     return {"message": "Logged in successfully"}

# @app.post("/logout")
# def logout(db: Session = Depends(get_db)):
#     user = db.query(User).filter(User.username == "your_user_identifier").first()  # Adjust the filter appropriately
#     if user:
#         db.delete(user)
#         db.commit()
#     return {"message": "Logged out and token cleared"}

# @app.get("/")
# def read_root():
#     content = """
#     <form action="/uploadpdf/" enctype="multipart/form-data" method="post">
#     <input name="file" type="file">
#     <input type="submit">
#     </form>
#     """
#     return HTMLResponse(content=content)

# @app.post("/uploadpdf/")
# async def upload_pdf(file: UploadFile = File(...)):

#     text = ""

#     if file.filename.endswith('.pdf'):
#         content = await file.read()
#         with open(f"uploads/{file.filename}", "wb") as f:
#             f.write(content)

#         text = extract_text_from_pdf(f"uploads/{file.filename}", text)
#         parsed_data = parse_schedule(text)

#         service = authenticate_with_google()
#         add_schedule_to_calendar(parsed_data, service)
        
#         return {"filename": file.filename, "info": "Uploaded and processed"}
#     else:
#         raise HTTPException(status_code=400, detail="Invalid file type")

from urllib import parse
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, BackgroundTasks
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.requests import Request
from sqlalchemy.orm import Session
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from schedule import extract_text_from_pdf, parse_schedule, authenticate_with_google, add_schedule_to_calendar, strip_dates
from database import SessionLocal, User
import os
import uuid
import json

app = FastAPI()

CLIENT_SECRET = "client_secret_643971126542-7udc7gg0usomvgl79jke8llna7nsssrb.apps.googleusercontent.com.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/login")
def login():
    user_id = str(uuid.uuid4())  # create a unique user identifier
    flow = Flow.from_client_secrets_file(CLIENT_SECRET, scopes=SCOPES, redirect_uri="http://localhost:8000/login/callback")
    authorization_url, state = flow.authorization_url(prompt="consent", state=user_id)
    return RedirectResponse(authorization_url)

@app.get("/login/callback")
def callback(state: str = "", code: str = "", db: Session = Depends(get_db)):
    user_id = state  # state is the user_id we sent during login
    flow = Flow.from_client_secrets_file(CLIENT_SECRET, scopes=SCOPES, state=state, redirect_uri="http://localhost:8000/login/callback")
    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Saving to DB
    user = User(username=user_id, token=credentials.to_json())
    db.add(user)
    db.commit()

    response = RedirectResponse(url="/")
    response.set_cookie(key="user_id", value=user_id, httponly=True)  # Set the user_id in a cookie for further identification
    return response

@app.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    user = db.query(User).filter(User.username == user_id).first()
    if user:
        db.delete(user)
        db.commit()
    response = RedirectResponse(url="/")
    response.delete_cookie(key="user_id")
    return response

@app.get("/")
def landing_page(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")  # Check if we have a user_id stored in a cookie

    if user_id:
        user = db.query(User).filter(User.username == user_id).first()
        if user:  # If user exists in the database
            # Return file upload form
            content = """
            <form action="/uploadpdf/" enctype="multipart/form-data" method="post">
            <input name="file" type="file">
            <input type="submit">
            </form>
            """
            return HTMLResponse(content=content)
    
    return HTMLResponse(content='<a href="/login"> Login with Google</a>')

@app.post("/uploadpdf/")
async def upload_pdf(request: Request, background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.query(User).filter(User.username == user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    credentials = Credentials.from_authorized_user_info(json.loads(user.token))
    service = authenticate_with_google(credentials=credentials)

    text = ""
    if file.filename.endswith('.pdf'):
        content = await file.read()
        file_path = f"uploads/{file.filename}"
        with open(file_path, "wb") as f:
            f.write(content)

        text = extract_text_from_pdf(file_path, text)
        parsed_data = parse_schedule(text)
        add_schedule_to_calendar(parsed_data, service)

        # Schedule file deletion in the background
        background_tasks.add_task(os.remove, file_path)
        
        return {"filename": file.filename, "info": "Uploaded and processed"}
    else:
        raise HTTPException(status_code=400, detail="Invalid file type")
