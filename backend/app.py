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
import numpy as np
import json

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
    
# Function to create input text for LLM
def create_input_text(all_pdf_texts, number, query_text):
    input_text = "You are a hiring manager at a company. You have received multiple resumes for a job opening regarding the job description. Now you have to answer the Query with these documents i am giving to you:\n\n"
    input_text += f"Query:\n{query_text}\n"
    input_text += f"Number of candiadtes you have to output:\n{number}\n"
    for i, pdf_text in enumerate(all_pdf_texts, 1):
        input_text += f"Document {i}:\n{pdf_text}\n\n"
    return input_text

# Function to get response from LLM
def get_response_from_llm(input_text):
    genai.configure(api_key=API_KEY_GEMINI)
    model = genai.GenerativeModel('gemini-1.0-pro')
    output = model.generate_content(input_text)
    response = output.text
    return response


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
        logging.debug(f"query: {query} and shortlisted candidate: {number}")

        # Fetch top 100 resumes and their embeddings
        # Fetch top 100 resumes and their embeddings
        response = supabase_client.table('resumes').select('resumetext', 'embedding').order('score', desc=True).limit(100).execute()

        # Check if the response has data
        if response.data:
            # Extract resume content and embeddings
            resume_content = [row['resumetext'] for row in response.data]
            top_n_embeddings = [row['embedding'] for row in response.data]

            # logging.debug(f"resume content: {resume_content}")
        else:
            logging.error("No data found in the response.")

        top_n_embeddings_list = [json.loads(embedding) for embedding in top_n_embeddings]


        # Calculate similarities and retrieve top N resumes
        query_embedding = get_embeddings(query).tolist()
        # logging.debug(f"Query embedding shape: {query_embedding}")

        # Ensure query embedding is not empty
        if len(query_embedding) == 0:
            logging.error("Empty query embedding received")
            return jsonify({'error': 'Empty query embedding'}), 500

        # logging.debug(f"Data type of top_n_embeddings: {type(top_n_embeddings_list)}")
        # logging.debug(f"Data type of query_embedding: {type(query_embedding)}")

        # Convert embeddings to numpy arrays
        try:
            top_n_embeddings_np = [np.array(embedding, dtype=float) for embedding in top_n_embeddings_list]
            query_embedding_np = np.array(query_embedding, dtype=float)
        except ValueError as e:
            logging.error(f"Error converting embeddings to numpy arrays: {e}")
            return jsonify({'error': 'Invalid embeddings format'}), 500

        # Calculate cosine similarities
        # similarities = [util.pytorch_cos_sim(query_embedding, embeddings) for embeddings in top_n_embeddings]
        similarities = []
        for embeddings in top_n_embeddings_np:
            # logging.debug(f"Embedding data type: {type(embeddings)}")
            similarity = util.cos_sim(query_embedding_np, embeddings)
            # logging.debug(f"Similarity datatype: {type(similarity.item())}")
            similarities.append(similarity.item())

        logging.debug(f"Similarities datatype: {type(similarities)}")


        # Get top N indices
        similarities = np.array(similarities)
        similarity_position = np.argsort(similarities)
        logging.debug(f"Indices are: {similarity_position}")
        top_indices= sorted(range(len(similarity_position)), key=lambda i: similarity_position[i], reverse=True)
        logging.debug(f"Top indices are: {top_indices}")
        output_indices = top_indices[:int(number)]
        logging.debug(f"Output indices are: {output_indices}")

        # Retrieve the content of the top N resumes
        all_pdf_texts = [resume_content[i] for i in output_indices]
        logging.debug(f"Top N resume content: {all_pdf_texts}")


        # Create input text for LLM
        input_text = create_input_text(all_pdf_texts, number, query)
        logging.debug(f"Input text for LLM: {input_text}")

        # Get response from LLM
        final_response = get_response_from_llm(input_text)

        logging.debug(f"Final response from LLM: \n\n\n\n{final_response}")

        return jsonify({'response': final_response})

    except Exception as e:
        logging.error(f"An error occurred during prompt processing: {e}")
        return jsonify({'error': 'Failed to process prompt'}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
