"""
LogScope Backend
Flask server for static files only
"""
from flask import Flask, send_from_directory

app = Flask(__name__, static_folder='../', static_url_path='')

@app.route('/')
def index():
    return send_from_directory('../', 'linux-os-log-analyzer.html')

if __name__ == '__main__':
    print("LogScope starting on port 5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
