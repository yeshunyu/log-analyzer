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
import time
from collections import defaultdict
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='../', static_url_path='')

# Config
API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
API_URL = os.environ.get('DEEPSEEK_API_URL', 'https://api.deepseek.com/v1/chat/completions')
PORT = int(os.environ.get('PORT', 5000))
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload

ALLOWED_EXTENSIONS = {'.log', '.txt', '.tar.gz', '.tgz', '.tar', '.gz', '.bz2', '.xz', '.zip'}

# Rate limiter (in-memory, per-IP)
_rate_limits = defaultdict(list)  # {ip: [timestamp, ...]}
RATE_LIMIT = 20   # max requests
RATE_WINDOW = 60  # seconds

# Upload history (in-memory, 24h retention)
upload_history = []  # list of {filename, size, content_size, preview, timestamp}

def allowed_file(filename):
    return '.' in filename and filename.lower()[filename.rfind('.'):] in ALLOWED_EXTENSIONS

def check_rate_limit(ip):
    """Return (allowed: bool, remaining: int)."""
    now = time.time()
    window = now - RATE_WINDOW
    _rate_limits[ip] = [t for t in _rate_limits[ip] if t > window]
    if len(_rate_limits[ip]) >= RATE_LIMIT:
        return False, 0
    _rate_limits[ip].append(now)
    return True, RATE_LIMIT - len(_rate_limits[ip])

def decompress_log_content(data, filename):
    """Decompress and extract log content from various formats.
    Returns:
      - plain text: str
      - archive: dict {tree, files: [{path, content, size}, ...]}
    """
    name = filename.lower()

    # gzip (single file)
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
        return extract_archive(io.BytesIO(gzip.decompress(data)), 'tar', filename)

    # tar (uncompressed)
    if name.endswith('.tar'):
        return extract_archive(io.BytesIO(data), 'tar', filename)

    # zip
    if name.endswith('.zip'):
        return extract_archive(io.BytesIO(data), 'zip', filename)

    # plain text - try decode
    return data.decode('utf-8', errors='replace')

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB per extracted file

def is_skippable(parts):
    """Skip hidden, system, and non-text files by path."""
    for part in parts:
        if not part or part == '.':
            continue
        if part.startswith('.') or part == '__MACOSX':
            return True
    return False

def build_tree(files, max_depth=3):
    """Build a tree-style string from file paths, showing only directories up to max_depth levels."""
    # Group files by directory, count files at each level
    tree = {}
    file_counts = {}  # path -> count of files under that path

    for f in sorted(files, key=lambda x: x['path']):
        parts = f['path'].replace('\\', '/').split('/')
        node = tree
        # Track file count for each directory level
        for i, p in enumerate(parts):
            if i == len(parts) - 1:
                # It's a file, increment file counts for all parent paths
                for j in range(1, len(parts)):
                    parent = '/'.join(parts[:j])
                    file_counts[parent] = file_counts.get(parent, 0) + 1
                break
            else:
                if p not in node:
                    node[p] = {}
                node = node[p]

    lines = []
    def _render(node, prefix, is_last, depth, parent_path):
        items = list(node.items())
        for i, (name, val) in enumerate(items):
            is_item_last = (i == len(items) - 1)
            connector = '└── ' if is_item_last else '├── '
            current_path = (parent_path + '/' + name).lstrip('/')
            if isinstance(val, dict) and depth < max_depth:
                fc = file_counts.get(current_path, 0)
                fc_str = f' ({fc} 文件)' if fc > 0 else ''
                lines.append(prefix + connector + name + '/' + fc_str)
                _render(val, prefix + ('    ' if is_item_last else '│   '), is_item_last, depth + 1, current_path)
            else:
                # At max depth or leaf node, show file count for this directory
                fc = file_counts.get(current_path, 0)
                if fc > 0:
                    lines.append(prefix + connector + name + '/ (' + str(fc) + ' 文件)')

    _render(tree, '', True, 0, '')
    return '\n'.join(lines)

def format_bytes(b):
    if b < 1024:
        return f'{b} B'
    if b < 1024 * 1024:
        return f'{b / 1024:.1f} KB'
    return f'{b / 1024 / 1024:.1f} MB'

