import os
import io
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
load_dotenv()
SCOPE = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/drive.file']
VECTOR_ZIP_NAME = 'pdf_vectors_archive.zip'
LOCAL_VECTOR_FOLDER = 'pdf_vectors_store'

class DriveAPI:
    def __init__(self):
        self.cred_path = '../credentials.json'
        self.token_path = '../google_token.json'
        self.parentImgVectorsFolderID = '1vgCCefOk8pjm1j3mwAJKlj90XNbmihu4' 
        self.parentPdfVectorsFolderID = None
        self.parentPdfFolderID = None
        self.creds = None
        self.service = None
        self.cred_state = False
        self.cred_url = None
        self._authenticate()
        if self.cred_state and self.service:
            self.create_initial_folders()

    def _authenticate(self):
     
        if os.path.exists(self.token_path):
            self.creds = Credentials.from_authorized_user_file(self.token_path)
        if self.creds and self.creds.valid:
            self.cred_state = True
        elif self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                with open(self.token_path, 'w') as f:
                    f.write(self.creds.to_json())
                self.cred_state = True
            except Exception as e:
                print(f"Error refreshing token: {e}")
                self.cred_state = False
        else:
            self.cred_state = False
        if not self.cred_state:
            if os.environ.get("PROD") == "true":
                redirect_uri = os.environ.get("PROD_URL") 
            else:
                redirect_uri = "http://127.0.0.1:8000/oauth2callback"  

            self.flow = Flow.from_client_secrets_file(
                self.cred_path, scopes=SCOPE, redirect_uri=redirect_uri
            )
            self.cred_url, _ = self.flow.authorization_url(prompt='consent')
            print(f"Auth required. URL generated: {self.cred_url}")
            return
        self.service = build('drive', 'v3', credentials=self.creds)
    def oauth2callback(self,auth_code):
        try:
            self.flow.fetch_token(code=auth_code)
            self.creds = self.flow.credentials
            with open(self.token_path,'w') as f:
                f.write(self.creds.to_json())
            self.cred_state = True

            self.service = build('drive', 'v3', credentials=self.creds)

            return True
        except Exception as e:
            print("OAuth callback error:", e)
            self.cred_state = False
            return False



    def create_initial_folders(self):
        try:

            self.parentImgVectorsFolderID = self._get_or_create_folder("ImgVectors")
            self.parentPdfVectorsFolderID = self._get_or_create_folder("PdfVectors")
            self.parentPdfFolderID = self._get_or_create_folder("Pdfs")

        except Exception as e:
            print(f'error has been occured in create_initial_folders: {e}')

    def _get_or_create_folder(self, folder_name):
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = self.service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = results.get('files', [])
        
        if files:
            print(f"Found folder {folder_name}: {files[0]['id']}")
            return files[0]['id']
        else:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = self.service.files().create(body=file_metadata, fields='id').execute()
            print(f"created {folder_name}:{folder.get('id')}")
            return folder.get('id')

    def upload_pdf_file(self, filename):
        try:
            file_metadata = {'name': filename, 'parents': [self.parentPdfFolderID]}
            media = MediaFileUpload(filename, mimetype='application/pdf')
            file = self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
           
            return file.get('id')
        except HttpError as error:
            print(f"error has been occured in upload_pdf_file: {error}")
            return None

    def search_vector_zip(self):
        try:
            query = f"'{self.parentPdfVectorsFolderID}' in parents and name = '{VECTOR_ZIP_NAME}' and trashed = false"
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            files = results.get('files', [])
            if files:
                return files[0] 
            return None
        except HttpError as e:
            print(f"error searching the vector zip: {e}")
            return None

    def download_file(self, file_id, output_filename):
        try:
            request = self.service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            fh.seek(0)
            with open(output_filename, 'wb') as f:
                f.write(fh.read())
            print(f"Downloaded {output_filename}")
            return True
        except HttpError as error:
            print(f"Download error: {error}")
            return False

    def upload_or_update_vector_zip(self, local_zip_path):
        existing_file = self.search_vector_zip()
        media = MediaFileUpload(local_zip_path, mimetype='application/zip', resumable=True)
        if existing_file:
            self.service.files().update(
                fileId=existing_file['id'],
                media_body=media
            ).execute()
        else:
            file_metadata = {
                'name': VECTOR_ZIP_NAME,
                'parents': [self.parentPdfVectorsFolderID]
            }
            self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
    def search_vector_img(self,file_path):
        try:
            query = f"'{self.parentImgVectorsFolderID}' in parents and name = '{file_path}' and trashed = false"
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            files = results.get('files', [])
            if files:
                return files[0] 
            return None
        except HttpError as e:
            print(f"error searching the image json: {e}")
            return None
    def upload_vector_img(self,file_path):
        existing_file = self.search_vector_img(file_path)
        
        media = MediaFileUpload(file_path, mimetype='application/octet-stream', resumable=True)
        if existing_file:
            self.service.files().update(
                fileId=existing_file['id'],
                media_body=media
            ).execute()
        else:
            file_metadata = {
                'name': file_path,
                'parents': [self.parentImgVectorsFolderID]
            }
            self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
    def upload_image(self, image_path):
            actual_filename = os.path.basename(image_path)
            
            media = MediaFileUpload(image_path, mimetype='image/png') 
            file_metadata = {
                'name': actual_filename, 
                'parents': [self.parentImgVectorsFolderID] 
            }
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            return file.get('id')

