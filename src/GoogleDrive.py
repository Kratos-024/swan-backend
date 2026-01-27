from langchain_google_community import GoogleDriveLoader
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import os
import io
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = ""

class DriveAPI:
    def __init__(self):
       
        self.cred_path = '../credentials.json'  
        self.token_path = '../google_token.json' 
        self.folder_id = '13jA4Xa3vcmzfKm424zYbszhjfd5amb3l' 
        self.creds = None

        if os.path.exists(self.token_path):
            self.creds = Credentials.from_authorized_user_file(self.token_path)
            
      
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                print("Refreshing expired token...")
                self.creds.refresh(Request())
            else:
                print("Logging in via Browser...")
                flow = InstalledAppFlow.from_client_secrets_file(
                        self.cred_path, 
                        scopes=['https://www.googleapis.com/auth/drive']
                    )
                self.creds = flow.run_local_server(port=0)
            

            with open(self.token_path, 'w') as token:
                token.write(self.creds.to_json())

      
        self.loader = GoogleDriveLoader(
            folder_id=self.folder_id,
            token_path=self.token_path,
            credentials_path=self.cred_path,
            recursive=False
        )
        print("Authentication Successful.")

    def upload_file(self, filename):
        try:
            service = build("drive", "v3", credentials=self.creds)
            
         
            file_metadata = {
                "name": filename,
                "parents": [self.folder_id] 
            }

            media = MediaFileUpload(filename, mimetype='application/octet-stream')

        
            file = service.files().create(
                body=file_metadata, 
                media_body=media, 
                fields="id"
            ).execute()
            
            file_id = file.get("id")
            print(f'Upload Complete File ID: "{file_id}"')
            return file_id

        except HttpError as error:
            print(f"error: {error}")
            return None

    def download_file(self, file_id, output_filename):
        try:
            service = build('drive', 'v3', credentials=self.creds)

            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                 done = downloader.next_chunk()
            fh.seek(0)
            with open(output_filename, 'wb') as f:
                f.write(fh.read())
            

        except HttpError as error:
            print(f"Download error: {error}")
