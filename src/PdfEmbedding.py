import io
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
load_dotenv()
import numpy as np
import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
class PDFEmbed:
    def __init__(self,model_path,device,myDriveInst):
        self.embeddings = []
        self.model_path = model_path
        print("os.listdir(self.model_path)",os.listdir(self.model_path))
        self.emebdding_model = HuggingFaceEmbeddings(
            model_name=self.model_path,
            model_kwargs={'device':device},
            encode_kwargs={'normalize_embeddings':True}
        )
        self.vector_store_file_id=None
        self.myDrive = myDriveInst
        self.pdf_path_name=''
    def createEmbedding(self):
        pdf_loader = PyPDFLoader(self.pdf_path_name)
        pdf_docs = pdf_loader.load()
        pdf_10_pages = pdf_docs[:10]   
        splitter = RecursiveCharacterTextSplitter(chunk_size=100,chunk_overlap=20)
        chunks = splitter.split_documents(pdf_10_pages)
        self.vector_store = FAISS.from_documents(chunks,self.emebdding_model)
        if(self.vector_store_file_id!=None):
            filePresent = self.myDrive.get_specific_file(self.vector_store_file_id)
            if filePresent:
                self.myDrive.download_file(self.vector_store_file_id,'pdf_vector.npy')
                old_vector = FAISS.load_local('pdf_vector.npy')
                self.vector_store = FAISS.merge_from(old_vector,self.vector_store)
        FAISS.save_local('pdf_vector.npy')
        self.myDrive.upload_file('pdf_vector.npy')
    def create_pdf_from_buffer(self,pdf_buffer,pdf_file_name):
        buffer = io.BytesIO()
        buffer.write(pdf_buffer)
        buffer.seek(0)
        try:
            with open(pdf_file_name, 'wb') as f:
                f.write(buffer.getvalue())
            print(f"created pdf '{pdf_file_name}' from the buffer.")
            self.pdf_path_name = pdf_file_name
        except IOError as e:
            print(f"error in upload_pdf: {e}")
        finally:
            buffer.close()
        self.myDrive.upload_file(self.pdf_path_name)
   
    def search_query(self,query):
        pass
        
                
                
        
        



        



 