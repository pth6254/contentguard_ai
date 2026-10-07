"""Process heartbeats and periodic work, using independent DB sessions."""
import logging
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta
from threading import Event, Thread

from models import WorkerHeartbeat

logger = logging.getLogger(__name__)


@contextmanager
def periodic(callback, interval=15):
    stopped = Event()
    def loop():
        while not stopped.wait(interval):
            try:
                callback()
            except Exception as exc:
                logger.warning("Worker heartbeat failed: %s", type(exc).__name__)
    thread = Thread(target=loop, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=2)


@contextmanager
def worker_heartbeat(factory, kind):
    worker_id = secrets.token_hex(16)
    def pulse():
        with factory() as db:
            row = db.get(WorkerHeartbeat, worker_id)
            if row is None:
                row = WorkerHeartbeat(id=worker_id, kind=kind)
                db.add(row)
            row.last_seen_at = datetime.utcnow()
            db.query(WorkerHeartbeat).filter(WorkerHeartbeat.last_seen_at < datetime.utcnow() - timedelta(days=1)).delete()
            db.commit()
    pulse()
    try:
        with periodic(pulse):
            yield
    finally:
        with factory() as db:
            db.query(WorkerHeartbeat).filter(WorkerHeartbeat.id == worker_id).delete()
            db.commit()
