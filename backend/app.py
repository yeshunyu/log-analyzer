"""
LogScope Backend
Flask server with file decompression and LLM proxy
"""
import os
import io
import gzip
import tarfile
import zipfile
import bz2
import lzma
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='../', static_url_path='')

# Config
API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
API_URL = os.environ.get('DEEPSEEK_API_URL', 'https://api.deepseek.com/v1/chat/completions')
PORT = int(os.environ.get('PORT', 5000))

ALLOWED_EXTENSIONS = {'.log', '.txt', '.tar.gz', '.tgz', '.tar', '.gz', '.bz2', '.xz', '.zip'}

def allowed_file(filename):
    return '.' in filename and filename.lower()[filename.rfind('.'):] in ALLOWED_EXTENSIONS

def decompress_log_content(data, filename):
    """Decompress and extract log content from various formats."""
    name = filename.lower()

    # gzip
    if name.endswith('.gz') and not name.endswith('.tar.gz'):
        content = gzip.decompress(data)
        return content.decode('utf-8', errors='replace')

    # bz2
    if name.endswith('.bz2'):
        return bz2.decompress(data).decode('utf-8', errors='replace')

    # xz/lzma
    if name.endswith('.xz'):
        return lzma.decompress(data).decode('utf-8', errors='replace')

    # tar.gz / tgz
    if name.endswith('.tar.gz') or name.endswith('.tgz'):
        return extract_tar(io.BytesIO(gzip.decompress(data)))

    # tar (uncompressed)
    if name.endswith('.tar'):
        return extract_tar(io.BytesIO(data))

    # zip
    if name.endswith('.zip'):
        return extract_zip(data)

    # plain text - try decode
    return data.decode('utf-8', errors='replace')

def extract_tar(tar_io):
    """Extract relevant log files from tar archive."""
    content = []
    key_files = ['dmesg', 'syslog', 'messages', 'journal', 'kernel', 'errors', 'smart', 'meminfo', 'diskstats']
    log_exts = ['.log', '.txt', '.err', '.out', '.json']

    try:
        with tarfile.open(fileobj=tar_io) as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                name_lower = member.name.lower()
                is_key = any(k in name_lower for k in key_files)
                is_log = any(name_lower.endswith(ext) for ext in log_exts)

                if is_key or is_log:
                    if member.size > 0 and member.size < 50 * 1024 * 1024:  # max 50MB
                        try:
                            f = tar.extractfile(member)
                            if f:
                                text = f.read().decode('utf-8', errors='replace')
                                content.append(f'=== {member.name} ===\n{text}')
                        except:
                            pass
    except Exception as e:
        return f'[tar extraction error: {e}]'

    if not content:
        return '[no log files found in archive]'
    return '\n\n'.join(content)

def extract_zip(data):
    """Extract relevant log files from zip archive."""
    content = []
    key_files = ['dmesg', 'syslog', 'messages', 'journal', 'kernel', 'errors', 'smart', 'meminfo', 'diskstats']
    log_exts = ['.log', '.txt', '.err', '.out', '.json']

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for name in zf.namelist():
                name_lower = name.lower()
                is_key = any(k in name_lower for k in key_files)
                is_log = any(name_lower.endswith(ext) for ext in log_exts)

                if (is_key or is_log) and not name.endswith('/'):
                    info = zf.getinfo(name)
                    if info.file_size > 0 and info.file_size < 50 * 1024 * 1024:
                        try:
                            text = zf.read(name).decode('utf-8', errors='replace')
                            content.append(f'=== {name} ===\n{text}')
                        except:
                            pass
    except Exception as e:
        return f'[zip extraction error: {e}]'

    if not content:
        return '[no log files found in archive]'
    return '\n\n'.join(content)

@app.route('/')
def index():
    return send_from_directory('../', 'linux-os-log-analyzer.html')

@app.route('/api/upload', methods=['POST'])
def upload():
    """Upload and decompress log file."""
    if 'file' not in request.files:
        return jsonify({'error': 'no file'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'no filename'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'unsupported format'}), 400

    data = file.read()
    filename = file.filename

    try:
        content = decompress_log_content(data, filename)
        return jsonify({
            'success': True,
            'filename': filename,
            'size': len(data),
            'content_size': len(content),
            'preview': content[:500] if len(content) > 500 else content
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """Proxy chat completions to DeepSeek."""
    if not API_KEY:
        return jsonify({'error': 'API key not configured. Set DEEPSEEK_API_KEY env'}), 401

    data = request.get_json()
    model = data.get('model', 'deepseek-chat')
    messages = data.get('messages', [])
    temperature = data.get('temperature', 0.3)
    max_tokens = data.get('max_tokens', 2000)

    payload = {
        'model': model,
        'messages': messages,
        'temperature': temperature,
        'max_tokens': max_tokens
    }

    try:
        import urllib.request
        req = urllib.request.Request(
            API_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {API_KEY}'
            },
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return jsonify(result)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        try:
            err_json = json.loads(error_body)
            return jsonify({'error': err_json.get('error', {}).get('message', str(e))}), e.code
        except:
            return jsonify({'error': f'HTTP {e.code}: {error_body}'}), e.code
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print(f"LogScope starting on port {PORT}")
    print(f"API URL: {API_URL}")
    print(f"API Key: {'Configured' if API_KEY else 'Not set'}")
    app.run(host='0.0.0.0', port=PORT, debug=False)