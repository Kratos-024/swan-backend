import io
import os
from langchain_huggingface import HuggingFaceEmbeddings, ChatHuggingFace, HuggingFaceEndpoint
from langchain_community.document_loaders import PyPDFLoader
import re 
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate
import json
import shutil
import zipfile
from langchain_core.documents import Document
from pdf2image import convert_from_path
import gc

import numpy as np
from datetime import date
VECTOR_ZIP_NAME = 'pdf_vectors_archive.zip'
LOCAL_VECTOR_FOLDER = 'pdf_vectors_store'
RESULT_JSON_FILE = 'result.json'

class PDFEmbed:
    def __init__(self, model_path, device, myDriveInst, repo_id="Qwen/Qwen2.5-7B-Instruct"):
        self.model_path = model_path
        self.device = device
        self.myDrive = myDriveInst
        self.pdf_path_name = ''
        self.embedding_model = HuggingFaceEmbeddings(
            model_name=self.model_path,
            model_kwargs={'device': device},
            encode_kwargs={'normalize_embeddings': True}
        )
        self.llm = HuggingFaceEndpoint(
            repo_id=repo_id,
            task="text-generation",
            max_new_tokens=512,
            do_sample=False,
            repetition_penalty=1.03,
        )
        self.chat_model = ChatHuggingFace(llm=self.llm)

    def create_pdf_from_buffer(self, pdf_buffer, pdf_file_name):
        pdf_bytes = bytes(pdf_buffer)
        buffer = io.BytesIO()
        buffer.write(pdf_bytes)
        buffer.seek(0)
        
        try:
            with open(pdf_file_name, 'wb') as f:
                f.write(buffer.getbuffer())
            self.pdf_path_name = pdf_file_name
        except IOError as e:
            print(f"error occured in create_pdf_from_buffer: {e}")
        finally:
            buffer.close()
            
        return self.myDrive.upload_pdf_file(pdf_file_name)

    def get_buffer_cover(self, fileId):
        try:
            pages = convert_from_path(self.pdf_path_name, first_page=1, last_page=1)
            if not pages: return None
            
            cover_image = pages[0].resize((300, 400))
            self.temp_filename = f"{fileId}_cover.png"
            cover_image.save(self.temp_filename, format='PNG')
            uploaded_cover_id = self.myDrive.upload_image(self.temp_filename)
            if os.path.exists(self.temp_filename): os.remove(self.temp_filename)
            return uploaded_cover_id
        except Exception as e:
            print(f"error has been occured in get_buffer_cover: {e}")
            return None

    def getAIResponse(self, text):
        summary_prompt = PromptTemplate(
            template=("""
            You are generating text for semantic embeddings of a PDF.
            
            TASK: Analyze the document text below and produce a search-aware summary.
            
            Your response MUST include:
            1. Document type (textbook, notes, question paper, etc.)
            2. Exact Title and Author.
            3. Main Subject.
            4. A paragraph with realistic user search queries (e.g. "send me notes for...", "book by...").
            
            DOCUMENT TEXT:
            {raw_text_context}
            """),
            validate_template=True,
            input_variables=["raw_text_context"]
        )

        ai_response_prompt = summary_prompt.invoke({'raw_text_context': text})
        ai_response = self.chat_model.invoke(ai_response_prompt)
        return ai_response.content

    def formatTheQuery(self, text):
        if os.path.exists(RESULT_JSON_FILE):
            router_prompt = PromptTemplate(
                template=("""
                You are a strict Intent Classifier. You are NOT a chatbot. 
                Do not explain. Do not write code.

                Task: Analyze the user input "{text}" relative to a list of search results.

                1. SELECTION: If the user is picking a specific item (e.g. "first one", "book 2", "yes that one", "send the second").
                   - Output format: NEGATIVE <IndexNumber>
                   - Convert words to 0-based index: "first"=0, "second"=1, "third"=2.

                2. SEARCH: If the user is asking for a new topic (e.g. "send me java", "notes for ai").
                   - Output format: POSITIVE

                OUTPUT ONLY THE STRING. NO OTHER TEXT.
                """),
                input_variables=["text"]
            )  
        else:
            router_prompt = PromptTemplate(
                template=("""
                You are a strict Intent Classifier.
                User input: "{text}"
                
                Task: Detect if this is a request for a document.
                Output: POSITIVE
                
                OUTPUT ONLY THE WORD "POSITIVE".
                """),
                input_variables=["text"]
            )

        response = self.chat_model.invoke(router_prompt.invoke({'text': text})).content.strip()
        response = response.replace('"', '').replace("'", "")
        
        if "NEGATIVE" in response: return response
        return "POSITIVE"
    
    def handle_selection(self, index):
        if not os.path.exists(RESULT_JSON_FILE):
            return [] 
        try:
            with open(RESULT_JSON_FILE, 'r') as f:
                history_results = json.load(f)
            
            if 0 <= index < len(history_results):
                doc_data = history_results[index]
                file_id = doc_data['metadata'].get('fileId')
                file_name = doc_data['metadata'].get('fileName', 'downloaded_file.pdf')
                
                if file_id:
                    self.myDrive.download_file(file_id, file_name)
                restored_doc = Document(
                    page_content=doc_data['page_content'], 
                    metadata=doc_data['metadata']
                )
                os.remove(RESULT_JSON_FILE)
                
                return [restored_doc]
            else:
                return []
        except Exception as e:
            print(f"Error in handle_selection: {e}")
            return []
    def createEmbedding(self, fileId):
        loader = PyPDFLoader(self.pdf_path_name)
        all_pages = loader.load()
        total_pages_count = len(all_pages)
        
        pages_for_ai = all_pages[:10] if len(all_pages) > 10 else all_pages
        raw_text_context = " ".join([p.page_content for p in pages_for_ai])[:8000]
        
        clean_filename = os.path.basename(self.pdf_path_name)
        clean_filename_spaced = re.sub(r'[_\-\.]', ' ', clean_filename).replace("pdf", "")
        ai_summary_text = self.getAIResponse(raw_text_context)
        
        final_content = (
            f"Book Title: {clean_filename_spaced}\n" 
            f"File Name: {clean_filename}\n"
            f"AI Analysis: {ai_summary_text}"
        )
        
        summary_doc = Document(
            page_content=final_content,
            metadata={
                'coverPageid': self.get_buffer_cover(fileId),
                "fileId": fileId,
                "fileName": self.pdf_path_name,
                "chunkIndex": 0,
                "total_pages": total_pages_count, 
                "date": str(date.today())
            }
        )

        new_vector_store = FAISS.from_documents([summary_doc], self.embedding_model)
        final_vector_store = None
        drive_zip = self.myDrive.search_vector_zip()
        
        if drive_zip:
            self.myDrive.download_file(drive_zip['id'], VECTOR_ZIP_NAME)
            if os.path.exists(LOCAL_VECTOR_FOLDER):
                shutil.rmtree(LOCAL_VECTOR_FOLDER)
            with zipfile.ZipFile(VECTOR_ZIP_NAME, 'r') as zip_ref:
                zip_ref.extractall(LOCAL_VECTOR_FOLDER)
            try:
                old_vector_store = FAISS.load_local(
                    LOCAL_VECTOR_FOLDER, 
                    self.embedding_model,
                    allow_dangerous_deserialization=True 
                )
                old_vector_store.merge_from(new_vector_store)
                final_vector_store = old_vector_store
            except Exception as e:
                final_vector_store = new_vector_store
        else:
            final_vector_store = new_vector_store

        final_vector_store.save_local(LOCAL_VECTOR_FOLDER)
        shutil.make_archive('upload_temp', 'zip', LOCAL_VECTOR_FOLDER)
        self.myDrive.upload_or_update_vector_zip('upload_temp.zip')
        self.cleanup()
        del new_vector_store
        del final_vector_store
        del all_pages
        gc.collect()

    def search_query(self, query_text, k=2):
        intent = self.formatTheQuery(query_text)
        if "NEGATIVE" in intent:
            try:
                match = re.search(r'\d+', intent)
                
                if match:
                    index = int(match.group())
                    print(f"Parsed Index: {index}")
                    return self.handle_selection(index)
                    
            except Exception as e:
                print(f"Parsing Error: {e}")


        if not os.path.exists(LOCAL_VECTOR_FOLDER):
            drive_zip = self.myDrive.search_vector_zip()
            if drive_zip:
                self.myDrive.download_file(drive_zip['id'], VECTOR_ZIP_NAME)
                with zipfile.ZipFile(VECTOR_ZIP_NAME, 'r') as zip_ref:
                    zip_ref.extractall(LOCAL_VECTOR_FOLDER)
            else:
                return [] 

        vector_store = FAISS.load_local(
            LOCAL_VECTOR_FOLDER, 
            self.embedding_model,
            allow_dangerous_deserialization=True
        )
        results = vector_store.max_marginal_relevance_search(query_text, k=k, fetch_k=10)
        serializable_results = []
        for doc in results:
            serializable_results.append({
                "page_content": doc.page_content,
                "metadata": doc.metadata
            })
        with open(RESULT_JSON_FILE, 'w') as f:
            json.dump(serializable_results, f)
            
        return results

    def cleanup(self):
        try:
            print('f')
        except Exception: pass



#  if os.path.exists('upload_temp.zip'): os.remove('upload_temp.zip')
#             if os.path.exists(VECTOR_ZIP_NAME): os.remove(VECTOR_ZIP_NAME)
#             if os.path.exists(self.pdf_path_name): os.remove(self.pdf_path_name)
#             if hasattr(self, 'temp_filename') and os.path.exists(self.temp_filename): os.remove(self.temp_filename)
       