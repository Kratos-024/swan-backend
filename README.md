# swan-backend

A FastAPI backend that provides:
- LLM-powered chat (via HuggingFace endpoints)
- PDF ingestion and semantic indexing (FAISS vector store)
- Image embedding and search (SigLIP-based embeddings)
- Google Drive integration for storing models, vectors, and files
- Persistent workflow checkpointing using a PostgreSQL-backed checkpointer

This README explains how to set up, run, and use the API endpoints.

---

## Quick facts / features
- REST API served with FastAPI (src/app.py)
- Chat logic and workflow via LangGraph + HuggingFace (src/ChatController.py)
- PDF ingestion, embedding, and search handled in src/PdfEmbedding.py (FAISS)
- Image embedding and nearest-neighbor search in src/imageEmbedCreation.py (SigLIP model)
- Google Drive integration for storing/retrieving models, vector archives and images (src/GoogleDrive.py)
- Persistent memory/checkpointing in PostgreSQL via langgraph/checkpoint (src/PersistentMem.py)

---

## Quick start

Important: The project uses plain module-level imports (e.g., `from ChatController import ...`) inside the `src` folder. To avoid import errors, run the server from the `src` directory.

From the repository root run:
```bash
cd src
uvicorn app:app --reload
```

Or to bind to all interfaces (e.g., for local network testing) and set the port:
```bash
cd src
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

---

## Requirements

- Python 3.10+ recommended (check your environment)
- GPU recommended for model inference but CPU is supported (app detects `cuda` automatically)
- Install Python dependencies:

```bash
pip install -r requirements.txt
```

(Requirements are listed in `requirements.txt`. Some packages require native dependencies, e.g. torch, pdf2image, poppler for pdf->image conversion.)

---

## Important environment variables

Copy `.sample.env` -> `.env` and populate:

- GOOGLE_API_KEY= (optional)
- GOOGLE_APPLICATION_CREDENTIALS='' (optional; project/service-account credentials file path)
- HUGGINGFACEHUB_API_TOKEN= (token for HuggingFace endpoints if required)
- POSTGRES_URI= (Postgres connection string used by the persistent checkpointer)

.env example (based on `.sample.env`):
```
GOOGLE_API_KEY=
GOOGLE_APPLICATION_CREDENTIALS=''
HUGGINGFACEHUB_API_TOKEN=
POSTGRES_URI=
```

Notes:
- The repo expects a `credentials.json` file (OAuth client secrets) at `../credentials.json` relative to `src/` (see GoogleDrive.cred_path). Place your OAuth client secrets at the repository root as `credentials.json`.
- The Google OAuth token will be stored in `../google_token.json` (relative to `src/`), i.e., repository root.
- If you use a service account or different file layout, update `DriveAPI` paths in `src/GoogleDrive.py`.

---

## Files & where to look

- src/app.py — FastAPI application & endpoints.
- src/ChatController.py — Chat workflow and HuggingFace chat integration.
- src/PdfEmbedding.py — PDF processing, embedding creation, merging with existing FAISS store, and search logic.
- src/imageEmbedCreation.py — Image vector creation, storage, and search utilities.
- src/GoogleDrive.py — Google Drive OAuth, upload/download, model downloading logic.
- src/PersistentMem.py — Postgres-based checkpointer setup for LangGraph workflows.

---

## Google Drive and model downloads

- The application uses Google Drive to:
  - Store image metadata and image vectors (image.json, imageVector.npy) under a Drive folder (created by the app).
  - Upload vector store ZIPs for PDFs (pdf_vectors_archive.zip).
  - Download prepacked model folders via shared Google Drive links (see DriveAPI.download_models).
- Place your OAuth client credentials file at: `credentials.json` at the repository root (so `src/` sees it as `../credentials.json`).
- When the app starts, if no valid token exists, it will print an auth URL. Visit that URL and complete the OAuth consent; the app provides an `/oauth2callback` endpoint to accept the returned code.

---

## Running locally

Important: the code uses plain imports like `from ChatController import ...` inside `src/app.py`. For predictable behavior, run uvicorn from the `src` folder:

1. Cd into src:
```bash
cd src
```

2. Run the server (minimum command):
```bash
uvicorn app:app --reload
```

Recommended example (bind to all interfaces and set port):
```bash
cd src
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

