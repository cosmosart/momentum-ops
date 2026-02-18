from ingestion.scheduler import DataScheduler
# Use BlockingScheduler instead of BackgroundScheduler in your class
# OR keep it simple:
scheduler = DataScheduler()
scheduler.start()
# Keep main thread alive without sleep hack if using BackgroundScheduler
import signal, time
try:
    while True: time.sleep(1)
except KeyboardInterrupt:
    scheduler.stop()