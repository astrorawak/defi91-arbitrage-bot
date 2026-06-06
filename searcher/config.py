"""
DeFi91 Arbitrage Engine - Configuration
Owner: Karman
Network: Base Network (Chain ID: 8453)
"""

import os

# ============ NETWORK ============
CHAIN_ID = 8453
BASE_RPC_URL = os.environ.get("BASE_RPC_URL", "https://mainnet.base.org")
BASE_WSS_URL = os.environ.get("BASE_WSS_URL", "")  # WebSocket for real-time blocks

# ============ WALLET ============
PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "")
ARBITRAGE_CONTRACT = os.environ.get("ARBITRAGE_CONTRACT", "")

# ============ DEX ROUTERS ============
UNISWAP_V3_ROUTER = "0x2626664c2603336E57B271c5C0b26F421741e481"
UNISWAP_V3_QUOTER = "0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a"
UNISWAP_V3_FACTORY = "0x33128a8fC17869897dcE68Ed026d694621f6FDfD"

AERODROME_SLIPSTREAM_ROUTER = "0xBE6D8f0d05cC4be24d5167a3eF062215bE6D18a5"
AERODROME_SLIPSTREAM_FACTORY = "0x5e7BB104d84c7CB9B682AaC2F3d509f5F406809A"
AERODROME_SLIPSTREAM_QUOTER = "0x254cF9E1E6e233aa1AC962CB9B05b2cfeAaE15b0"

# ============ TOKENS ============
WETH = "0x4200000000000000000000000000000000000006"
USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
CBBTC = "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf"

# Token decimals
TOKEN_DECIMALS = {
    WETH: 18,
    USDC: 6,
    CBBTC: 8,
}

# ============ TRADING PAIRS ============
# Each pair: (tokenA, tokenB, uniswap_fee, aerodrome_tick_spacing)
# Uniswap V3 fees: 100 (0.01%), 500 (0.05%), 3000 (0.3%), 10000 (1%)
# Aerodrome tick spacings: 1, 50, 100, 200
PAIRS = [
    {
        "name": "WETH/USDC",
        "tokenA": WETH,
        "tokenB": USDC,
        "uniswap_fee": 500,       # 0.05% fee tier (highest liquidity)
        "aerodrome_tick_spacing": 100,
    },
    {
        "name": "WETH/USDC_3000",
        "tokenA": WETH,
        "tokenB": USDC,
        "uniswap_fee": 3000,      # 0.3% fee tier
        "aerodrome_tick_spacing": 100,
    },
    {
        "name": "cbBTC/USDC",
        "tokenA": CBBTC,
        "tokenB": USDC,
        "uniswap_fee": 3000,
        "aerodrome_tick_spacing": 200,
    },
    {
        "name": "WETH/cbBTC",
        "tokenA": WETH,
        "tokenB": CBBTC,
        "uniswap_fee": 500,
        "aerodrome_tick_spacing": 50,
    },
]

# ============ BOT PARAMETERS ============
MIN_PROFIT_USD = float(os.environ.get("MIN_PROFIT_USD", "0.50"))  # Minimum profit in USD
MAX_GAS_GWEI = float(os.environ.get("MAX_GAS_GWEI", "0.5"))      # Max gas price (Base is cheap)
SCAN_INTERVAL_MS = int(os.environ.get("SCAN_INTERVAL_MS", "500"))  # Scan every 500ms
PRIORITY_FEE_GWEI = float(os.environ.get("PRIORITY_FEE_GWEI", "0.01"))  # Priority fee

# Slippage tolerance (0.5% = 50 basis points)
SLIPPAGE_BPS = int(os.environ.get("SLIPPAGE_BPS", "50"))

# ============ DRY RUN MODE ============
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"

# ============ LOGGING ============
LOG_FILE = os.environ.get("LOG_FILE", "trades_log.json")
DASHBOARD_DATA_FILE = os.environ.get("DASHBOARD_DATA_FILE", "dashboard/data.json")

# ============ MULTICALL ============
MULTICALL3_ADDRESS = "0xcA11bde05977b3631167028862bE2a173976CA11"

# ============ ABI SNIPPETS ============
# Uniswap V3 Pool slot0
UNISWAP_V3_POOL_ABI = [
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
            {"internalType": "int24", "name": "tick", "type": "int24"},
            {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
            {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
            {"internalType": "bool", "name": "unlocked", "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "liquidity",
        "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "token0",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "token1",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# Aerodrome Slipstream Pool slot0 (slightly different from Uniswap V3)
AERODROME_POOL_ABI = [
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
            {"internalType": "int24", "name": "tick", "type": "int24"},
            {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
            {"internalType": "bool", "name": "unlocked", "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "liquidity",
        "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "token0",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "token1",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# Uniswap V3 Factory getPool
UNISWAP_V3_FACTORY_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "tokenA", "type": "address"},
            {"internalType": "address", "name": "tokenB", "type": "address"},
            {"internalType": "uint24", "name": "fee", "type": "uint24"},
        ],
        "name": "getPool",
        "outputs": [{"internalType": "address", "name": "pool", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    }
]

# Aerodrome Slipstream Factory getPool
AERODROME_FACTORY_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "tokenA", "type": "address"},
            {"internalType": "address", "name": "tokenB", "type": "address"},
            {"internalType": "int24", "name": "tickSpacing", "type": "int24"},
        ],
        "name": "getPool",
        "outputs": [{"internalType": "address", "name": "pool", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    }
]

# QuoterV2 ABI (for quoting exact output)
QUOTER_V2_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"},
                ],
                "internalType": "struct IQuoterV2.QuoteExactInputSingleParams",
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "quoteExactInputSingle",
        "outputs": [
            {"internalType": "uint256", "name": "amountOut", "type": "uint256"},
            {"internalType": "uint160", "name": "sqrtPriceX96After", "type": "uint160"},
            {"internalType": "uint32", "name": "initializedTicksCrossed", "type": "uint32"},
            {"internalType": "uint256", "name": "gasEstimate", "type": "uint256"},
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

# SwapRouter02 exactInputSingle ABI
SWAP_ROUTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "address", "name": "recipient", "type": "address"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"},
                    {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"},
                ],
                "internalType": "struct IV3SwapRouter.ExactInputSingleParams",
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "exactInputSingle",
        "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function",
    }
]

# Aerodrome SwapRouter exactInputSingle ABI
AERODROME_SWAP_ROUTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "int24", "name": "tickSpacing", "type": "int24"},
                    {"internalType": "address", "name": "recipient", "type": "address"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"},
                    {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"},
                ],
                "internalType": "struct ICLRouter.ExactInputSingleParams",
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "exactInputSingle",
        "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function",
    }
]
