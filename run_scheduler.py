"""
Run the data ingestion scheduler.
"""

import logging
import signal
import time
import sys
from ingestion.scheduler import DataScheduler

# Force unbuffered output for Docker
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Configure logging with immediate flush
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Force flush after each log
logging.getLogger().handlers[0].flush = lambda: sys.stdout.flush()

logger = logging.getLogger(__name__)

def main():
    """Main function to run the scheduler."""
    try:
        logger.info("Starting scheduler application...")
        sys.stdout.flush()
        
        # Create and start scheduler
        scheduler = DataScheduler()
        
        # Set up signal handlers
        def handle_shutdown(signum, frame):
            """Handle termination signals by stopping the scheduler and exiting."""
            logger.info(f"Shutdown signal {signum} received, stopping scheduler...")
            sys.stdout.flush()
            scheduler.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)
        
        # Start the scheduler
        logger.info("Initializing scheduler...")
        sys.stdout.flush()
        scheduler.start()
        
        logger.info("Scheduler is running. Press Ctrl+C to stop.")
        sys.stdout.flush()
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, stopping scheduler...")
        sys.stdout.flush()
        scheduler.stop()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error in scheduler: {e}", exc_info=True)
        sys.stdout.flush()
        sys.stderr.flush()
        sys.exit(1)

if __name__ == "__main__":
    main()