from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
import logging
import fitz
from models import process_pdfs, compute_similarity, extract_text_from_pdf, fetch_urls, get_embeddings
from sentence_transformers import SentenceTransformer, util
import google.generativeai as genai

model = SentenceTransformer('all-MiniLM-L6-v2')
load_dotenv()

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.getenv('DATABASE_URL')
engine = create_engine(DATABASE_URL)
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
api_key = os.getenv('API_TOKEN_GEMINI')

supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/api/prior_info', methods=['POST'])
def prior_info():
    data = request.json
    job_description = data.get('jobDesc')
    category = data.get('category')

    # Process PDFs
    def process_pdfs(job_description, category):
        logging.debug("Process PDFs started")
        urls = fetch_urls(category)
        logging.debug(f"URLs fetched successfully: {urls}")
        logging.debug(f"datatype of urls: {type(urls)}")
        size = len(urls)
        logging.debug(f"list has {size} urls")

        # Iterate through the URLs and update the score and embeddings columns
        for entry in range(size):
            pdf_text = extract_text_from_pdf(urls[entry])
            logging.debug("Going to enter the compute similarity function")
            score = compute_similarity(pdf_text, job_description, model, util)
            logging.debug(f"Computed the score {score}")

            pdf_embeddings = get_embeddings(pdf_text)
            supabase_client.table(category).update({'score': score, 'embeddings': pdf_embeddings}).eq('url', urls[entry]).execute()
            logging.debug("Updated score and embeddings in database successfully")

        return      

    process_pdfs(job_description, category)
    return jsonify({'status': 'success', 'message': 'Updated score and embeddings in database successfully'})

@app.route('/api/prompt', methods=['POST'])
def prompt():
    data = request.json
    query = data.get('prompt')
    number = data.get('shortlistedCand')
    category = data.get('category')

    response = supabase_client.table(category).select('url').order('score', desc=True).limit(number).execute()
    logging.debug(f"Debugging the response {response.data}")
    urls = [row['url'] for row in response.data]
    logging.debug(f"Fetched the content in descending order {urls}")

    # Fetch the content of the PDFs and then pass it to the LLM
    all_pdf_texts = []
    for url in urls:
        pdf_text = extract_text_from_pdf(url)
        all_pdf_texts.append(pdf_text)

    def create_input_text(all_pdf_texts, query_text):
        input_text = ""
        for i, pdf_text in enumerate(all_pdf_texts, 1):
            input_text += f"Document {i}:\n{pdf_text}\n\n"
        input_text += f"Query:\n{query_text}\n"
        logging.debug(f"Input text created: {input_text}")
        return input_text

    input_text = create_input_text(all_pdf_texts, query)

    def get_response_from_llm(input_text):
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.0-pro')
        output = model.generate_content(input_text)
        response = output.text
        logging.debug(f"Response from LLM: {response}")
        return response

    final_response = get_response_from_llm(input_text)
    return jsonify({'response': final_response})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
