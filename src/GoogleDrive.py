from langchain_google_community import GoogleDriveLoader
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
import os
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = ""
import io
SCOPE = ['https://www.googleapis.com/auth/drive','https://www.googleapis.com/auth/drive.file']
class DriveAPI:
    def __init__(self):
        self.cred_path = '../credentials.json'
        self.token_path = '../google_token.json'
        self.parentImgVectorsFolderID = '1vgCCefOk8pjm1j3mwAJKlj90XNbmihu4'
        self.creds = None
        self.cred_state = False
        self.cred_url = None
        self.loader = None
        self.flow = None 
        self.parentPdfVectorsFolderID = None
        
        if os.path.exists(self.token_path):
            self.creds = Credentials.from_authorized_user_file(self.token_path)
        
        if self.creds and self.creds.valid:
            self.cred_state = True
        elif self.creds and self.creds.expired and self.creds.refresh_token:
            self.creds.refresh(Request())
            self.cred_state = True
            with open(self.token_path, 'w') as f:
                f.write(self.creds.to_json())
        
        else:
            self.cred_state = False
            if os.environ.get("PROD") == "true":
                redirect_uri = os.environ.get("PROD_URL") 
            else:
                redirect_uri = "http://127.0.0.1:8000/oauth2callback"  

            self.flow = Flow.from_client_secrets_file(
                self.cred_path,
                scopes=SCOPE,
                redirect_uri=redirect_uri
            )

            self.cred_url, _ = self.flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true'
            )

        if self.cred_state:
            self.loader = GoogleDriveLoader(
                folder_id=self.folder_id,
                token_path=self.token_path,
                credentials_path=self.cred_path,
                recursive=False
            )
        if not (self.parentPdfVectorsFolderID and self.folder_id):
            self.create_initial_folders()
    def create_initial_folders(self):
        try:
            service = build('drive','v3',credentials=self.creds)
            file_pdfEmb_metadata = {
                 'name':"ImgVectors",
                 "mimeType": "application/vnd.google-apps.folder",
            }
            file_imgEmb_metadata = {
                'name':"PdfVectors",
                 "mimeType": "application/vnd.google-apps.folder",
            }
            file_Img_vectors = service.files().create(body=file_pdfEmb_metadata,fields="id").execute()
            file_Pdf_vectors = service.files().create(body=file_imgEmb_metadata,fields="id").execute()
           
            self.parentPdfVectorsFolderID=file_Pdf_vectors.get('id')
            self.parentImgVectorsFolderID=file_Img_vectors.get('id')
            return {'success':True}
        except Exception as e:
            print('error occured in create_initial_folders',e)
    def finalize_login(self, code):
        self.flow.fetch_token(code=code)
        self.creds = self.flow.credentials
        
        with open(self.token_path, 'w') as f:
            f.write(self.creds.to_json())
            
        self.cred_state = True
        
        self.loader = GoogleDriveLoader(
            folder_id=self.folder_id,
            token_path=self.token_path,
            credentials_path=self.cred_path,
            recursive=False
        )
        return True
    def upload_file(self,filename):
        try:
            service = build("drive", "v3", credentials=self.creds)
            file_metadata = {
                "name": filename,
                "parents": [self.parentPdfVectorsFolderID] 
            }
            media = MediaFileUpload(filename, mimetype='application/octet-stream')
            file = service.files().create(
                body=file_metadata, 
                media_body=media, 
                fields="id"
            ).execute()
            
            file_id = file.get("id")
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
    def get_specific_file(self,file_id):
        try:
            service = build('drive','v3',credentials=self.creds)
            request = service.files().get(fileId=file_id).execute()
            if request['name'] != '':
                return True
            
        except Exception as e:
            print("Error has been occured in get_specific_file ",e)
            if e.resp.status == 404:
                return False
            else:
                print("Some other error")
                return False
    def get_all_pdf_vectors(self):
        try:
            service = build('drive', 'v3', credentials=self.creds)
            files = []
            page_token = None
            
            while True:
        
                query = f"'{self.parentPdfVectorsFolderID}' in parents "
                response = (
                    service.files().list(
                        q=f'{query}',
                        spaces='drive',
                        fields="nextPageToken, files(id, name, mimeType)", 
                        pageToken=page_token,
                        supportsAllDrives=True, 
                        includeItemsFromAllDrives=True
                    ).execute()
                )
                
                found_files = response.get('files', [])
                sendFilesMime = []
                for file in found_files:
                    sendFilesMime.append({"name":file.get('name'),"type":file.get('mimeType'), 'id':file.get('id')})
                files.extend(found_files)
                page_token = response.get("nextPageToken", None)
                
                if page_token is None:
                    break
                    
        except HttpError as error:
            print(f"An error occurred: {error}")
            files = None

        return sendFilesMime
    def get_documents(self):
        try:
            service = build('drive', 'v3', credentials=self.creds)
            files = []
            page_token = None
            
            while True:
        
                query = f"'{self.folder_id}' in parents "
                response = (
                    service.files().list(
                        q=f'{query}',
                        spaces='drive',
                        fields="nextPageToken, files(id, name, mimeType)", 
                        pageToken=page_token,
                        supportsAllDrives=True, 
                        includeItemsFromAllDrives=True
                    ).execute()
                )
                
                found_files = response.get('files', [])
                sendFilesMime = []
                for file in found_files:
                    sendFilesMime.append({"name":file.get('name'),"type":file.get('mimeType'), 'id':file.get('id')})
                files.extend(found_files)
                page_token = response.get("nextPageToken", None)
                
                if page_token is None:
                    break
                    
        except HttpError as error:
            print(f"An error occurred: {error}")
            files = None

        return sendFilesMime

