# chunk_upload_handler.py
import os
from tornado.web import RequestHandler

class ChunkUploadHandler(RequestHandler):
    def post(self):
        filename = self.get_argument('filename')
        chunk = self.request.body
        output_path = os.path.join('uploads', filename)
        os.makedirs('uploads', exist_ok=True)
        with open(output_path, "ab") as f:
            f.write(chunk)
        self.set_status(200)
