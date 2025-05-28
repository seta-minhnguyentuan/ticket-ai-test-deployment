#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import os
import json
from datetime import datetime
import uuid
from bottle import Bottle, request, response, run, static_file
import openai
from google.cloud import bigquery, storage
# Initialize bottle app
app = Bottle()

# Setup markdown parser

# Configuration
config = {
    "openai_api_key": os.environ.get("OPENAI_API_KEY", ""),
    "gcp_project_id": os.environ.get("GCP_PROJECT_ID", ""),
    "storage_bucket": os.environ.get("STORAGE_BUCKET", "api_logs"),
    "static_folder": os.path.join(os.getcwd(), "Static")
}

# Initialize OpenAI client
openai.api_key = config["openai_api_key"]

# Initialize GCP clients if credentials are available
bigquery_client = None
storage_client = None
try:
    bigquery_client = bigquery.Client()
    storage_client = storage.Client()
except Exception as e:
    print(f"Warning: Could not initialize GCP clients: {e}")

# Serve static files
@app.route('/static/<filepath:path>')
def serve_static(filepath):
    return static_file(filepath, root=config["static_folder"])

# Serve favicon
@app.route('/favicon.ico')
def favicon():
    return static_file('favicon.ico', root=config["static_folder"])

# Root endpoint
@app.route('/')
def index():
    return static_file('index.html', root=config["static_folder"])

# Health check endpoint
@app.route('/health')
def health_check():
    return {"status": "healthy", "version": "1.0.0"}

# Ticket processing endpoint
@app.route('/process_ticket', method='POST')
def process_ticket():
    try:
        data = request.json
        query = data.get('query', '')
        response_type = data.get('responseType', 'customer')
        deployment = data.get('deployment', 'gpt-3.5-turbo')
        agent_name = data.get('agentName', '')
        ticket_number = data.get('ticketNumber', '')

        if not query:
            response.status = 400
            return {"error": "No query provided"}

        # Start time for processing
        start_time = datetime.now()

        # Read sample response from Test.md
        with open(os.path.join(os.getcwd(), 'Test.md'), 'r') as file:
            content = file.read()

        # Extract customer response from markdown file
        import re
        customer_response_match = re.search(r'### Customer response:\s*"(.+?)"', content, re.DOTALL)
        customer_response = customer_response_match.group(1).strip() if customer_response_match else "Thank you for your query. We'll get back to you soon."

        # Generate a session ID for tracking
        query_id = str(uuid.uuid4())

        # Mock data
        vehicleSubscriptionResponse = "Vehicle: Mitsubishi Outlander 2023\nVIN: ABC123456789\nSubscription: Active\nExpiry: 2025-12-31"
        debugResponse = json.dumps({
            "query": query,
            "model": deployment,
            "processingSteps": ["Parse query", "Extract context", "Generate response"]
        })
        SW_INFO = "TicketAI for Finch (v1.11.0)"
        reply_role = response_type
        runtime = datetime.now() - start_time
        processing_time = runtime
        user_query = query

        return {
            'customerResponse': customer_response,
            'vehicleSubscriptionResponse': vehicleSubscriptionResponse,
            'debugResponse': debugResponse,
            'sessionId': query_id,
            'SW_INFO': SW_INFO,
            'processing_time': processing_time.total_seconds(),
            'Role': reply_role,
            'run_time': runtime.total_seconds(),
            'customerQuery': user_query
        }

    except Exception as e:
        response.status = 500
        return {"error": str(e)}

# Process rating feedback
@app.route('/process_rating', method='POST')
def process_rating():
    try:
        data = request.json
        name = data.get('name', '')
        ticket = data.get('ticket', '')
        rating = data.get('rating', '0')
        comment = data.get('comment', '')
        followup = data.get('followup', '0')
        session_id = data.get('sessionID', '')

        # Log the rating to BigQuery or other storage
        print(f"Rating received: {rating} for session {session_id}")

        return {"status": "success"}

    except Exception as e:
        response.status = 500
        return {"error": str(e)}


# Run the server if executed directly
if __name__ == '__main__':
    # Print information about the server
    print(f"Current working directory: {os.getcwd()}")
    print(f"Running in Jupyter notebook environment")
    print(f"Static folder: {config['static_folder']}")
    print(f"File directory: {os.getcwd()}")
    print(f"Static folder: {config['static_folder']}")
    print("Starting API server on port 8080...")
    run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
