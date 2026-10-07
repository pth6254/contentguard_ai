"""Run with `python webhook_worker.py` after applying database migrations."""
import logging
import time
from database import SessionLocal
from services.worker_health import worker_heartbeat
from services.webhook_service import deliver_one

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO)
    with worker_heartbeat(SessionLocal, 'webhook'):
        run_loop()


def run_loop():
    while True:
        try:
            with SessionLocal() as db:
                processed = deliver_one(db)
        except Exception as exc:
            logger.error("Webhook worker error: %s", type(exc).__name__)
            processed = False
        if not processed:
            time.sleep(5)


if __name__ == "__main__":
    main()
