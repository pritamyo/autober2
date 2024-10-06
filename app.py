from flask import Flask, request, jsonify
import queue
import threading
from worker import process_pull_request
import os

app = Flask(__name__)

# GitHub API token (replace with your actual token)
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', os.environ.get('GITHUB_TOKEN'))

# Create a queue for jobs
job_queue = queue.Queue()

# Function to process jobs from the queue
def worker():
    while True:
        job = job_queue.get()
        if job is None:
            break
        payload, token = job
        process_pull_request(payload, token)
        job_queue.task_done()

# Start the worker thread
worker_thread = threading.Thread(target=worker)
worker_thread.start()

@app.route('/webhook', methods=['POST'])
def webhook():
    # Process the webhook payload
    event = request.headers.get('X-GitHub-Event')
    if event == 'pull_request':
        payload = request.json
        action = payload.get('action')
        
        # Only process 'opened' action for pull requests
        if action == 'opened':
            # Add the job to the queue
            job_queue.put((payload, GITHUB_TOKEN))
            return jsonify({"message": "Pull request creation queued for processing"}), 202
        else:
            return jsonify({"message": "Ignored non-creation pull request event"}), 200
    
    return jsonify({"message": "Ignored non-pull request event"}), 200

if __name__ == '__main__':
    try:
        app.run(debug=False, port=os.environ.get('PORT', 5000), host='0.0.0.0')
    finally:
        # Signal the worker thread to exit
        job_queue.put(None)
        worker_thread.join()