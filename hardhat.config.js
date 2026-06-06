require("@nomicfoundation/hardhat-toolbox");

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.24",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
      viaIR: true,
    },
  },
  networks: {
    hardhat: {
      chainId: 8453,
    },
    base: {
      url: "https://mainnet.base.org",
      accounts: ["0x8afd4ca004bc063d1fd556368ba3a97874efa38da94bec7086f4d4a4d733964c"],
      chainId: 8453,
      gasPrice: "auto",
    },
  },
};
