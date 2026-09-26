"""Run with `python analysis_worker.py` after applying database migrations."""
import logging
import time
from database import SessionLocal
from services.analysis_job_service import process_one

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            with SessionLocal() as db:
                processed = process_one(db)
        except Exception as exc:
            logger.error("Analysis worker error: %s", type(exc).__name__)
            processed = False
        if not processed:
            time.sleep(2)


if __name__ == "__main__":
    main()
