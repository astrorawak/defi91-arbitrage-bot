const { ethers } = require("hardhat");

async function main() {
  console.log("=================================================");
  console.log("  DeFi91 Arbitrage Engine - Deployment Script");
  console.log("=================================================");

  const [deployer] = await ethers.getSigners();
  const balance = await ethers.provider.getBalance(deployer.address);

  console.log("\n[INFO] Deployer address:", deployer.address);
  console.log("[INFO] Deployer balance:", ethers.formatEther(balance), "ETH");
  console.log("[INFO] Network: Base Mainnet (Chain ID: 8453)");
  console.log("\n[DEPLOY] Deploying ArbitrageExecutor...");

  const ArbitrageExecutor = await ethers.getContractFactory("ArbitrageExecutor");
  const contract = await ArbitrageExecutor.deploy({
    gasLimit: 2000000,
  });

  await contract.waitForDeployment();
  const contractAddress = await contract.getAddress();

  console.log("\n✅ ArbitrageExecutor deployed successfully!");
  console.log("📍 Contract Address:", contractAddress);
  console.log("🔗 BaseScan:", `https://basescan.org/address/${contractAddress}`);
  console.log("\n[INFO] Owner:", deployer.address);
  console.log("[INFO] UNISWAP_V3_ROUTER:", await contract.UNISWAP_V3_ROUTER());
  console.log("[INFO] AERODROME_ROUTER:", await contract.AERODROME_ROUTER());
  console.log("[INFO] WETH:", await contract.WETH());
  console.log("[INFO] USDC:", await contract.USDC());
  console.log("\n=================================================");
  console.log("  SAVE THIS CONTRACT ADDRESS!");
  console.log("  CONTRACT_ADDRESS=" + contractAddress);
  console.log("=================================================");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("[ERROR]", error);
    process.exit(1);
  });
