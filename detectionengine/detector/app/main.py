import os
import time

from app.processor import process_batch


BATCH_SIZE = int(os.environ.get("DETECTOR_BATCH_SIZE", 100))
EVENT_WORKERS = int(os.environ.get("DETECTOR_EVENT_WORKERS", 4))
POLL_INTERVAL = float(os.environ.get("DETECTOR_POLL_INTERVAL", 0.05))
ERROR_SLEEP = float(os.environ.get("DETECTOR_ERROR_SLEEP", 0.25))


def main():
    print(f"[detector] started batch_size={BATCH_SIZE} event_workers={EVENT_WORKERS} poll_interval={POLL_INTERVAL}")

    while True:
        try:
            result = process_batch(batch_size=BATCH_SIZE, event_workers=EVENT_WORKERS)
            if not result.get("processed"):
                time.sleep(POLL_INTERVAL)
        except Exception as e:
            print(f"[ERROR] detector loop failure: {e}")
            time.sleep(ERROR_SLEEP)


if __name__ == "__main__":
    main()
