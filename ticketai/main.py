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

# Text completion API endpoint
@app.route('/api/complete', method='POST')
def text_completion():
    try:
        data = request.json
        prompt = data.get('prompt')
        model = data.get('model', 'gpt-3.5-turbo')
        max_tokens = data.get('max_tokens', 100)
        temperature = data.get('temperature', 0.7)

        if not prompt:
            response.status = 400
            return {"error": "No prompt provided"}

        # Call OpenAI API
        result = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )

        # Log request to BigQuery if available
        if bigquery_client:
            _log_to_bigquery(prompt, result)

        # Return formatted response
        return {
            "id": str(uuid.uuid4()),
            "text": result.choices[0].message.content,
            "prompt_tokens": result.usage.prompt_tokens,
            "completion_tokens": result.usage.completion_tokens,
            "total_tokens": result.usage.total_tokens,
            "model": model
        }

    except Exception as e:
        response.status = 500
        return {"error": str(e)}


# Store file in GCS
@app.route('/api/upload', method='POST')
def upload_file():
    try:
        if not storage_client:
            response.status = 503
            return {"error": "GCS storage not configured"}

        file_data = request.files.get('file')
        if not file_data:
            response.status = 400
            return {"error": "No file provided"}

        file_name = file_data.filename
        file_content = file_data.file.read()
        content_type = file_data.content_type

        bucket = storage_client.bucket(config["storage_bucket"])
        blob = bucket.blob(f"uploads/{datetime.now().strftime('%Y%m%d')}/{file_name}")
        blob.upload_from_string(file_content, content_type=content_type)

        return {
            "status": "success",
            "file_name": file_name,
            "url": f"gs://{config['storage_bucket']}/{blob.name}"
        }

    except Exception as e:
        response.status = 500
        return {"error": str(e)}

# Helper function to log to BigQuery
def _log_to_bigquery(prompt, response):
    try:
        table_id = f"{config['gcp_project_id']}.apilog.requests"

        row = {
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "model": response.model,
            "tokens": response.usage.total_tokens,
            "session_id": str(uuid.uuid4())
        }

        errors = bigquery_client.insert_rows_json(table_id, [row])
        if errors:
            print(f"BigQuery insert errors: {errors}")
    except Exception as e:
        print(f"Failed to log to BigQuery: {e}")

# Run the server if executed directly
if __name__ == '__main__':
    # Print information about the server
    print(f"Current working directory: {os.getcwd()}")
    print(f"Running in Jupyter notebook environment")
    print(f"Static folder: {config['static_folder']}")
    print(f"File directory: {os.getcwd()}")
    print(f"Static folder: {config['static_folder']}")
    print("Starting API server on port 5010...")
    run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 5010)), debug=True)


# # TicketAI for Finch (v1.11.0)
# 
# ## Overview
# 
# TicketAI is a support tool designed to assist customer support agents in providing responses to customer queries based on predefined knowledge base entries. It leverages OpenAI's API and integrates with Google Cloud Platform (GCP) services to retrieve relevant vehicle data and operational context for each query. The tool is built using the Bottle web framework and supports interactions with BigQuery and Google Cloud Storage.
# 
# ## Features
# 
# - Integration with OpenAI’s Azure API for generating automated responses.
# - Queries GCP services (BigQuery, Storage) for vehicle data and subscriptions.
# - Uses a Markdown-based knowledge base for predefined customer support templates.
# - Logs queries, responses, and processing times into BigQuery for tracking and analysis.
# - Allows support agents to update the knowledge base dynamically from GCP Storage.
# - Supports vehicle identification through VIN lookups and retrieves detailed vehicle context.
# 
# ## Requirements
# 
# - Python 3.x
# - Google Cloud Project with BigQuery, Cloud Storage, and Secret Manager enabled.
# - OpenAI API key and Azure OpenAI setup.
# - GCP credentials (stored as environment variables).
# - Bottle framework.
# 
# ## Environment Variables
# 
# The application relies on several environment variables to function correctly:
# 
# | Variable             | Description                                                   |
# |----------------------|---------------------------------------------------------------|
# | `GCP_PROJECT`        | Google Cloud project name.                                    |
# | `AZURE_OPENAI_ENDPOINT` | Azure OpenAI API endpoint.                                    |
# | `AZURE_OPENAI_KEY`    | Azure OpenAI API key.                                         |
# | `GCP_DATASET`        | Name of the BigQuery dataset used for logging stats.           |
# | `GCS_BUCKET_NAME`    | Name of the GCS bucket where knowledge base files are stored.  |
# | `TOOL_DEBUG`         | Debug flag to enable or disable detailed logs.                 |
# 
# ## Endpoints
# 
# ### `/`
# 
# - **Method**: `GET`
# - **Description**: Returns the main page with software information and the agent's email.
# 
# ### `/process_ticket`
# 
# - **Method**: `POST`
# - **Description**: Processes a customer query and returns a suggested response from the knowledge base.
# - **Request Payload**:
#   ```json
#   {
#     "query": "<customer query>",
#     "responseType": "customer", // or "agent"
#     "deployment": "<model deployment (optional)>"
#   }
#   ```
# 
# # Run the server if executed directly
# if __name__ == '__main__':
#     # Determine the current directory to properly serve static files
#     print(f"Current working directory: {os.getcwd()}")
#     print(f"File directory: {os.path.dirname(os.path.abspath(__file__))}")
#     
#     # Start server on port 5010
#     print("Starting API server on port 5010...")
#     run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5010)), debug=True)
