"""Запуск веб-версии: python src/server.py, затем откройте http://localhost:8000"""

import os
import sys
from pathlib import Path

import uvicorn

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    # Один процесс: партии хранятся в памяти сервера.
    uvicorn.run('web.server:app', host=os.environ.get('HOST', '0.0.0.0'),
                port=int(os.environ.get('PORT', '8000')), workers=1)
