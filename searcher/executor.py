"""
DeFi91 Arbitrage Engine - Executor
Membangun dan mengirim transaksi arbitrase ke smart contract.
"""

import time
import json
from datetime import datetime, timezone
from web3 import Web3
from eth_abi import encode

from config import (
    BASE_RPC_URL,
    PRIVATE_KEY,
    ARBITRAGE_CONTRACT,
    UNISWAP_V3_ROUTER,
    AERODROME_SLIPSTREAM_ROUTER,
    UNISWAP_V3_FACTORY,
    AERODROME_SLIPSTREAM_FACTORY,
    WETH,
    USDC,
    TOKEN_DECIMALS,
    PAIRS,
    MAX_GAS_GWEI,
    PRIORITY_FEE_GWEI,
    SLIPPAGE_BPS,
    MIN_PROFIT_USD,
    DRY_RUN,
    SWAP_ROUTER_ABI,
    AERODROME_SWAP_ROUTER_ABI,
)
from logger import ArbitrageLogger


# ArbitrageExecutor contract ABI (minimal for executeArbitrage)
ARBITRAGE_EXECUTOR_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "tokenIn", "type": "address"},
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {
                "components": [
                    {"internalType": "address", "name": "router", "type": "address"},
                    {"internalType": "bytes", "name": "swapData", "type": "bytes"},
                ],
                "internalType": "struct ArbitrageExecutor.SwapParams[]",
                "name": "swaps",
                "type": "tuple[]",
            },
            {"internalType": "uint256", "name": "minProfit", "type": "uint256"},
        ],
        "name": "executeArbitrage",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "token", "type": "address"}],
        "name": "getBalance",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class ArbitrageExecutor:
    """Executor untuk mengirim transaksi arbitrase ke smart contract."""

    def __init__(self, logger: ArbitrageLogger):
        self.w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))
        self.logger = logger
        self.account = None
        self.contract = None
        self._init_account()

    def _init_account(self):
        """Inisialisasi wallet dan contract."""
        if not PRIVATE_KEY:
            self.logger.log_status("[WARN] No PRIVATE_KEY set. Running in view-only mode.")
            return

        self.account = self.w3.eth.account.from_key(PRIVATE_KEY)
        self.logger.log_status(f"Wallet: {self.account.address}")

        if ARBITRAGE_CONTRACT:
            self.contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(ARBITRAGE_CONTRACT),
                abi=ARBITRAGE_EXECUTOR_ABI,
            )
            self.logger.log_status(f"Contract: {ARBITRAGE_CONTRACT}")
        else:
            self.logger.log_status("[WARN] No ARBITRAGE_CONTRACT set.")

    def get_contract_balance(self, token_address):
        """Get token balance of the arbitrage contract."""
        if not self.contract:
            return 0
        try:
            balance = self.contract.functions.getBalance(
                Web3.to_checksum_address(token_address)
            ).call()
            return balance
        except Exception as e:
            self.logger.log_status(f"[ERROR] Failed to get balance: {e}")
            return 0

    def execute_opportunity(self, opportunity):
        """
        Eksekusi peluang arbitrase yang ditemukan oleh scanner.
        
        opportunity: dict dari scanner.find_opportunities()
        """
        pair_name = opportunity["pair"]
        direction = opportunity["direction"]
        price_diff = opportunity["price_diff_pct"]

        self.logger.log_status(
            f"[EXEC] Processing: {pair_name} | {direction} | Diff: {price_diff:.4f}%"
        )

        # Determine token and amount
        pair_config = self._get_pair_config(pair_name)
        if not pair_config:
            self.logger.log_error({"pair": pair_name, "reason": "Pair config not found"})
            return False

        # Determine which token to use as base (tokenIn)
        token_in = pair_config["tokenA"]  # Usually WETH or cbBTC
        token_out = pair_config["tokenB"]  # Usually USDC

        # Get available balance in contract
        balance = self.get_contract_balance(token_in)
        decimals = TOKEN_DECIMALS.get(token_in, 18)

        if balance == 0:
            self.logger.log_error({"pair": pair_name, "reason": f"No balance for {token_in}"})
            return False

        # Use a portion of balance (max 50% per trade for safety)
        amount_in = min(balance, balance // 2)

        if amount_in == 0:
            self.logger.log_error({"pair": pair_name, "reason": "Amount too small"})
            return False

        # Build swap calldata based on direction
        try:
            swaps = self._build_swap_params(
                direction, pair_config, token_in, token_out, amount_in
            )
        except Exception as e:
            self.logger.log_error({"pair": pair_name, "reason": f"Failed to build swaps: {e}"})
            return False

        # Calculate minimum profit (in token_in units)
        # MIN_PROFIT_USD converted to token units
        min_profit = self._usd_to_token_amount(MIN_PROFIT_USD, token_in)

        # DRY RUN mode - simulate only
        if DRY_RUN:
            self.logger.log_status(
                f"[DRY RUN] Would execute: {pair_name} | {direction} | "
                f"Amount: {amount_in / 10**decimals:.6f} | MinProfit: {min_profit}"
            )
            # Log as simulated trade
            self.logger.log_trade({
                "pair": pair_name,
                "direction": direction,
                "amount_in": amount_in / 10**decimals,
                "amount_out": 0,
                "profit_usd": price_diff * 0.01 * (amount_in / 10**decimals),  # Estimated
                "gas_used": 0,
                "gas_cost_usd": 0,
                "tx_hash": "0x_DRY_RUN_SIMULATED",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return True

        # LIVE EXECUTION
        return self._send_transaction(
            token_in, amount_in, swaps, min_profit, pair_name, direction
        )

    def _build_swap_params(self, direction, pair_config, token_in, token_out, amount_in):
        """
        Build swap parameters for the arbitrage contract.
        Returns list of (router, calldata) tuples.
        """
        uniswap_fee = pair_config["uniswap_fee"]
        aero_tick_spacing = pair_config["aerodrome_tick_spacing"]

        # Calculate minimum amount out with slippage
        # For simplicity, we set amountOutMinimum to 1 (the contract's require handles safety)
        amount_out_min = 1

        if direction == "Uniswap->Aerodrome":
            # Step 1: Swap tokenIn -> tokenOut on Uniswap V3
            swap1_data = self._encode_uniswap_swap(
                token_in, token_out, uniswap_fee, amount_in, amount_out_min
            )
            # Step 2: Swap tokenOut -> tokenIn on Aerodrome
            swap2_data = self._encode_aerodrome_swap(
                token_out, token_in, aero_tick_spacing, 0, amount_out_min  # 0 = use all received
            )
            return [
                (UNISWAP_V3_ROUTER, swap1_data),
                (AERODROME_SLIPSTREAM_ROUTER, swap2_data),
            ]
        else:
            # direction == "Aerodrome->Uniswap"
            # Step 1: Swap tokenIn -> tokenOut on Aerodrome
            swap1_data = self._encode_aerodrome_swap(
                token_in, token_out, aero_tick_spacing, amount_in, amount_out_min
            )
            # Step 2: Swap tokenOut -> tokenIn on Uniswap V3
            swap2_data = self._encode_uniswap_swap(
                token_out, token_in, uniswap_fee, 0, amount_out_min  # 0 = use all received
            )
            return [
                (AERODROME_SLIPSTREAM_ROUTER, swap1_data),
                (UNISWAP_V3_ROUTER, swap2_data),
            ]

    def _encode_uniswap_swap(self, token_in, token_out, fee, amount_in, amount_out_min):
        """Encode Uniswap V3 exactInputSingle calldata."""
        # Use contract ABI to encode
        router = self.w3.eth.contract(
            address=Web3.to_checksum_address(UNISWAP_V3_ROUTER),
            abi=SWAP_ROUTER_ABI,
        )
        calldata = router.encode_abi("exactInputSingle", [{
            "tokenIn": Web3.to_checksum_address(token_in),
            "tokenOut": Web3.to_checksum_address(token_out),
            "fee": fee,
            "recipient": Web3.to_checksum_address(ARBITRAGE_CONTRACT),
            "amountIn": amount_in,
            "amountOutMinimum": amount_out_min,
            "sqrtPriceLimitX96": 0,
        }])
        return bytes.fromhex(calldata[2:]) if calldata.startswith("0x") else bytes.fromhex(calldata)

    def _encode_aerodrome_swap(self, token_in, token_out, tick_spacing, amount_in, amount_out_min):
        """Encode Aerodrome Slipstream exactInputSingle calldata."""
        router = self.w3.eth.contract(
            address=Web3.to_checksum_address(AERODROME_SLIPSTREAM_ROUTER),
            abi=AERODROME_SWAP_ROUTER_ABI,
        )
        deadline = int(time.time()) + 300  # 5 minutes
        calldata = router.encode_abi("exactInputSingle", [{
            "tokenIn": Web3.to_checksum_address(token_in),
            "tokenOut": Web3.to_checksum_address(token_out),
            "tickSpacing": tick_spacing,
            "recipient": Web3.to_checksum_address(ARBITRAGE_CONTRACT),
            "deadline": deadline,
            "amountIn": amount_in,
            "amountOutMinimum": amount_out_min,
            "sqrtPriceLimitX96": 0,
        }])
        return bytes.fromhex(calldata[2:]) if calldata.startswith("0x") else bytes.fromhex(calldata)

    def _send_transaction(self, token_in, amount_in, swaps, min_profit, pair_name, direction):
        """Build and send the arbitrage transaction."""
        if not self.contract or not self.account:
            self.logger.log_error({"pair": pair_name, "reason": "Contract or account not initialized"})
            return False

        try:
            # Check gas price
            gas_price = self.w3.eth.gas_price
            max_gas_wei = Web3.to_wei(MAX_GAS_GWEI, "gwei")
            if gas_price > max_gas_wei:
                self.logger.log_status(
                    f"[SKIP] Gas too high: {Web3.from_wei(gas_price, 'gwei'):.4f} gwei > {MAX_GAS_GWEI} gwei"
                )
                return False

            # Build transaction
            swap_params = [(Web3.to_checksum_address(router), data) for router, data in swaps]

            tx = self.contract.functions.executeArbitrage(
                Web3.to_checksum_address(token_in),
                amount_in,
                swap_params,
                min_profit,
            ).build_transaction({
                "from": self.account.address,
                "nonce": self.w3.eth.get_transaction_count(self.account.address),
                "gas": 500000,  # Estimate, will be adjusted
                "maxFeePerGas": gas_price + Web3.to_wei(PRIORITY_FEE_GWEI, "gwei"),
                "maxPriorityFeePerGas": Web3.to_wei(PRIORITY_FEE_GWEI, "gwei"),
                "chainId": 8453,
            })

            # Estimate gas
            try:
                estimated_gas = self.w3.eth.estimate_gas(tx)
                tx["gas"] = int(estimated_gas * 1.2)  # 20% buffer
            except Exception as e:
                # If estimation fails, the tx would likely revert (no profit)
                self.logger.log_error({
                    "pair": pair_name,
                    "reason": f"Gas estimation failed (likely no profit): {e}",
                })
                return False

            # Sign and send
            signed_tx = self.w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            self.logger.log_status(f"[TX SENT] {tx_hash.hex()}")

            # Wait for receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

            if receipt["status"] == 1:
                # Success!
                gas_used = receipt["gasUsed"]
                gas_cost_eth = gas_used * gas_price / 10**18
                gas_cost_usd = gas_cost_eth * self._get_eth_price_estimate()

                decimals = TOKEN_DECIMALS.get(token_in, 18)
                self.logger.log_trade({
                    "pair": pair_name,
                    "direction": direction,
                    "amount_in": amount_in / 10**decimals,
                    "amount_out": 0,  # Would need to parse logs for exact amount
                    "profit_usd": MIN_PROFIT_USD,  # Conservative estimate
                    "gas_used": gas_used,
                    "gas_cost_usd": gas_cost_usd,
                    "tx_hash": tx_hash.hex(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return True
            else:
                # Reverted (should be rare due to gas estimation check)
                self.logger.log_error({
                    "pair": pair_name,
                    "reason": f"TX reverted: {tx_hash.hex()}",
                })
                return False

        except Exception as e:
            self.logger.log_error({
                "pair": pair_name,
                "reason": f"Execution error: {str(e)}",
            })
            return False

    def _get_pair_config(self, pair_name):
        """Get pair configuration by name."""
        for pair in PAIRS:
            if pair["name"] == pair_name:
                return pair
        return None

    def _usd_to_token_amount(self, usd_amount, token_address):
        """Convert USD amount to token units (rough estimate)."""
        # Rough price estimates for calculation
        if token_address.lower() == WETH.lower():
            eth_price = self._get_eth_price_estimate()
            return int((usd_amount / eth_price) * 10**18)
        elif token_address.lower() == USDC.lower():
            return int(usd_amount * 10**6)
        else:
            # Default: assume $1 = 1 token unit
            decimals = TOKEN_DECIMALS.get(token_address, 18)
            return int(usd_amount * 10**decimals)

    def _get_eth_price_estimate(self):
        """Get rough ETH price estimate (from config or hardcoded fallback)."""
        # In production, this would query an oracle or use the WETH/USDC pool price
        # For now, use a reasonable estimate
        return 1600.0  # Will be updated dynamically in production
