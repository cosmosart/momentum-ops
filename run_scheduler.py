from ingestion.scheduler import DataScheduler
# Use BlockingScheduler instead of BackgroundScheduler in your class
# OR keep it simple:
scheduler = DataScheduler()
scheduler.start()
# Keep main thread alive without sleep hack if using BackgroundScheduler
import signal
import time
def _handle_shutdown(signum, frame):
    """
    Handle termination signals by stopping the scheduler and exiting.
    """
    scheduler.stop()
    raise SystemExit(0)
signal.signal(signal.SIGTERM, _handle_shutdown)
signal.signal(signal.SIGINT, _handle_shutdown)
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    scheduler.stop()