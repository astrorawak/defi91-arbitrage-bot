from web3 import Web3
from eth_abi import encode, decode
import json

print("web3 imported OK")
print("eth_abi imported OK")

# Quick test
w3 = Web3(Web3.HTTPProvider("https://mainnet.base.org"))
print(f"Connected to Base: {w3.is_connected()}")
if w3.is_connected():
    block = w3.eth.block_number
    print(f"Current block: {block}")
print("All imports and connection OK!")
