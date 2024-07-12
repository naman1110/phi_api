from collections import defaultdict
from flask import Flask, request, jsonify 
import os
from flask_cors import CORS
from delete import *
import time 
from phi.document import Document
from phi.document.reader.pdf import PDFReader,PDFUrlReader
from phi.document.reader.website import WebsiteReader
# from url import WebsiteReader
from phi.document.reader.docx import DocxReader
from phi.document.reader.json import JSONReader
from phi.document.reader.text import TextReader
from pathlib import Path
from phi.utils.log import logger
from typing import List,Optional,Dict,Callable
import logging
from logging.handlers import RotatingFileHandler



from assistant import get_groq_assistant ,get_openai_assistant 

import shutil
user_model_mapping = {}

app = Flask(__name__)
upload_folder = 'uploads'
os.makedirs(upload_folder, exist_ok=True)
ds=defaultdict(list)  
p_embeddings_model = "text-embedding-3-large"
default_assistant_processor = get_groq_assistant
default_llm_model = "llama3-70b-8192"
custom_key = 42 #"NetComLearning@PhiRagChatBot"
CORS(app) 

logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')
handler = RotatingFileHandler('app.log', maxBytes=2*1024*1024, backupCount=10)
handler.setLevel(logging.INFO)
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s:%(message)s'))

app.logger.addHandler(handler)


@app.route('/select-model', methods=['POST'])
def select_model():
    if request.is_json:
        data = request.get_json()
        user_id = data.get('kb_name')
        model_id = data.get('llm')
        selected_model = data.get('model')
        
        file_processors = {
            'groq': get_groq_assistant,
            'openai': get_openai_assistant
        }

        if not user_id:
            return jsonify("Missing user ID"), 400

        # Use default values if model information is not provided
        if not model_id or not selected_model:
            model_id = 'groq'
            selected_model = default_llm_model

        assistant_processor = file_processors.get(model_id, default_assistant_processor)

        # Store the selected model for the specific user
        user_model_mapping[user_id] = {
            'llm_model': selected_model,
            'assistant_processor': assistant_processor
        }

        return jsonify("Successfully selected the model"), 200
    return jsonify("Invalid request"), 400


     


@app.route('/receive-file', methods=['POST'])
def receive_file():
    
    # Get Knowledge Base (KB) name from request parameter
    folder_name_param = request.form.get('kb_name')
    folder_name = folder_name_param
    if folder_name_param is None:
        folder_name = "General-Domain"
    
    # Create folder if it doesn't exist
   
    
    user_context = user_model_mapping.get(folder_name_param , {
            'llm_model': default_llm_model,
            'assistant_processor': default_assistant_processor
        })

    llm_model = user_context['llm_model']
    assistant_processor = user_context['assistant_processor']
    
    rag_assistant = assistant_processor(llm_model=llm_model, embeddings_model=p_embeddings_model,user_id=folder_name_param)
    
    
    # Handle file uploads
    if 'file' in request.files:
        uploaded_files = request.files.getlist('file')
        # rag_assistant = get_groq_assistant(llm_model=p_llm_model, embeddings_model=p_embeddings_model,user_id=folder_name_param)
        for uploaded_file in uploaded_files:
            if uploaded_file.filename != '':
                
               
                process_file(uploaded_file,rag_assistant,folder_name_param,uploaded_file.filename)  # Process the file directly for the knowledge base
 
            else: logging.error(f"Error in processing file ")
 
    elif 'url' in request.form:
        url = request.form['url']        
        process_url(rag_assistant, url)
        
    return jsonify({'message': 'Files uploaded successfully', 'kb_name': folder_name_param}),200


def process_file(file_path,rag_assistant,user_id,file_name):
    print("Processing and integrating file into knowledge base:", file_path)
    
    # check file type ans 
    
    file_extension = os.path.splitext(file_name)[-1].lower()
    file_processors = {
        '.pdf': process_file_pdf,
        '.docx': process_file_docx,
        '.json': process_file_json,
        '.txt': process_file_text,
    }
    
    processor = file_processors.get(file_extension)
    if processor:
        processor(file_path,rag_assistant, user_id,file_name)
    else:
        logging.error(f"No handler for file type: {file_extension}")
        return jsonify({'message': 'Unsupported filetype. Please upload a valid file.'}),400

def process_file_pdf(uploaded_file,rag_assistant,user_id,name):

    print("inside process_file_pdf")
    
 
    if rag_assistant :
                file_path = os.path.join("uploads", name) 
                uploaded_file.save(file_path)
    
                
                reader = PDFReader(chunk_size=2048)
                rag_documents: List[Document] = reader.read(file_path)
                if rag_documents:
                    rag_assistant.knowledge_base.load_documents(rag_documents, upsert=True)
                    logging.info("PDF processed and loaded into the knowledge base")
                    ds[user_id].append(name)
                else:
                    logging.error("Could not read PDF in process_file")
                os.remove(file_path)

