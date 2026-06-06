"""
DeFi91 Arbitrage Engine - Scanner
Memantau harga real-time via multicall dan mendeteksi peluang arbitrase.
"""

import time
import math
from web3 import Web3
from eth_abi import encode, decode

from config import (
    BASE_RPC_URL,
    PAIRS,
    UNISWAP_V3_FACTORY,
    AERODROME_SLIPSTREAM_FACTORY,
    UNISWAP_V3_FACTORY_ABI,
    AERODROME_FACTORY_ABI,
    UNISWAP_V3_POOL_ABI,
    AERODROME_POOL_ABI,
    MULTICALL3_ADDRESS,
    TOKEN_DECIMALS,
    MIN_PROFIT_USD,
    SCAN_INTERVAL_MS,
)
from logger import ArbitrageLogger


class ArbitrageScanner:
    """Scanner untuk mendeteksi peluang arbitrase antar DEX di Base Network."""

    def __init__(self, logger: ArbitrageLogger):
        self.w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))
        self.logger = logger
        self.pool_cache = {}  # Cache pool addresses
        self._init_pools()

    def _init_pools(self):
        """Inisialisasi dan cache alamat pool untuk setiap pair."""
        self.logger.log_status("Initializing pool addresses...")

        uni_factory = self.w3.eth.contract(
            address=Web3.to_checksum_address(UNISWAP_V3_FACTORY),
            abi=UNISWAP_V3_FACTORY_ABI,
        )
        aero_factory = self.w3.eth.contract(
            address=Web3.to_checksum_address(AERODROME_SLIPSTREAM_FACTORY),
            abi=AERODROME_FACTORY_ABI,
        )

        for pair in PAIRS:
            pair_name = pair["name"]
            tokenA = Web3.to_checksum_address(pair["tokenA"])
            tokenB = Web3.to_checksum_address(pair["tokenB"])

            # Get Uniswap V3 pool
            try:
                uni_pool = uni_factory.functions.getPool(
                    tokenA, tokenB, pair["uniswap_fee"]
                ).call()
                if uni_pool == "0x0000000000000000000000000000000000000000":
                    uni_pool = None
            except Exception as e:
                self.logger.log_status(f"  [WARN] Uniswap pool not found for {pair_name}: {e}")
                uni_pool = None

            # Get Aerodrome Slipstream pool
            try:
                aero_pool = aero_factory.functions.getPool(
                    tokenA, tokenB, pair["aerodrome_tick_spacing"]
                ).call()
                if aero_pool == "0x0000000000000000000000000000000000000000":
                    aero_pool = None
            except Exception as e:
                self.logger.log_status(f"  [WARN] Aerodrome pool not found for {pair_name}: {e}")
                aero_pool = None

            self.pool_cache[pair_name] = {
                "uniswap": uni_pool,
                "aerodrome": aero_pool,
                "tokenA": tokenA,
                "tokenB": tokenB,
            }

            uni_status = f"✅ {uni_pool[:10]}..." if uni_pool else "❌ Not found"
            aero_status = f"✅ {aero_pool[:10]}..." if aero_pool else "❌ Not found"
            self.logger.log_status(f"  {pair_name}: Uniswap={uni_status} | Aerodrome={aero_status}")

    def get_prices_multicall(self):
        """
        Mengambil harga (sqrtPriceX96) dari semua pool menggunakan Multicall3.
        Mengembalikan dict dengan harga per pair per DEX.
        """
        calls = []
        call_map = []  # Track which call belongs to which pair/dex

        for pair in PAIRS:
            pair_name = pair["name"]
            pools = self.pool_cache.get(pair_name, {})

            # Uniswap pool slot0
            if pools.get("uniswap"):
                pool_contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(pools["uniswap"]),
                    abi=UNISWAP_V3_POOL_ABI,
                )
                calldata = pool_contract.encode_abi("slot0")
                calls.append((Web3.to_checksum_address(pools["uniswap"]), calldata))
                call_map.append({"pair": pair_name, "dex": "uniswap", "type": "slot0"})

            # Aerodrome pool slot0
            if pools.get("aerodrome"):
                pool_contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(pools["aerodrome"]),
                    abi=AERODROME_POOL_ABI,
                )
                calldata = pool_contract.encode_abi("slot0")
                calls.append((Web3.to_checksum_address(pools["aerodrome"]), calldata))
                call_map.append({"pair": pair_name, "dex": "aerodrome", "type": "slot0"})

        if not calls:
            return {}

        # Build Multicall3 aggregate call
        multicall_abi = [
            {
                "inputs": [
                    {
                        "components": [
                            {"name": "target", "type": "address"},
                            {"name": "callData", "type": "bytes"},
                        ],
                        "name": "calls",
                        "type": "tuple[]",
                    }
                ],
                "name": "aggregate",
                "outputs": [
                    {"name": "blockNumber", "type": "uint256"},
                    {"name": "returnData", "type": "bytes[]"},
                ],
                "stateMutability": "payable",
                "type": "function",
            }
        ]

        multicall = self.w3.eth.contract(
            address=Web3.to_checksum_address(MULTICALL3_ADDRESS),
            abi=multicall_abi,
        )

        try:
            block_number, return_data = multicall.functions.aggregate(
                [(addr, data) for addr, data in calls]
            ).call()
        except Exception as e:
            self.logger.log_status(f"[ERROR] Multicall failed: {e}")
            return {}

        # Parse results
        prices = {}
        for i, data in enumerate(return_data):
            info = call_map[i]
            pair_name = info["pair"]
            dex = info["dex"]

            if pair_name not in prices:
                prices[pair_name] = {}

            try:
                if dex == "uniswap":
                    # Uniswap V3 slot0: (sqrtPriceX96, tick, ...)
                    decoded = decode(
                        ["uint160", "int24", "uint16", "uint16", "uint16", "uint8", "bool"],
                        data,
                    )
                else:
                    # Aerodrome slot0: (sqrtPriceX96, tick, ...) - no feeProtocol
                    decoded = decode(
                        ["uint160", "int24", "uint16", "uint16", "uint16", "bool"],
                        data,
                    )

                sqrt_price_x96 = decoded[0]
                tick = decoded[1]

                prices[pair_name][dex] = {
                    "sqrtPriceX96": sqrt_price_x96,
                    "tick": tick,
                    "price": self._sqrt_price_to_price(sqrt_price_x96, pair_name),
                }
            except Exception as e:
                self.logger.log_status(f"[WARN] Failed to decode {pair_name}/{dex}: {e}")

        return prices

    def _sqrt_price_to_price(self, sqrt_price_x96, pair_name):
        """
        Convert sqrtPriceX96 ke harga yang readable.
        price = (sqrtPriceX96 / 2^96)^2 * 10^(decimals0 - decimals1)
        """
        if sqrt_price_x96 == 0:
            return 0

        # Find pair config
        pair_config = None
        for p in PAIRS:
            if p["name"] == pair_name:
                pair_config = p
                break

        if not pair_config:
            return 0

        tokenA = pair_config["tokenA"]
        tokenB = pair_config["tokenB"]

        # In Uniswap V3, token0 < token1 (sorted by address)
        if int(tokenA, 16) < int(tokenB, 16):
            decimals0 = TOKEN_DECIMALS.get(tokenA, 18)
            decimals1 = TOKEN_DECIMALS.get(tokenB, 18)
        else:
            decimals0 = TOKEN_DECIMALS.get(tokenB, 18)
            decimals1 = TOKEN_DECIMALS.get(tokenA, 18)

        price = (sqrt_price_x96 / (2**96)) ** 2
        # Adjust for decimals
        price = price * (10 ** (decimals0 - decimals1))

        return price

    def find_opportunities(self, prices):
        """
        Analisis harga dan temukan peluang arbitrase.
        Returns list of opportunities.
        """
        opportunities = []

        for pair_name, dex_prices in prices.items():
            if "uniswap" not in dex_prices or "aerodrome" not in dex_prices:
                continue

            uni_price = dex_prices["uniswap"]["price"]
            aero_price = dex_prices["aerodrome"]["price"]

            if uni_price == 0 or aero_price == 0:
                continue

            # Calculate price difference percentage
            price_diff_pct = abs(uni_price - aero_price) / min(uni_price, aero_price) * 100

            # Determine direction
            if uni_price > aero_price:
                # Buy on Aerodrome (cheaper), sell on Uniswap (more expensive)
                direction = "Aerodrome->Uniswap"
                buy_price = aero_price
                sell_price = uni_price
            else:
                # Buy on Uniswap (cheaper), sell on Aerodrome (more expensive)
                direction = "Uniswap->Aerodrome"
                buy_price = uni_price
                sell_price = aero_price

            # Estimate profit (simplified - actual profit depends on amount and slippage)
            # For a $20 trade, estimate gross profit
            estimated_profit_pct = price_diff_pct - 0.1  # Subtract ~0.1% for fees (0.05% each side)

            # Log scan result
            is_profitable = estimated_profit_pct > 0.05  # At least 0.05% net profit
            self.logger.log_scan(pair_name, price_diff_pct, is_profitable)

            if is_profitable:
                opportunities.append({
                    "pair": pair_name,
                    "direction": direction,
                    "uni_price": uni_price,
                    "aero_price": aero_price,
                    "price_diff_pct": price_diff_pct,
                    "estimated_profit_pct": estimated_profit_pct,
                    "uni_sqrtPriceX96": dex_prices["uniswap"]["sqrtPriceX96"],
                    "aero_sqrtPriceX96": dex_prices["aerodrome"]["sqrtPriceX96"],
                })

        # Sort by profit potential (highest first)
        opportunities.sort(key=lambda x: x["estimated_profit_pct"], reverse=True)
        return opportunities

    def scan_once(self):
        """Lakukan satu kali scan dan return opportunities."""
        prices = self.get_prices_multicall()
        if not prices:
            return []
        return self.find_opportunities(prices)

    def run_continuous(self, callback=None):
        """
        Jalankan scanner secara terus-menerus.
        callback: fungsi yang dipanggil saat ada opportunity (untuk executor).
        """
        self.logger.log_status(f"Scanner started. Interval: {SCAN_INTERVAL_MS}ms")
        self.logger.log_status(f"Monitoring {len(PAIRS)} pairs across Uniswap V3 & Aerodrome")

        scan_count = 0
        while True:
            try:
                scan_count += 1
                opportunities = self.scan_once()

                if opportunities and callback:
                    for opp in opportunities:
                        callback(opp)

                # Sleep between scans
                time.sleep(SCAN_INTERVAL_MS / 1000.0)

                # Periodic status update every 100 scans
                if scan_count % 100 == 0:
                    self.logger.log_status(f"Scan #{scan_count} complete. Block: {self.w3.eth.block_number}")

            except KeyboardInterrupt:
                self.logger.log_status("Scanner stopped by user.")
                break
            except Exception as e:
                self.logger.log_status(f"[ERROR] Scanner error: {e}")
                time.sleep(5)  # Wait 5s before retry on error
