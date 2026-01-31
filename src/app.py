from typing import List, Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PdfEmbedding import PDFEmbed
from pydantic import BaseModel
import torch
from GoogleDrive import DriveAPI
import os
from imageEmbedCreation import ImgEmbedder
import base64

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_headers=['*'],
    allow_credentials=True,
    allow_methods=['*']
)
MODEL = 'meta-llama/Meta-Llama-3-8B-Instruct'
DB_URI = "postgresql://postgres:mysecretpassword@localhost:5432/postgres"
IMAGE_MODEL_FOLDER = "../siglip_model"
PDF_MODEL_FOLDER = '../pdf_embeder-bge-base' 
device = 'cuda' if torch.cuda.is_available() else 'cpu'
mydriveInst = DriveAPI()
img_embedder = ImgEmbedder(IMAGE_MODEL_FOLDER,mydriveInst,device)
# chat_model = Chat_HuggingFaceController(MODEL, DB_URI)
myPdfInsta = PDFEmbed(PDF_MODEL_FOLDER, device, mydriveInst)

class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None

class Buffer_data(BaseModel):
    data: List[int]

class EmbeddingRequest(BaseModel):
    buffer: Buffer_data

class PdfRequest(BaseModel):
    buffer: Buffer_data   
    pdf_name: str

class PdfQuerySearch(BaseModel):
    Pdf_query: str   

class ImageQueryRequest(BaseModel):
    img_query: str

def createBase64Bytes(file_path):
    try:
        if not os.path.exists(file_path):
            return None
        with open(file_path, 'rb') as f:
            image_data = f.read()
            return base64.b64encode(image_data).decode('utf-8')
    except Exception as e:
        print(f"err in  createBase64Bytes {e}")
        return None

def check_drive_auth():
    try:
        if not mydriveInst.cred_state:
            return {'url_string': mydriveInst.cred_url, "auth": False}
        return {"auth": True}
    except Exception as e:
        return {'error': str(e)}

@app.get('/')
def testing():
    return {'response': "Server is running"}

@app.get("/oauth2callback")
async def handle_callback(request: Request):
    auth_code = request.query_params.get("code")
    if not auth_code:
        return {"error": "No code"}
    try:
        mydriveInst.oauth2callback(auth_code)
        return {"message": "Login Successfully"}
    except Exception as e:
        return {"error": str(e)}

# @app.post('/chat')
# def getReply_text(request: ChatRequest):
#     try:
#         return {'reply': chat_model.chat(request.message, request.thread_id)}
#     except Exception as e:
#         return {'error': str(e)}

@app.post('/chat-img')
def getReply_imgQuery(request: ImageQueryRequest):
    try:
        auth = check_drive_auth()
        if not auth.get('auth'): return auth
     
        img_buffer = img_embedder.search_and_send(request.img_query)
        if img_buffer and isinstance(img_buffer, list) and len(img_buffer) > 0:
            return {'imageResponse': base64.b64encode(img_buffer[0]).decode('utf-8')}
        else:
            return {
                'imageResponse': 'No image found'
            }
    except Exception as e:
        print('error in getReply_imgQuery', e)
        return {'error': str(e)}
@app.post('/create-embed-img')
def createEmbeddingRoute(data: EmbeddingRequest):
    try:
        auth = check_drive_auth()
        if not auth.get('auth'): return auth
    
        img_embedder.add_image(bytes(data.buffer.data))
        return {'reply': 'Embeddings created'}
    except Exception as e:
        return {'error': str(e)}

@app.post('/send-pdfbuffer')
def pdf_embedding_and_drive(data: PdfRequest):
    try:
        auth = check_drive_auth()
        if not auth.get('auth'): return auth
        fileId = myPdfInsta.create_pdf_from_buffer(data.buffer.data, data.pdf_name)
        myPdfInsta.createEmbedding(fileId)
        return {'reply': 'PDF metadata indexed successfully'}
    except Exception as e:
        print('Error:', e)
        return {'error': str(e)}

@app.post('/search_pdf_query')
def pdf_query_search(data: PdfQuerySearch):
    try:
        auth = check_drive_auth()
        if not auth.get('auth'): return auth

        results = myPdfInsta.search_query(data.Pdf_query, k=2)
        if not results:
            return {'reply': []}
        if not 'pdfBytes' in results:
            response_list = []
            for doc in results:
                meta = doc.metadata 
                cover_id = meta.get('coverPageid')
                base64Bytes = None
                
                if cover_id:
                    temp_name = f"{cover_id}_temp.png"
                    try:
                        mydriveInst.download_file(cover_id, temp_name)
                        base64Bytes = createBase64Bytes(temp_name)
                    except Exception as e:
                        print(f"Cover download failed: {e}")
                    finally:
                        if os.path.exists(temp_name): os.remove(temp_name)

                response_list.append({
                    'File_Name': meta.get('fileName', 'Unknown'),
                    'date': meta.get('date', ''),
                    'total_pages': meta.get('total_pages', 'N/A'),
                    'cover_buffer': base64Bytes
                })
            return {'reply': response_list}
        elif 'pdfBytes' in results:
            return JSONResponse(content={'reply':results['pdfBytes'],'pdf_name':results['pdf_name']})
    except Exception as e:
        print('Error in pdf_query_search:', e)
        return {'error in pdf_query_search': str(e)}