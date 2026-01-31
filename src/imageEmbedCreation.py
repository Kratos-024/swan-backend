import io
import uuid
import numpy as np
from PIL import Image
from transformers import SiglipImageProcessor, SiglipModel, SiglipTokenizer, SiglipProcessor
import json
import os
import torch

class ImgEmbedder:
    def __init__(self, MODEL_FOLDER, myDrive, device):
        self.mydrive = myDrive
        self.device = device
        self.npy_filename = 'imageVector.npy'
        self.json_filename = 'image.json'
        self.npy_file_id = None
        self.json_file_id = None
        image_processor = SiglipImageProcessor.from_pretrained(MODEL_FOLDER, local_files_only=True)
        tokenizer = SiglipTokenizer.from_pretrained(MODEL_FOLDER, local_files_only=True)
        self.processor = SiglipProcessor(image_processor=image_processor, tokenizer=tokenizer)
        self.model = SiglipModel.from_pretrained(MODEL_FOLDER, local_files_only=True).to(self.device)
        self.model.eval()
        self.image_map = {}   
        self.embeddings = None 
        self.load_state()

    def load_state(self):
        found_json = self.mydrive.search_vector_img(self.json_filename)
        if found_json and 'id' in found_json:
            self.json_file_id = found_json['id']
            self.mydrive.download_file(self.json_file_id, self.json_filename)
            if os.path.exists(self.json_filename):
                with open(self.json_filename, "r") as f:
                    self.image_map = json.load(f)
        else:
            self.image_map = {}
        found_npy = self.mydrive.search_vector_img(self.npy_filename)
        if found_npy and 'id' in found_npy:
            self.npy_file_id = found_npy['id']
            self.mydrive.download_file(self.npy_file_id, self.npy_filename)
            if os.path.exists(self.npy_filename):
                self.embeddings = np.load(self.npy_filename)
        else:
            self.embeddings = None

    def save_state(self):
        with open(self.json_filename, "w") as f:
            json.dump(self.image_map, f)
        self.json_file_id = self.mydrive.upload_vector_img(self.json_filename)
        if self.embeddings is not None:
            np.save(self.npy_filename, self.embeddings)
            self.npy_file_id = self.mydrive.upload_vector_img(self.npy_filename)

    def add_image(self, img_binary):

        try:
            img = Image.open(io.BytesIO(img_binary)).convert('RGB')
            unique_name = f"{uuid.uuid4().hex}.png"
            img.save(unique_name, "PNG")
            image_drive_id = self.mydrive.upload_image(unique_name)
            
            if not image_drive_id:
                raise Exception("fail to get the id.")
            if os.path.exists(unique_name):
                os.remove(unique_name)

            inputs = self.processor(images=img, return_tensors="pt").to(self.device)
            with torch.no_grad():
                features = self.model.get_image_features(**inputs)
                if hasattr(features, "pooler_output"):
                    features = features.pooler_output
                elif hasattr(features, "image_embeds"):
                    features = features.image_embeds
                features = features / features.norm(p=2, dim=-1, keepdim=True)
                new_embedding = features.cpu().numpy()
            current_idx = len(self.image_map)
            self.image_map[str(current_idx)] = image_drive_id
            
            if self.embeddings is None:
                self.embeddings = new_embedding
            else:
                self.embeddings = np.vstack((self.embeddings, new_embedding))
            self.save_state()

        except Exception as e:
            print(f"Error adding image: {e}")

    def search_and_send(self, query, top_k=1):

        if self.embeddings is None or len(self.image_map) == 0:
            return {"reply": "Database is empty."}

        try:
            inputs = self.processor(text=[query], return_tensors="pt", padding="max_length", truncation=True).to(self.device)
            with torch.no_grad():
                text_feat = self.model.get_text_features(**inputs)
                if hasattr(text_feat, "pooler_output"):
                    text_feat = text_feat.pooler_output
                elif hasattr(text_feat, "text_embeds"):
                    text_feat = text_feat.text_embeds
                text_feat = text_feat / text_feat.norm(p=2, dim=-1, keepdim=True)
                text_vec = text_feat.cpu().numpy()
            scores = text_vec @ self.embeddings.T
            top_indices = scores[0].argsort()[-top_k:][::-1]

            results = []
            for idx in top_indices:
                idx_str = str(idx)
                if idx_str not in self.image_map:
                    continue
                file_id = self.image_map[idx_str]
                temp_dl_path = f"temp_{idx_str}.png"
                try:
                    self.mydrive.download_file(file_id, temp_dl_path)
                    if os.path.exists(temp_dl_path):
                        with open(temp_dl_path, "rb") as f:
                            results.append(f.read())
                        os.remove(temp_dl_path)
                except Exception as dl_error:
                    print(f"Failed to download image {file_id}: {dl_error}")
            return results
        except Exception as e:
            print(f"Error in search: {e}")
            return []