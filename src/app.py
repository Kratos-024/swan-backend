from fastapi import FastAPI, Request,Response
from fastapi.middleware.cors import CORSMiddleware
from ChatController import Chat_HuggingFaceController
app = FastAPI()
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_headers=['*'],allow_credentials=True,allow_methods=['*'])


MODEL = 'meta-llama/Meta-Llama-3-8B-Instruct'
DB_URI = "postgresql://postgres:mysecretpassword@localhost:5432/postgres"


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
        response = chat_model.chat(user_query,thread_id)
        return {'reply':response}
    except Exception as e:
        return {'error':str(e)}

@app.post('/chat-img')
async def getReply(request:Request):
    try:
        data =  await request.json()
        img_buffer = data.get('message')
        thread_id = data.get('thread_id')
        response = chat_model.chat(user_query,thread_id)
        return {'reply':response}
    except Exception as e:
        return {'error':str(e)}