def process_file_docx(uploaded_file, rag_assistant,user_id,name):
   
   if rag_assistant :
        
        
                file_path = os.path.join("uploads", name) 
                uploaded_file.save(file_path)
                reade = DocxReader(chunk_size=2048)
                path_obj = Path(file_path)
                rag_document = reade.read(path_obj)
                if rag_document:
                    rag_assistant.knowledge_base.load_documents(rag_document, upsert=True)
                    logging.info("DOCX file processed and loaded into the knowledge base")
                else:
                    logging.error("Could not read DOCX file")
                os.remove(file_path)
 
 
def process_file_json(uploaded_file, rag_assistant,user_id,name):
   print("inside process_file_json")
   if rag_assistant :
                file_path = os.path.join("uploads", name) 
                uploaded_file.save(file_path)
                reade = JSONReader(chunk_size=1024)
                path_obj = Path(file_path)
                rag_document = reade.read(path_obj)
                if rag_document:
                    rag_assistant.knowledge_base.load_documents(rag_document, upsert=True)
                    logging.info("JSON file processed and loaded into the knowledge base")
                else:
                    logging.error("Could not read JSON file")
                os.remove(file_path)

def process_file_text(uploaded_file, rag_assistant,user_id,name):
   print("inside process_file_text")
   if rag_assistant :
                file_path = os.path.join("uploads",name) 
                uploaded_file.save(file_path)
                reade = TextReader(chunk_size=1024)
                path_obj = Path(file_path)
                rag_document = reade.read(path_obj)
                if rag_document:
                    rag_assistant.knowledge_base.load_documents(rag_document, upsert=True)
                    logging.info("TEXT file processed and loaded into the knowledge base")
                else:
                    logging.error("Could not read TEXT file")
                os.remove(file_path)


def process_url( rag_assistant, input_url):
     if rag_assistant :
        scraper = WebsiteReader()
        web_documents = scraper.read(input_url)
        
       
        if web_documents:
            rag_assistant.knowledge_base.load_documents(web_documents, upsert=True)
            logging.info("URL processed and content loaded into the knowledge base")
        else:
            logging.error("Could not process URL")    



@app.route('/chat', methods=['POST'])
def rag_chat():
    if request.is_json:
        data = request.get_json()
        user_prompt = data.get('user_prompt')
        user_id = data.get('kb_name')
        
        user_context = user_model_mapping.get(user_id, {
            'llm_model': default_llm_model,
            'assistant_processor': default_assistant_processor
        })

        llm_model = user_context['llm_model']
        assistant_processor = user_context['assistant_processor']
        
   
        try:
            
            rag_assistant = assistant_processor(llm_model=llm_model, embeddings_model=p_embeddings_model, user_id=user_id)
            
            rag_assistant_run_ids = rag_assistant.storage.get_all_run_ids(user_id=user_id) 
            
            if not rag_assistant_run_ids:
                run_id = rag_assistant.create_run()
            else:
                run_id = rag_assistant_run_ids[0]
           
            rag_assistant = assistant_processor(llm_model=llm_model, embeddings_model=p_embeddings_model, run_id=run_id, user_id=user_id)
            
            
            response = ''
            for delta in rag_assistant.run(user_prompt):
                response += delta
            
            
            
            logging.info(f"Run IDs: {rag_assistant_run_ids} for user ID: {rag_assistant.user_id}")
            return jsonify({"content": response, "kb_name": user_id}), 200
        
        except Exception as e:
            logging.error(f"Error processing chat: {str(e)}")
            return jsonify("Error processing request"), 500
    return jsonify("Invalid request"), 400

@app.route('/delete', methods=['POST'])
def file_delete():
    
    if request.is_json:
     data = request.get_json()
    kb_name=data.get('kb_name')
    name=data.get('file_name')
    return delete_rows_by_name(kb_name,name)

@app.route('/clear', methods=['POST'])
def clear_db():
    global p_llm_model, assistant_processor
    try:
         
        # Extract the 'user_prompt' from the JSON data
        data = request.get_json()
        id=data.get('kb_name')

        rag_assistant = assistant_processor(llm_model=p_llm_model, embeddings_model=p_embeddings_model,user_id=id)
        logging.info("Clearing KB : "+id)
        rag_assistant.knowledge_base.vector_db.clear()
     
        return jsonify({'message': 'Knowledge Base Cleared successfully.', 'kb_name': id}),200
    except:
         return jsonify({'message': 'The Knowledge Base does not exists.', 'kb_name': id}),404
         
    #return "Knowledge base cleared"

@app.route('/status', methods=['GET'])
def status_check():
    logging.info('Status check called')
    return jsonify({'status': 'API is up'}), 200
     