When the server starts it will:
- Initialize DriveAPI and attempt to authenticate with saved token; if not available, it will create an auth URL.
- Attempt to download models into `../pdf_embeder-bge-base` and `../siglip_model` using hard-coded Drive folder links (see DriveAPI.download_models). Ensure gdown has network access and the links are accessible.

If you prefer running from repository root, ensure Python import resolution works in your environment (adjust sys.path or use a package layout).

---

## OAuth / Authentication flow

1. Ensure `credentials.json` (OAuth client secrets) is placed at repository root.
2. Start server (see above).
3. If DriveAPI needs auth, app prints an authorization URL (and the `/` endpoint shows server running).
4. Visit the printed URL in your browser, complete consent. The redirect should point to the server's `/oauth2callback` endpoint:
   - Default redirect is `http://127.0.0.1:8000/oauth2callback`
   - If you run in production behind a public URL, ensure `PROD` and `PROD_URL` env vars are set to adjust the redirect URI logic in `GoogleDrive.py`.
5. The server stores the OAuth token at `../google_token.json`.

---

## API Reference (endpoints)

Base URL (local): http://127.0.0.1:8000

- GET /
  - Simple health check
  - Response: `{"response": "Server is running"}`

- GET /oauth2callback
  - Used by Google OAuth redirect to pass auth code.
  - Example: visit the authorization URL and Google will redirect here with `?code=...`.

- POST /chat
  - Chat with the LLM-backed assistant.
  - Request JSON:
    ```json
    {
      "message": "Hello, how are you?",
      "thread_id": "optional-thread-id"
    }
    ```
  - Response:
    ```json
    { "reply": "Assistant response text..." }
    ```

- POST /chat-img
  - Search images by a text query and return the top match as base64 image bytes.
  - Request JSON:
    ```json
    { "img_query": "sunset painting" }
    ```
  - Response (on success):
    ```json
    { "imageResponse": "<base64-png-data>" }
    ```
  - If Drive is not authenticated, returns authorization info.

- POST /create-embed-img
  - Add an image (byte buffer) to the image embedding database.
  - Request JSON shape:
    ```json
    {
      "buffer": {
        "data": [ /* array of ints representing image bytes */ ]
      }
    }
    ```
  - Example note: easiest is to send with Python `requests` by reading bytes and converting to a list (example below).
  - Response:
    ```json
    { "reply": "Embeddings created" }
    ```

- POST /send-pdfbuffer
  - Upload a PDF (as a byte buffer), store on Drive, and kick off embedding creation.
  - Request JSON:
    ```json
    {
      "buffer": {
        "data": [ /* PDF bytes as int list */ ]
      },
      "pdf_name": "my_doc.pdf"
    }
    ```
  - The server will:
    - Write file locally, upload to Drive via `DriveAPI.upload_pdf_file`
    - Create embedding summary and merge with vector archive
    - Upload updated vector archive to Drive
  - Response:
    ```json
    { "reply": "PDF metadata indexed successfully" }
    ```

- POST /search_pdf_query
  - Search the indexed PDFs.
  - Request JSON:
    ```json
    { "Pdf_query": "notes on linear algebra" }
    ```
  - Response:
    - If the query is a selection (like "first one"), the endpoint may return the PDF bytes encoded in base64:
      ```json
      { "reply": [ ...search results... ] }
      ```
    - Or:
      ```json
      { "reply": [ { "File_Name": "...", "date": "...", "total_pages": N, "cover_buffer": "<base64-or-null>" }, ... ] }
      ```

---

## Example usage

Python helper to send a chat message:

