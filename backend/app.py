import os
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from sqlalchemy import create_engine
from dotenv import load_dotenv
import fitz
import logging
from sentence_transformers import SentenceTransformer, util
import google.generativeai as genai
from io import BytesIO

logging.basicConfig(level=logging.DEBUG)


# Initialize Flask application and CORS
app = Flask(__name__)
CORS(app)

# Load environment variables
load_dotenv()

# Constants for Supabase and LLM
DATABASE_URL = os.getenv('DATABASE_URL')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
API_KEY_GEMINI = os.getenv('API_TOKEN_GEMINI')

# Initialize Supabase client
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize SentenceTransformer model
model = SentenceTransformer('all-MiniLM-L6-v2')
# Function to extract text from PDF file
def extract_text_from_pdf(file_stream):
    try:
        doc = fitz.open(stream=file_stream, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        logging.error(f"Error extracting text from PDF: {e}")
        return ""

# Function to get embeddings of text using SentenceTransformer model
def get_embeddings(text):
    try:
        embeddings = model.encode(text, convert_to_tensor=True)
        return embeddings
    except Exception as e:
        logging.error(f"Error getting embeddings: {e}")
        return []

# Route for file upload
@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        # before saving the details in database table, first we'll truncate the table
        trunc = supabase_client.table('resumes').delete().neq("id", 0).execute()
        logging.debug(f"Truncated table: {trunc}") 
        data = request.json
        job_description = data.get('jobDesc')
        logging.debug(f"Received job description: {job_description}")
        job_description_embeddings = get_embeddings(job_description)
        # logging.debug(f"Computed embeddings for job description: {job_description_embeddings}")

        files = data.get('files', [])
        logging.debug(f"Received {len(files)} files")

        for file in files:
            file_content = base64.b64decode(file['content'])
            content = extract_text_from_pdf(BytesIO(file_content))
            logging.debug(f"Extracted text from PDF: {content}")

            if content:
                content_embeddings = get_embeddings(content)
                logging.debug(f"Computed embeddings for content: {content_embeddings}")

                score = util.cos_sim(job_description_embeddings, content_embeddings)
                logging.debug(f"Computed similarity score: {score}")

                # Save data to Supabase
                res = supabase_client.table('resumes').insert({
                    'resumetext': content, 
                    'score': score.item(), 
                    'embedding': content_embeddings.tolist()
                }).execute()
                logging.debug(f"Saved data to database: {res}")

            else:
                logging.warning("Empty content extracted from PDF")

        return jsonify({'status': 'success', 'message': 'Uploaded file(s) successfully'}), 200

    except Exception as e:
        logging.error(f"Error uploading file: {e}")
        return jsonify({'error': 'Failed to upload file'}), 500

# Route for generating response from prompt
@app.route('/api/prompt', methods=['POST'])
def prompt():
    try:
        data = request.json
        query = data.get('prompt')
        number = data.get('shortlistedCand')

        response = supabase_client.table('resumes').select('resumetext').order('score', desc=True).limit(number).execute()
        resume_content = [row['resumetext'] for row in response.data]

        # Fetch the content of the PDFs and pass it to the LLM
        all_pdf_texts = []
        for content in resume_content:
            # pdf_text = extract_text_from_pdf(url)
            all_pdf_texts.append(content)

        # Function to create input text for LLM
        def create_input_text(all_pdf_texts, query_text):
            input_text = "You are a hiring manager at a company. You have received multiple resumes for a job opening regarding the job description. Now you have to answer the Query with these documents i am giving to you:\n\n"
            input_text += f"Query:\n{query_text}\n"
            for i, pdf_text in enumerate(all_pdf_texts, 1):
                input_text += f"Document {i}:\n{pdf_text}\n\n"
            return input_text

        input_text = create_input_text(all_pdf_texts, query)

        # Function to get response from LLM
        def get_response_from_llm(input_text):
            genai.configure(api_key=API_KEY_GEMINI)
            model = genai.GenerativeModel('gemini-1.0-pro')
            output = model.generate_content(input_text)
            response = output.text
            return response

        final_response = get_response_from_llm(input_text)
        
        return jsonify({'response': final_response})
    
    except Exception as e:
        logging.error(f"An error occurred during prompt processing: {str(e)}")
        return jsonify({'error': 'Failed to process prompt'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
