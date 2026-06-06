"""
DeFi91 Arbitrage Engine - Main Entry Point
Owner: Karman
Network: Base Network (Chain ID: 8453)

Usage:
    python main.py              # Run bot (uses DRY_RUN env var)
    python main.py --dry-run    # Force dry run mode
    python main.py --live       # Force live mode (CAUTION!)
"""

import sys
import os
import signal
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DRY_RUN, BASE_RPC_URL, PRIVATE_KEY, ARBITRAGE_CONTRACT, PAIRS
from logger import ArbitrageLogger
from scanner import ArbitrageScanner
from executor import ArbitrageExecutor


def print_banner():
    """Print bot banner."""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║        ██████╗ ███████╗███████╗██╗ █████╗  ██╗              ║
║        ██╔══██╗██╔════╝██╔════╝██║██╔══██╗███║              ║
║        ██║  ██║█████╗  █████╗  ██║╚██████║╚██║              ║
║        ██║  ██║██╔══╝  ██╔══╝  ██║ ╚═══██║ ██║              ║
║        ██████╔╝███████╗██║     ██║ █████╔╝ ██║              ║
║        ╚═════╝ ╚══════╝╚═╝     ╚═╝ ╚════╝  ╚═╝              ║
║                                                              ║
║           ARBITRAGE ENGINE v1.0 | Base Network               ║
║                     by: KARMAN                               ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def validate_config():
    """Validate configuration before starting."""
    errors = []

    if not BASE_RPC_URL:
        errors.append("BASE_RPC_URL not set")

    if not PRIVATE_KEY and not DRY_RUN:
        errors.append("PRIVATE_KEY not set (required for live mode)")

    if not ARBITRAGE_CONTRACT and not DRY_RUN:
        errors.append("ARBITRAGE_CONTRACT not set (required for live mode)")

    if not PAIRS:
        errors.append("No trading pairs configured")

    return errors


def main():
    """Main entry point."""
    print_banner()

    # Parse command line arguments
    dry_run = DRY_RUN
    if "--dry-run" in sys.argv:
        dry_run = True
    elif "--live" in sys.argv:
        dry_run = False

    # Initialize logger
    logger = ArbitrageLogger()

    # Validate config
    errors = validate_config()
    if errors:
        for err in errors:
            logger.log_status(f"[CONFIG ERROR] {err}")
        if not dry_run:
            logger.log_status("Cannot start in live mode with config errors. Exiting.")
            sys.exit(1)
        else:
            logger.log_status("Running in DRY RUN mode despite config errors.")

    # Set mode
    mode = "dry_run" if dry_run else "online"
    logger.set_bot_status(mode)
    logger.log_status(f"Mode: {'🧪 DRY RUN (Simulation)' if dry_run else '🔴 LIVE (Real Money)'}")
    logger.log_status(f"RPC: {BASE_RPC_URL}")
    logger.log_status(f"Pairs: {len(PAIRS)}")

    if not dry_run:
        logger.log_status("⚠️  LIVE MODE - Real transactions will be sent!")
        logger.log_status("    Press Ctrl+C to stop at any time.")
        time.sleep(3)  # Give user time to cancel

    # Initialize components
    logger.log_status("Initializing Scanner...")
    scanner = ArbitrageScanner(logger)

    logger.log_status("Initializing Executor...")
    executor = ArbitrageExecutor(logger)

    # Setup graceful shutdown
    def signal_handler(sig, frame):
        logger.log_status("Shutting down gracefully...")
        logger.set_bot_status("offline")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start scanning
    logger.log_status("=" * 60)
    logger.log_status("Bot started! Scanning for arbitrage opportunities...")
    logger.log_status("=" * 60)

    # Run scanner with executor callback
    def on_opportunity(opportunity):
        """Callback when scanner finds an opportunity."""
        logger.log_status(
            f"[OPPORTUNITY] {opportunity['pair']} | "
            f"{opportunity['direction']} | "
            f"Diff: {opportunity['price_diff_pct']:.4f}%"
        )
        executor.execute_opportunity(opportunity)

    # Override DRY_RUN in executor if needed
    if dry_run:
        import config
        config.DRY_RUN = True

    scanner.run_continuous(callback=on_opportunity)


if __name__ == "__main__":
    main()