```python
import requests
url = "http://127.0.0.1:8000/chat"
payload = {"message": "What is the capital of France?", "thread_id": None}
r = requests.post(url, json=payload)
print(r.json())
```

Send a PDF buffer (Python):
```python
import requests

def send_pdf(path, name):
    with open(path, "rb") as f:
        b = list(f.read())
    payload = {"buffer": {"data": b}, "pdf_name": name}
    r = requests.post("http://127.0.0.1:8000/send-pdfbuffer", json=payload, timeout=120)
    print(r.json())

# Example
send_pdf("example.pdf", "example.pdf")
```

Create image embedding (Python):
```python
import requests

def create_img_embedding(path):
    with open(path, "rb") as f:
        b = list(f.read())
    payload = {"buffer": {"data": b}}
    r = requests.post("http://127.0.0.1:8000/create-embed-img", json=payload)
    print(r.json())

create_img_embedding("photo.png")
```

Search image by text (curl):
```bash
curl -X POST "http://127.0.0.1:8000/chat-img" -H "Content-Type: application/json" \
  -d '{"img_query": "a red car"}'
# The response returns base64 encoded PNG bytes in imageResponse
```

Search PDFs:
```bash
curl -X POST "http://127.0.0.1:8000/search_pdf_query" -H "Content-Type: application/json" \
  -d '{"Pdf_query": "machine learning notes"}'
```

If the search result is a selection (e.g. user selects "first one"), the app may return base64 PDF bytes as `pdfBytes` and `pdf_name`.

---

## Model and data storage notes

- Models are downloaded by `DriveAPI.download_models()` into parent directories:
  - `../pdf_embeder-bge-base`
  - `../siglip_model`
- PDF vector local folder used for FAISS store: `pdf_vectors_store`
- The FAISS store is zipped as `pdf_vectors_archive.zip` and uploaded to a Drive folder called `PdfVectors` (created automatically)
- Image state files: `image.json` (mapping) and `imageVector.npy` (numpy embeddings) — uploaded to Drive under `ImgVectors`

---

## Troubleshooting tips

- If imports fail, ensure you are running uvicorn from `src/`:
  - cd src && uvicorn app:app --reload
- If the app prints an auth URL but you get errors when exchanging the code:
  - Confirm `credentials.json` exists at repo root and OAuth client has the redirect URI set to `http://127.0.0.1:8000/oauth2callback` (or set `PROD` and `PROD_URL` env vars)
- Drive credentials:
  - The token is stored at `google_token.json` (in the repository root when running from `src/`)
  - If tokens expire, the app attempts to refresh them automatically, but you may need to re-authorize
- If models fail to load:
  - Ensure `gdown` can access the shared folder links and that the machine has network access
  - Manual alternative: place your model folders at `../pdf_embeder-bge-base` and `../siglip_model`
- For PDF->image conversion (cover extraction) you may need poppler (pdf2image dependency)
- Database: make sure POSTGRES_URI points to a reachable Postgres instance. The code uses `psycopg[binary]` and `psycopg_pool` — check Postgres version compatibility.

---

## Development & contribution

- Keep the import assumptions in mind (module-level imports expect to be able to import ChatController, PdfEmbedding, etc.).
- If converting to a package layout, add `__init__.py` files and adjust imports for clarity.
- For debugging, add log statements or run components interactively (the repo also includes sample notebooks under `src/`).

---

## Security & privacy

- Do not commit `credentials.json` or `google_token.json` to the repository.
- Keep API tokens (HuggingFace, Google API keys, DB credentials) in environment variables or a safe secret store.

---

## License

No license file is included. Add a LICENSE if you intend to publish with a specific license.

---

If you want, I can:
- Add concrete curl + Python examples that show converting binary files to the required JSON payload format in one place.
- Provide a small script to perform the first OAuth flow automatically and save the token.
- Turn `src/` into a proper Python package for more robust imports and cleaner run instructions.
