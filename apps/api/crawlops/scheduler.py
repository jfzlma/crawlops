import logging
import os
import signal
import threading
import time

import httpx

stop = threading.Event()
logging.basicConfig(level=logging.INFO)


def main():
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    with httpx.Client(
        base_url=os.environ.get("CRAWLOPS_API_URL", "http://api:8000"),
        timeout=30,
        headers={"Authorization": "Bearer " + os.environ["CRAWLOPS_AGENT_TOKEN"]},
    ) as client:
        last_cleanup = 0.0
        while not stop.is_set():
            try:
                client.post("/internal/scheduler/tick").raise_for_status()
                if time.monotonic() - last_cleanup > 3600:
                    client.post("/internal/maintenance").raise_for_status()
                    last_cleanup = time.monotonic()
            except httpx.HTTPError:
                logging.exception("Schedule tick failed; database occurrences remain durable")
            stop.wait(2)


if __name__ == "__main__":
    main()