def extract_archive(io_obj, fmt, filename):
    """Extract ALL files from an archive. Returns {tree, files}."""
    result = []
    max_files = 200

    try:
        if fmt == 'tar':
            with tarfile.open(fileobj=io_obj) as tar:
                for member in tar.getmembers():
                    if not member.isfile():
                        continue
                    if member.size == 0 or member.size > MAX_FILE_SIZE:
                        continue
                    path = member.name.lstrip('./')
                    if is_skippable(path.replace('\\', '/').split('/')):
                        continue
                    if len(result) >= max_files:
                        break
                    try:
                        f = tar.extractfile(member)
                        if f:
                            text = f.read().decode('utf-8', errors='replace')
                            result.append({'path': path, 'content': text, 'size': len(text)})
                    except Exception:
                        pass
        else:  # zip
            with zipfile.ZipFile(io_obj) as zf:
                for name in zf.namelist():
                    if name.endswith('/'):
                        continue
                    info = zf.getinfo(name)
                    if info.file_size == 0 or info.file_size > MAX_FILE_SIZE:
                        continue
                    path = name.lstrip('/')
                    if is_skippable(path.replace('\\', '/').split('/')):
                        continue
                    if len(result) >= max_files:
                        break
                    try:
                        text = zf.read(name).decode('utf-8', errors='replace')
                        result.append({'path': path, 'content': text, 'size': len(text)})
                    except Exception:
                        pass
    except Exception as e:
        return {'tree': f'[extraction error: {e}]', 'files': [], 'error': str(e)}

    if not result:
        return {'tree': '(empty archive)', 'files': []}

    return {
        'tree': build_tree(result),
        'files': result,
        'file_count': len(result)
    }

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

        # Clean up expired entries (24h)
        now = time.time()
        while upload_history and now - upload_history[0]['timestamp'] > 86400:
            upload_history.pop(0)

        if isinstance(content, dict):
            # Archive: tree + files
            entry = {
                'id': int(now * 1000),
                'filename': filename,
                'size': len(data),
                'is_archive': True,
                'file_count': content.get('file_count', 0),
                'tree': content.get('tree', ''),
                'preview': content.get('tree', ''),
                'timestamp': now
            }
            upload_history.append(entry)

            return jsonify({
                'success': True,
                'id': entry['id'],
                'type': 'archive',
                'filename': filename,
                'size': len(data),
                'tree': content.get('tree', ''),
                'files': content.get('files', []),
                'file_count': content.get('file_count', 0),
                'error': content.get('error', '')
            })
        else:
            # Plain text
            entry = {
                'id': int(now * 1000),
                'filename': filename,
                'size': len(data),
                'is_archive': False,
                'content_size': len(content),
                'preview': content[:500] if len(content) > 500 else content,
                'timestamp': now
            }
            upload_history.append(entry)

            return jsonify({
                'success': True,
                'id': entry['id'],
                'type': 'text',
                'filename': filename,
                'size': len(data),
                'content': content,
                'content_size': len(content),
                'preview': content[:500] if len(content) > 500 else content
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history', methods=['GET'])
def history():
    """Get upload history (last 24h)."""
    now = time.time()
    active = [h for h in upload_history if now - h['timestamp'] <= 86400]
    return jsonify({
        'history': [
            {
                'id': h['id'],
                'filename': h['filename'],
                'size': h['size'],
                'content_size': h.get('content_size', 0),
                'preview': h['preview'][:200] + ('...' if len(h['preview']) > 200 else ''),
                'timestamp': h['timestamp']
            }
            for h in reversed(active[-10:])
        ]
    })

@app.route('/api/history/<int:item_id>', methods=['GET'])
def history_item(item_id):
    """Get a single history item by ID."""
    now = time.time()
    for h in upload_history:
        if h['id'] == item_id and now - h['timestamp'] <= 86400:
            return jsonify({
                'id': h['id'],
                'filename': h['filename'],
                'size': h['size'],
                'content_size': h.get('content_size', 0),
                'preview': h['preview'],
                'timestamp': h['timestamp']
            })
    return jsonify({'error': 'Item not found or expired'}), 404

@app.route('/api/chat', methods=['POST'])
def chat():
    """Proxy chat completions to DeepSeek."""
    ip = request.remote_addr or 'unknown'
    allowed, remaining = check_rate_limit(ip)
    if not allowed:
        return jsonify({'error': f'Rate limit exceeded. {RATE_LIMIT} req/{RATE_WINDOW}s per IP'}), 429

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
        except (json.JSONDecodeError, ValueError):
            return jsonify({'error': f'HTTP {e.code}: {error_body}'}), e.code
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large. Max upload size is 100MB'}), 413

if __name__ == '__main__':
    print(f"LogScope starting on port {PORT}")
    print(f"API URL: {API_URL}")
    print(f"API Key: {'Configured' if API_KEY else 'Not set'}")
    app.run(host='0.0.0.0', port=PORT, debug=False)