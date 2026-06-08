"""
DeFi91 Arbitrage Engine - Scanner
Memantau harga real-time via multicall dan mendeteksi peluang arbitrase.
Includes RPC fallback and retry logic to avoid 429 rate limiting.
"""

import time
import math
import random
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


# Multiple free RPC endpoints for Base Mainnet (fallback rotation)
RPC_ENDPOINTS = [
    BASE_RPC_URL,
    "https://base.llamarpc.com",
    "https://base-mainnet.public.blastapi.io",
    "https://1rpc.io/base",
    "https://base.meowrpc.com",
    "https://base.drpc.org",
]


class ArbitrageScanner:
    """Scanner untuk mendeteksi peluang arbitrase antar DEX di Base Network."""

    def __init__(self, logger: ArbitrageLogger):
        self.logger = logger
        self.rpc_index = 0
        self.w3 = self._create_web3(RPC_ENDPOINTS[0])
        self.pool_cache = {}
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
        self._init_pools()

    def _create_web3(self, rpc_url):
        """Create Web3 instance with given RPC URL."""
        return Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))

    def _rotate_rpc(self):
        """Rotate to next RPC endpoint on error."""
        self.rpc_index = (self.rpc_index + 1) % len(RPC_ENDPOINTS)
        new_rpc = RPC_ENDPOINTS[self.rpc_index]
        self.w3 = self._create_web3(new_rpc)
        self.logger.log_status(f"[RPC] Rotated to: {new_rpc}")
        return new_rpc

    def _call_with_retry(self, func, max_retries=3):
        """Execute a Web3 call with retry and RPC rotation on failure."""
        for attempt in range(max_retries):
            try:
                result = func()
                self.consecutive_errors = 0
                return result
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "Too Many Requests" in error_str:
                    self._rotate_rpc()
                    time.sleep(1 + attempt * 0.5)
                elif "timeout" in error_str.lower():
                    self._rotate_rpc()
                    time.sleep(0.5)
                else:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(0.5)
        return None

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
                uni_pool = self._call_with_retry(
                    lambda tA=tokenA, tB=tokenB, fee=pair["uniswap_fee"]:
                        uni_factory.functions.getPool(tA, tB, fee).call()
                )
                if uni_pool == "0x0000000000000000000000000000000000000000":
                    uni_pool = None
            except Exception as e:
                self.logger.log_status(f"  [WARN] Uniswap pool not found for {pair_name}: {e}")
                uni_pool = None

            # Get Aerodrome Slipstream pool
            try:
                aero_pool = self._call_with_retry(
                    lambda tA=tokenA, tB=tokenB, ts=pair["aerodrome_tick_spacing"]:
                        aero_factory.functions.getPool(tA, tB, ts).call()
                )
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
        """Mengambil harga dari semua pool menggunakan Multicall3."""
        calls = []
        call_map = []

        for pair in PAIRS:
            pair_name = pair["name"]
            pools = self.pool_cache.get(pair_name, {})

            if pools.get("uniswap"):
                pool_contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(pools["uniswap"]),
                    abi=UNISWAP_V3_POOL_ABI,
                )
                calldata = pool_contract.encode_abi("slot0")
                calls.append((Web3.to_checksum_address(pools["uniswap"]), calldata))
                call_map.append({"pair": pair_name, "dex": "uniswap", "type": "slot0"})

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
            result = self._call_with_retry(
                lambda: multicall.functions.aggregate(
                    [(addr, data) for addr, data in calls]
                ).call()
            )
            if result is None:
                return {}
            block_number, return_data = result
        except Exception as e:
            self.logger.log_status(f"[ERROR] Multicall failed: {e}")
            self.consecutive_errors += 1
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
                    decoded = decode(
                        ["uint160", "int24", "uint16", "uint16", "uint16", "uint8", "bool"],
                        data,
                    )
                else:
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
        """Convert sqrtPriceX96 ke harga yang readable."""
        if sqrt_price_x96 == 0:
            return 0

        pair_config = None
        for p in PAIRS:
            if p["name"] == pair_name:
                pair_config = p
                break

        if not pair_config:
            return 0

        tokenA = pair_config["tokenA"]
        tokenB = pair_config["tokenB"]

        if int(tokenA, 16) < int(tokenB, 16):
            decimals0 = TOKEN_DECIMALS.get(tokenA, 18)
            decimals1 = TOKEN_DECIMALS.get(tokenB, 18)
        else:
            decimals0 = TOKEN_DECIMALS.get(tokenB, 18)
            decimals1 = TOKEN_DECIMALS.get(tokenA, 18)

        price = (sqrt_price_x96 / (2**96)) ** 2
        price = price * (10 ** (decimals0 - decimals1))

        return price

    def find_opportunities(self, prices):
        """Analisis harga dan temukan peluang arbitrase."""
        opportunities = []

        for pair_name, dex_prices in prices.items():
            if "uniswap" not in dex_prices or "aerodrome" not in dex_prices:
                continue

            uni_price = dex_prices["uniswap"]["price"]
            aero_price = dex_prices["aerodrome"]["price"]

            if uni_price == 0 or aero_price == 0:
                continue

            price_diff_pct = abs(uni_price - aero_price) / min(uni_price, aero_price) * 100

            if uni_price > aero_price:
                direction = "Aerodrome->Uniswap"
            else:
                direction = "Uniswap->Aerodrome"

            estimated_profit_pct = price_diff_pct - 0.1

            is_profitable = estimated_profit_pct > 0.05
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

        opportunities.sort(key=lambda x: x["estimated_profit_pct"], reverse=True)
        return opportunities

    def scan_once(self):
        """Lakukan satu kali scan dan return opportunities."""
        prices = self.get_prices_multicall()
        if not prices:
            return []
        return self.find_opportunities(prices)

    def run_continuous(self, callback=None):
        """Jalankan scanner secara terus-menerus dengan adaptive interval."""
        # Use minimum 2 seconds interval to avoid rate limiting on free RPCs
        effective_interval = max(SCAN_INTERVAL_MS, 2000)
        self.logger.log_status(f"Scanner started. Interval: {effective_interval}ms (min 2s)")
        self.logger.log_status(f"Monitoring {len(PAIRS)} pairs across Uniswap V3 & Aerodrome")
        self.logger.log_status(f"RPC endpoints available: {len(RPC_ENDPOINTS)}")

        scan_count = 0
        while True:
            try:
                scan_count += 1
                opportunities = self.scan_once()

                if opportunities and callback:
                    for opp in opportunities:
                        callback(opp)

                # Adaptive sleep
                if self.consecutive_errors > 0:
                    sleep_time = min(
                        effective_interval / 1000.0 * (2 ** self.consecutive_errors),
                        30.0
                    )
                else:
                    sleep_time = effective_interval / 1000.0 + random.uniform(0, 0.5)

                time.sleep(sleep_time)

                # Periodic status every 50 scans
                if scan_count % 50 == 0:
                    try:
                        block = self._call_with_retry(lambda: self.w3.eth.block_number)
                        self.logger.log_status(
                            f"Scan #{scan_count} complete. Block: {block} | "
                            f"RPC: {RPC_ENDPOINTS[self.rpc_index][:30]}..."
                        )
                    except Exception:
                        self.logger.log_status(f"Scan #{scan_count} complete.")

            except KeyboardInterrupt:
                self.logger.log_status("Scanner stopped by user.")
                break
            except Exception as e:
                self.consecutive_errors += 1
                self.logger.log_status(f"[ERROR] Scanner error: {e}")
                if self.consecutive_errors >= self.max_consecutive_errors:
                    self._rotate_rpc()
                    self.consecutive_errors = 0
                time.sleep(5)
