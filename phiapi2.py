from collections import defaultdict
from flask import Flask, request, jsonify 
import os
from flask_cors import CORS
import re
import requests
from phi.document import Document
from phi.document.reader.pdf import PDFReader,PDFUrlReader
from phi.document.reader.website import WebsiteReader
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

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 60 * 1024 * 1024  # 60 MB
upload_folder = 'uploads'
os.makedirs(upload_folder, exist_ok=True)
ds=defaultdict(list)  
p_llm_model: Optional[str] = "llama3-70b-8192"
p_embeddings_model = "text-embedding-3-large"
assistant_processor: Optional[Callable] =get_groq_assistant
custom_key = 42 #"NetComLearning@PhiRagChatBot"
CORS(app) 

logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')
handler = RotatingFileHandler('app.log', maxBytes=2*1024*1024, backupCount=10)
handler.setLevel(logging.INFO)
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s:%(message)s'))

app.logger.addHandler(handler)


@app.route('/select-model', methods=['POST'])
def model():
    global p_llm_model, assistant_processor
    if request.is_json:
     data = request.get_json()
    model_id=data.get('llm')
    p_llm_model=data.get('model')
    
    file_processors: Dict[str, Callable] = {
            'groq': get_groq_assistant,
            'openai': get_openai_assistant
            }

    if not model_id or not p_llm_model:
        return jsonify("Missing necessary model information"), 400

    assistant_processor = file_processors.get(model_id)
    if not assistant_processor:
        return jsonify("Invalid model ID"), 400

    return jsonify("Successfully selected the model"), 200
     


@app.route('/receive-file', methods=['POST'])
def receive_file():
    global p_llm_model, assistant_processor
    # Get Knowledge Base (KB) name from request parameter
    folder_name_param = request.form.get('kb_name')
    folder_name = folder_name_param
    if folder_name_param is None:
        folder_name = "General-Domain"
    
    # Create folder if it doesn't exist
    folder_path = os.path.join(upload_folder, folder_name)
    os.makedirs(folder_path, exist_ok=True)
    
    rag_assistant = assistant_processor(llm_model=p_llm_model, embeddings_model=p_embeddings_model,user_id=folder_name_param)
    
    # Handle file uploads
    if 'file' in request.files:
        uploaded_files = request.files.getlist('file')
        # rag_assistant = get_groq_assistant(llm_model=p_llm_model, embeddings_model=p_embeddings_model,user_id=folder_name_param)
        for uploaded_file in uploaded_files:
            if uploaded_file.filename != '':
                file_path = os.path.join(folder_path, uploaded_file.filename)
                uploaded_file.save(file_path)
                process_file(file_path,rag_assistant,folder_name_param,uploaded_file.filename)  # Process the file directly for the knowledge base
 
            else: logging.error(f"Error in processing file ")
 
    elif 'url' in request.form:
        url = request.form['url']        
        process_url(folder_path, rag_assistant, url)
        
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

def process_file_pdf(file_path,rag_assistant,user_id,name):

    print("inside process_file_pdf")
    
 
    if rag_assistant :
    
        with open(file_path, 'rb') as file:
                reader = PDFReader(chunk_size=2048)
                rag_documents: List[Document] = reader.read(file_path)
                if rag_documents:
                    rag_assistant.knowledge_base.load_documents(rag_documents, upsert=True)
                    logging.info("PDF processed and loaded into the knowledge base")
                    ds[user_id].append(name)
                else:
                    logging.error("Could not read PDF in process_file")
 
def process_file_docx(file_path, rag_assistant,user_id,name):
   print("inside process_file_docx")
   if rag_assistant :
        with open(file_path, 'rb') as file:
        
        
                print("inside process_file_docx")
                reade = DocxReader(chunk_size=2048)
                path_obj = Path(file_path)
                rag_document = reade.read(path_obj)
                if rag_document:
                    rag_assistant.knowledge_base.load_documents(rag_document, upsert=True)
                    logging.info("DOCX file processed and loaded into the knowledge base")
                else:
                    logging.error("Could not read DOCX file")
 
 
def process_file_json(file_path, rag_assistant,user_id,name):
   print("inside process_file_json")
   if rag_assistant :
        with open(file_path, 'rb') as file:
        
                print("inside process_file_json")
                reade = JSONReader(chunk_size=1024)
                path_obj = Path(file_path)
                rag_document = reade.read(path_obj)
                if rag_document:
                    rag_assistant.knowledge_base.load_documents(rag_document, upsert=True)
                    logging.info("JSON file processed and loaded into the knowledge base")
                else:
                    logging.error("Could not read JSON file")

