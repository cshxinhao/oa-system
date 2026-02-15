import os

bind = os.environ.get("GUNICORN_BIND", "unix:/run/oa-system/gunicorn.sock")
workers = int(os.environ.get("GUNICORN_WORKERS", "3"))
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "sync")
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "60"))
accesslog = "-"
errorlog = "-"
