import base64
from io import BytesIO
import PIL
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from ChatController import Chat_HuggingFaceController
from GoogleDrive import DriveAPI
from imageEmbedCreation import ImgEmbedder
app = FastAPI()
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_headers=['*'],allow_credentials=True,allow_methods=['*'])

driveapi = DriveAPI()
driveapi.__init__()
MODEL = 'meta-llama/Meta-Llama-3-8B-Instruct'
DB_URI = "postgresql://postgres:mysecretpassword@localhost:5432/postgres"

MODEL_FOLDER = "../siglip_model" 

img_embedder = ImgEmbedder(MODEL_FOLDER)


chat_model = Chat_HuggingFaceController(MODEL,DB_URI)

@app.get('/')
def testing():
    return {'response':"running"}


@app.post('/chat')
async def getReply(request:Request):
    try:
        data =  await request.json()
        user_query = data.get('message')
        thread_id = data.get('thread_id')
        print(user_query)
        response = chat_model.chat(user_query,thread_id)
        return {'reply':response}
    except Exception as e:
        return {'error':str(e)}

@app.post('/chat-img')
async def getReply(request:Request):
    try:
        data =  await request.json()
        img_query = data.get('img_query')
        img_buffer = img_embedder.search_and_send(img_query)
        return {'reply':base64.b64encode(img_buffer[0]).decode('utf-8')}
    except Exception as e:
        return {'error':str(e)}
    

@app.post('/create-embed')
async def createEmbedding(data: Request):
    try:
        data = await data.json()
        img_list = data.get('buffer', {}).get('data')
        img_embedder.ProcessedImg([img_list])
        img_embedder.createEmmbedding()
        return {'reply': 'created successfully'}

    except Exception as e:
        return {'error': str(e)}
