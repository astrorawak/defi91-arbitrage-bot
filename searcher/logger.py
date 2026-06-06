"""
DeFi91 Arbitrage Engine - Logger
Mencatat semua aktivitas bot ke file JSON untuk dashboard.
"""

import json
import os
import time
from datetime import datetime, timezone


class ArbitrageLogger:
    """Logger untuk mencatat trades, errors, dan statistik bot."""

    def __init__(self, log_file="trades_log.json", dashboard_file="dashboard/data.json"):
        self.log_file = log_file
        self.dashboard_file = dashboard_file
        self._ensure_files()

    def _ensure_files(self):
        """Pastikan file log dan dashboard ada."""
        if not os.path.exists(self.log_file):
            self._write_json(self.log_file, {"trades": [], "errors": [], "stats": {}})

        dashboard_dir = os.path.dirname(self.dashboard_file)
        if dashboard_dir and not os.path.exists(dashboard_dir):
            os.makedirs(dashboard_dir, exist_ok=True)

        if not os.path.exists(self.dashboard_file):
            self._write_json(self.dashboard_file, self._empty_dashboard())

    def _empty_dashboard(self):
        """Template data dashboard kosong."""
        return {
            "last_updated": "",
            "total_profit_usd": 0.0,
            "total_trades": 0,
            "successful_trades": 0,
            "failed_trades": 0,
            "win_rate": 0.0,
            "daily_profits": [],
            "recent_trades": [],
            "bot_status": "offline",
            "uptime_start": "",
        }

    def _read_json(self, filepath):
        """Baca file JSON dengan aman."""
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _write_json(self, filepath, data):
        """Tulis data ke file JSON."""
        dir_path = os.path.dirname(filepath)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def log_trade(self, trade_data):
        """
        Catat trade yang berhasil.
        
        trade_data: dict dengan keys:
            - pair: str (e.g., "WETH/USDC")
            - direction: str (e.g., "Uniswap->Aerodrome")
            - amount_in: float
            - amount_out: float
            - profit_usd: float
            - gas_used: int
            - gas_cost_usd: float
            - tx_hash: str
            - timestamp: str (ISO format)
        """
        logs = self._read_json(self.log_file)
        if "trades" not in logs:
            logs["trades"] = []

        trade_entry = {
            "id": len(logs["trades"]) + 1,
            "timestamp": trade_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "pair": trade_data.get("pair", ""),
            "direction": trade_data.get("direction", ""),
            "amount_in": trade_data.get("amount_in", 0),
            "amount_out": trade_data.get("amount_out", 0),
            "profit_usd": trade_data.get("profit_usd", 0),
            "gas_used": trade_data.get("gas_used", 0),
            "gas_cost_usd": trade_data.get("gas_cost_usd", 0),
            "net_profit_usd": trade_data.get("profit_usd", 0) - trade_data.get("gas_cost_usd", 0),
            "tx_hash": trade_data.get("tx_hash", ""),
            "status": "success",
        }

        logs["trades"].append(trade_entry)
        self._write_json(self.log_file, logs)
        self._update_dashboard(trade_entry)

        print(f"[TRADE] ✅ {trade_entry['pair']} | Profit: ${trade_entry['net_profit_usd']:.4f} | TX: {trade_entry['tx_hash'][:16]}...")

    def log_error(self, error_data):
        """
        Catat error/revert.
        
        error_data: dict dengan keys:
            - pair: str
            - reason: str
            - timestamp: str
        """
        logs = self._read_json(self.log_file)
        if "errors" not in logs:
            logs["errors"] = []

        error_entry = {
            "id": len(logs["errors"]) + 1,
            "timestamp": error_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "pair": error_data.get("pair", ""),
            "reason": error_data.get("reason", "Unknown"),
        }

        logs["errors"].append(error_entry)
        self._write_json(self.log_file, logs)

        # Update dashboard failed trades count
        dashboard = self._read_json(self.dashboard_file)
        dashboard["failed_trades"] = dashboard.get("failed_trades", 0) + 1
        dashboard["total_trades"] = dashboard.get("total_trades", 0) + 1
        self._recalculate_win_rate(dashboard)
        dashboard["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._write_json(self.dashboard_file, dashboard)

        print(f"[ERROR] ❌ {error_entry['pair']} | Reason: {error_entry['reason']}")

    def log_scan(self, pair_name, price_diff_pct, profitable):
        """Log scanning activity (verbose mode)."""
        status = "💰 OPPORTUNITY" if profitable else "⏳ No arb"
        print(f"[SCAN] {status} | {pair_name} | Diff: {price_diff_pct:.4f}%")

    def log_status(self, message):
        """Log status message."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"[STATUS] [{timestamp}] {message}")

    def set_bot_status(self, status):
        """Update bot status di dashboard (online/offline/dry_run)."""
        dashboard = self._read_json(self.dashboard_file)
        dashboard["bot_status"] = status
        if status in ("online", "dry_run"):
            dashboard["uptime_start"] = datetime.now(timezone.utc).isoformat()
        dashboard["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._write_json(self.dashboard_file, dashboard)

    def _update_dashboard(self, trade_entry):
        """Update dashboard data setelah trade berhasil."""
        dashboard = self._read_json(self.dashboard_file)

        dashboard["total_profit_usd"] = dashboard.get("total_profit_usd", 0) + trade_entry["net_profit_usd"]
        dashboard["total_trades"] = dashboard.get("total_trades", 0) + 1
        dashboard["successful_trades"] = dashboard.get("successful_trades", 0) + 1
        self._recalculate_win_rate(dashboard)

        # Daily profits
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily_profits = dashboard.get("daily_profits", [])
        if daily_profits and daily_profits[-1].get("date") == today:
            daily_profits[-1]["profit"] += trade_entry["net_profit_usd"]
            daily_profits[-1]["trades"] += 1
        else:
            daily_profits.append({
                "date": today,
                "profit": trade_entry["net_profit_usd"],
                "trades": 1,
            })
        dashboard["daily_profits"] = daily_profits[-30:]  # Keep last 30 days

        # Recent trades (last 50)
        recent = dashboard.get("recent_trades", [])
        recent.append({
            "timestamp": trade_entry["timestamp"],
            "pair": trade_entry["pair"],
            "profit": trade_entry["net_profit_usd"],
            "tx_hash": trade_entry["tx_hash"],
        })
        dashboard["recent_trades"] = recent[-50:]

        dashboard["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._write_json(self.dashboard_file, dashboard)

    def _recalculate_win_rate(self, dashboard):
        """Hitung ulang win rate."""
        total = dashboard.get("total_trades", 0)
        success = dashboard.get("successful_trades", 0)
        dashboard["win_rate"] = (success / total * 100) if total > 0 else 0.0

    def get_stats(self):
        """Ambil statistik ringkas."""
        dashboard = self._read_json(self.dashboard_file)
        return {
            "total_profit": dashboard.get("total_profit_usd", 0),
            "total_trades": dashboard.get("total_trades", 0),
            "win_rate": dashboard.get("win_rate", 0),
            "bot_status": dashboard.get("bot_status", "offline"),
        }
