import sys
sys.path.insert(0, 'scan_entry')
sys.path.insert(0, 'ocr_cli')
from app import app
app.run(debug=False, threaded=True, port=5000)
