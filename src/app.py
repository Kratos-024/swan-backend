import base64
from typing import List, Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from ChatController import Chat_HuggingFaceController
from GoogleDrive import DriveAPI
from PdfEmbedding import PDFEmbed
from imageEmbedCreation import ImgEmbedder
import torch
app = FastAPI()
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_headers=['*'],allow_credentials=True,allow_methods=['*'])
MODEL = 'meta-llama/Meta-Llama-3-8B-Instruct'
DB_URI = "postgresql://postgres:mysecretpassword@localhost:5432/postgres"
IMAGE_MODEL_FOLDER = "../siglip_model"
PDF_MODEL_FOLDER='../pdf_embedder ' 
device = 'cuda' if torch.cuda.is_available() else 'cpu'
img_embedder = ImgEmbedder(IMAGE_MODEL_FOLDER)
chat_model = Chat_HuggingFaceController(MODEL,DB_URI)
mydriveInst = DriveAPI()
myPdfInsta = PDFEmbed(PDF_MODEL_FOLDER,device,mydriveInst)
class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None
class Buffer_data(BaseModel):
    data: List[int]
class EmbeddingRequest(BaseModel):
    buffer: Buffer_data
class PdfRequest(BaseModel):
    buffer: Buffer_data   
    pdf_name:str
class ImageQueryRequest(BaseModel):
    img_query: str

@app.get('/')
def testing():
    return {'response':"running"}


def check_drive_auth():
    try:
        if not mydrive.cred_state:
            url_string = mydrive.cred_url
            return {
                'url_string':url_string,"auth":False
            }
        return {
                "auth":True
            }

    except Exception as e:
        return {'error': str(e)}

@app.post('/chat')
def getReply_text(request:ChatRequest):
    try:
        user_query = request['message']
        thread_id = request['thread_id']
        response = chat_model.chat(user_query,thread_id)
        return {'reply':response}
    except Exception as e:
        return {'error':str(e)}

@app.post('/chat-img')
def getReply_imgQuery(request:ImageQueryRequest):
    try:
        print('img_queryimg_queryimg_queryimg_query',request)
        check_authorization = check_drive_auth()
        if not check_authorization['auth']:
            return {'url_string': check_authorization['url_string'],'auth':False}
     
        img_query = request.img_query
        img_buffer = img_embedder.search_and_send(img_query)
        return {'imageResponse':base64.b64encode(img_buffer[0]).decode('utf-8')}
    except Exception as e:
        print(e)
        return {'error':str(e)}
    

@app.post('/create-embed')
def createEmbedding(data: EmbeddingRequest):
    try:

        check_authorization = check_drive_auth()
        if not check_authorization['auth']:
            return {'url_string': check_authorization['url_string'],'auth':False}
        
        img_list = data.buffer.data
        img_embedder.ProcessedImg([img_list])
        img_embedder.createEmbedding()
        
        return {'reply': 'Embeddings created successfully'}

    except Exception as e:
        print(e)
        return {'error': str(e)}
    
@app.get("/oauth2callback")
async def handle_callback(request: Request):
    auth_code = request.query_params.get("code")
    if not auth_code:
        return {"error": "No code"}
    try:
        mydriveInst.finalize_login(auth_code)
        return {"message": "Login Successfully"}
    except Exception as e:
        return {"error": str(e)}  



@app.post('/create-embed')
def pdf_embedding_and_drive(data: PdfRequest):
    try:
        check_authorization = check_drive_auth()
        if not check_authorization['auth']:
            return {'url_string': check_authorization['url_string'],'auth':False}
        
        pdf_buffer = data.buffer.data
        pdf__name = data.pdf_name
        myPdfInsta.create_pdf_from_buffer(pdf_buffer,pdf__name)
        
        return {'reply': 'pdf and its embedding saved successfully'}

    except Exception as e:
        print(e)
        return {'error': str(e)}