import base64
import io
import  torch,  os, matplotlib.pyplot as plt
from PIL import Image
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm
from transformers import SiglipImageProcessor,SiglipModel, SiglipTokenizer, SiglipProcessor
import torch
import numpy as np
device = "cuda" if torch.cuda.is_available() else "cpu"

class CifarDataset(Dataset):
    def __init__(self, pil_images, processor):
        self.images = pil_images
        self.processor = processor

    def __getitem__(self, index):
        image = self.images[index]
        pixel_values = self.processor(images=image, return_tensors="pt")["pixel_values"]
        print(pixel_values.shape)
        return index, pixel_values.squeeze(0)

    def __len__(self):
        return len(self.images)
    



class ImgEmbedder:
    def __init__(self,MODEL_FOLDER):

        image_processor = SiglipImageProcessor.from_pretrained(MODEL_FOLDER, local_files_only=True)
        tokenizer = SiglipTokenizer.from_pretrained(MODEL_FOLDER, local_files_only=True)
        self.processor = SiglipProcessor(image_processor=image_processor, tokenizer=tokenizer)
        self.model = SiglipModel.from_pretrained(MODEL_FOLDER, local_files_only=True).to(device)
        self.PILprocessed_imgs = []
        self.model.eval()
    def ProcessedImg(self, img_list):
            new_images = []
            for img in img_list:
                img_bytes = bytes(img)
                img = Image.open(io.BytesIO(img_bytes))
                img = img.resize((300, 200), Image.BICUBIC).convert('RGB')
                
                self.PILprocessed_imgs.append(img) 
                new_images.append(img)             

            ImgDataset = CifarDataset(new_images, self.processor)
            self.ImgDataloader = DataLoader(ImgDataset, batch_size=1, shuffle=False)

    def createEmmbedding(self):
        all_embeddings = []

        with torch.no_grad():
            for indices, img_pixels in tqdm(self.ImgDataloader,desc='Processing Images'):
                print(img_pixels.shape)
                img_pixels = img_pixels.to(device)

                features = self.model.get_image_features(pixel_values=img_pixels)
                if hasattr(features, "pooler_output"):
                    features = features.pooler_output
                elif hasattr(features, "image_embeds"):
                    features = features.image_embeds
                else:
                    features = features
                features /= features.norm(p=2, dim=-1, keepdim=True)

                all_embeddings.append(features.cpu())
        index_matrix = torch.cat(all_embeddings).numpy()
        if  (os.path.exists('vector_data.npy')) :
             print('load old')
             new_index_matrix=np.load('vector_data.npy')
             index_matrix = np.vstack((new_index_matrix,index_matrix))
             np.save('vector_data.npy',index_matrix)
        else:
            print('saved new')
            np.save('vector_data.npy',index_matrix)


       
    def search_and_send(self,query, top_k=1):
        try:
      
            inputs = self.processor(text=[query], return_tensors="pt", padding="max_length").to(device)
            with torch.no_grad():
                text_feat = self.model.get_text_features(**inputs)
                text_feat = text_feat.pooler_output
                text_feat /= text_feat.norm(p=2, dim=-1, keepdim=True)
            index_matrix=np.load('vector_data.npy')

            scores = (text_feat.cpu().numpy() @ index_matrix.T)
            top_indices = scores[0].argsort()[-top_k:][::-1]
       
            binary_data=[]
            for i, idx in enumerate(top_indices):
                img = self.PILprocessed_imgs[idx]
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")  
                image_bytes = buffered.getvalue()
                binary_data.append(image_bytes)
            return binary_data
        except Exception as e:
            print(e)
    

                        