def process_file_text(file_path, rag_assistant,user_id,name):
   print("inside process_file_text")
   if rag_assistant :
        with open(file_path, 'rb') as file:
        
        
                print("inside process_file_docx")
                reade = TextReader(chunk_size=1024)
                path_obj = Path(file_path)
                rag_document = reade.read(path_obj)
                if rag_document:
                    rag_assistant.knowledge_base.load_documents(rag_document, upsert=True)
                    logging.info("TEXT file processed and loaded into the knowledge base")
                else:
                    logging.error("Could not read TEXT file")




def process_url(file_path, rag_assistant, input_url):
     if rag_assistant :
        scraper = WebsiteReader(max_links=2, max_depth=1)
        web_documents = scraper.read(input_url)
        print(web_documents)
        save_text_to_folder(web_documents, file_path, str(input_url))
        if web_documents:
            rag_assistant.knowledge_base.load_documents(web_documents, upsert=True)
            logging.info("URL processed and content loaded into the knowledge base")
        else:
            logging.error("Could not process URL")    

def save_text_to_folder(text, folder_path, file_name):
    # Check if the folder exists, if not, create it
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    

    # Remove special characters from the URL
    file_name = re.sub(r'[./\\:"\']', '', file_name)
    # Write text to a file in the specified folder
    file_path = os.path.join(folder_path, file_name)
    with open(file_path, 'w') as file:
        file.write(str(text))
    
    print("Text saved to folder successfully.")

@app.route('/listKB', methods=['GET'])
def list_kb():
    if request.is_json:
      data = request.get_json()
      id=data.get('kb_name')
      directory_path = upload_folder+"/"+id
      files = list_files_in_folder(directory_path)
      if files:
          return jsonify({"kb_list": files, "kb_name":id}),200
      else:
          return jsonify({"kb_list": files, "kb_name":id,'message': 'The Knowledge Base does not exists.'}),200
    else:
         return jsonify({"error": "Missing parameters in request"}), 400
         
  
 
def list_files_in_folder(folder_path):
    file_list = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            print(file)
            file_list.append(file)
    return file_list

@app.route('/chat', methods=['POST'])
def rag_chat():  
    global p_llm_model, assistant_processor
    data = None
    user_prompt = None
    id=None

    if request.is_json:
          data = request.get_json()
          user_prompt = data.get('user_prompt')
          id=data.get('kb_name')
    print(assistant_processor,p_llm_model)
    try:
        rag_assistant = assistant_processor(llm_model=p_llm_model, embeddings_model=p_embeddings_model,user_id=id)
        rag_assistant_run_ids: List[str] = rag_assistant.storage.get_all_run_ids(user_id=id) 
        if not rag_assistant_run_ids:    
           run_id=rag_assistant.create_run()
        else: run_id=rag_assistant_run_ids[0]
        rag_assistant=assistant_processor(llm_model=p_llm_model, embeddings_model=p_embeddings_model,run_id=run_id,user_id=id)
        
        response=''
        
        for delta in rag_assistant.run(user_prompt):
                    response += delta 
        # r = requests.post("https://api.apispreadsheets.com/data/44QkCUAfiN14wsvh/", headers={}, json={"data": {"Prompt":user_prompt,"phidata":response}})
        # if r.status_code == 201:
        #     # SUCCESS 
        #     print('Sucess on xlsx')
        #     pass
        # else:
        #     # ERROR
        #     print('error on xlsx')
        #     pass
        
        logging.info(f"run ids: {rag_assistant_run_ids} for user id:{rag_assistant.user_id}")
        return jsonify({"content": response,"kb_name":id}),200
        #return response
    except Exception as e:
        logging.error(f"Error processing chat: {str(e)}")
        return jsonify("Error processing request"), 500

@app.route('/get_file_contents', methods=['GET'])
def get_file_contents():
    if request.is_json:
      data = request.get_json()
      id=data.get('kb_name')
      if id is None:
          return "KB name not found", 404
     
      filename=data.get('kb_file_name')
      if filename is None:
          return "File name not found", 404
 
      directory_path = upload_folder+"/"+id
      file_path = os.path.join(directory_path, filename)
      if os.path.exists(file_path):
        with open(file_path, 'rb') as file:
            file_contents = file.read()
        return jsonify({"kb_name":id,'kb_file_name': filename, 'contents': str(file_contents)})
      else:
        return "File not found", 404

@app.route('/clear', methods=['POST'])
def clear_db():
    global p_llm_model, assistant_processor
    try:
         
        # Extract the 'user_prompt' from the JSON data
        data = request.get_json()
        id=data.get('kb_name')
        directory_path = upload_folder+"/"+id
        rag_assistant = assistant_processor(llm_model=p_llm_model, embeddings_model=p_embeddings_model,user_id=id)
        logging.info("Clearing KB : "+id)
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

@app.route('/status', methods=['GET'])
def status_check():
    logging.info('Status check called')
    return jsonify({'status': 'API is up'}), 200
     








if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=9000)
