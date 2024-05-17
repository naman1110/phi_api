from collections import defaultdict
from flask import Flask, request, jsonify 
import os

from phi.assistant import Assistant
from phi.document import Document
from phi.document.reader.pdf import PDFReader
from phi.document.reader.website import WebsiteReader
from phi.utils.log import logger
from typing import List



from assistant import get_groq_assistant  
from cryptography.fernet import Fernet
import base64
import binascii
import urllib.parse
import shutil

app = Flask(__name__)
upload_folder = 'uploads'
os.makedirs(upload_folder, exist_ok=True)
ds=defaultdict(list)  
p_llm_model = "llama3-70b-8192"
p_embeddings_model = "text-embedding-3-large"
custom_key = 42 #"NetComLearning@PhiRagChatBot"


@app.route('/receive-file', methods=['POST'])
def receive_file():
    # Get Knowledge Base (KB) name from request parameter
    folder_name_param = request.form.get('kb_name')
    folder_name = folder_name_param
    if folder_name_param is None:
        folder_name = "General-Domain"
    
    # Create folder if it doesn't exist
    folder_path = os.path.join(upload_folder, folder_name)
    os.makedirs(folder_path, exist_ok=True)
    
    # Handle file uploads
    uploaded_files = request.files.getlist('file')
    rag_assistant = get_groq_assistant(llm_model=p_llm_model, embeddings_model=p_embeddings_model,user_id=folder_name) 
    for uploaded_file in uploaded_files:
        if uploaded_file.filename != '':
            file_path = os.path.join(folder_path, uploaded_file.filename)
            uploaded_file.save(file_path)
            process_file(file_path,rag_assistant,folder_name_param,uploaded_file.filename)  # Process the file directly for the knowledge base
    
    return jsonify({'message': 'Files uploaded successfully', 'kb_name': folder_name_param, 'kb_path':folder_path}),200


def process_file(filepath,rag_assistant,user_id,name):
    print("Processing and integrating file into knowledge base:", filepath)
    if rag_assistant.knowledge_base:
        with open(filepath, 'rb') as file:
                # pdf_file = io.BytesIO(file.read())
                reader = PDFReader(chunk_size=2900)
                # rag_name = name
                rag_documents: List[Document] = reader.read(filepath)
                if rag_documents:
                    rag_assistant.knowledge_base.load_documents(rag_documents, upsert=True,skip_existing=True)
                    logger.debug("PDF processed and loaded into the knowledge base")
                    ds[user_id].append(name)
                else:
                    logger.debug("Could not read PDF")

@app.route('/listKB', methods=['GET'])
def list_kb():
    key = request.args.get('key', default=None, type=str)
    if key is None or key not in ds:
        return "Key not found", 200
    # Access and return the data associated with the key
    return {'KB': ds[key]}


@app.route('/chat', methods=['POST'])
def rag_chat():  
    data = None
    user_prompt = None
    id=None

    if request.is_json:
          data = request.get_json()
          user_prompt = data.get('user_prompt')
          id=data.get('kb_name')

    rag_assistant = get_groq_assistant(llm_model=p_llm_model, embeddings_model=p_embeddings_model,user_id=id)
    rag_assistant_run_ids: List[str] = rag_assistant.storage.get_all_run_ids(user_id=id) 
    if not rag_assistant_run_ids:    
     run_id=rag_assistant.create_run()
    else: run_id=rag_assistant_run_ids[0]
    rag_assistant=get_groq_assistant(llm_model=p_llm_model, embeddings_model=p_embeddings_model,run_id=run_id,user_id=id)
     
    response=''
    
    for delta in rag_assistant.run(user_prompt):
                response += delta 
    
    
    logger.debug(f"run ids: {rag_assistant_run_ids}")
    return jsonify({"content": response,"kb_name":id}),200
    #return response

@app.route('/clear', methods=['POST'])
def clear_db():
    try:
         
        # Extract the 'user_prompt' from the JSON data
        data = request.get_json()
        id=data.get('kb_name')
        directory_path = upload_folder+"/"+id
        rag_assistant = get_groq_assistant(llm_model=p_llm_model, embeddings_model=p_embeddings_model,user_id=id)
        logger.info("Clearing KB : "+id)
        clear_status = rag_assistant.knowledge_base.vector_db.clear()
        if clear_status:
            try:
                shutil.rmtree(directory_path)
                logger.info(f"Directory '{directory_path}' deleted successfully.")
            except OSError as e:
                logger.info(f"Error deleting directory '{directory_path}': {e}")
        
        return jsonify({'message': 'Knowledge Base Cleared successfully.', 'kb_name': id,"kb_path":directory_path}),200
    except:
         return jsonify({'message': 'The Knowledge Base does not exists.', 'kb_name': id,"kb_path":directory_path}),404
         
    #return "Knowledge base cleared"
     






