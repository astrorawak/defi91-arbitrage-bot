// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

/// @title DeFi91 Arbitrage Executor
/// @author Karman (DeFi91)
/// @notice Atomic arbitrage executor for Base Network - supports Uniswap V3 and Aerodrome Slipstream
/// @dev All arbitrage executions are atomic: if no profit, the transaction reverts automatically.
contract ArbitrageExecutor is Ownable, ReentrancyGuard, Pausable {
    using SafeERC20 for IERC20;

    // ============ EVENTS ============
    event ArbitrageExecuted(
        address indexed tokenIn,
        uint256 amountIn,
        uint256 profit,
        uint256 timestamp
    );
    event TokenWithdrawn(address indexed token, uint256 amount);
    event ETHWithdrawn(uint256 amount);

    // ============ ERRORS ============
    error NoProfitRealized();
    error InsufficientBalance();
    error SwapFailed(uint8 step);
    error InvalidPath();

    // ============ STRUCTS ============
    struct SwapParams {
        address router;       // DEX router address
        bytes swapData;       // Encoded swap calldata
    }

    // ============ CONSTANTS ============
    // Uniswap V3 SwapRouter02 on Base
    address public constant UNISWAP_V3_ROUTER = 0x2626664c2603336E57B271c5C0b26F421741e481;
    // Aerodrome Slipstream SwapRouter on Base
    address public constant AERODROME_ROUTER = 0xBE6D8f0d05cC4be24d5167a3eF062215bE6D18a5;
    // WETH on Base
    address public constant WETH = 0x4200000000000000000000000000000000000006;
    // USDC on Base (Native)
    address public constant USDC = 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913;

    // ============ CONSTRUCTOR ============
    constructor() Ownable(msg.sender) {
        // Pre-approve routers for WETH and USDC to save gas on future swaps
        IERC20(WETH).approve(UNISWAP_V3_ROUTER, type(uint256).max);
        IERC20(WETH).approve(AERODROME_ROUTER, type(uint256).max);
        IERC20(USDC).approve(UNISWAP_V3_ROUTER, type(uint256).max);
        IERC20(USDC).approve(AERODROME_ROUTER, type(uint256).max);
    }

    // ============ CORE FUNCTIONS ============

    /// @notice Execute atomic arbitrage with multiple swaps
    /// @param tokenIn The token to start and end with (profit token)
    /// @param amountIn Amount of tokenIn to use
    /// @param swaps Array of swap operations to execute sequentially
    /// @param minProfit Minimum profit required (in tokenIn units) - extra safety
    function executeArbitrage(
        address tokenIn,
        uint256 amountIn,
        SwapParams[] calldata swaps,
        uint256 minProfit
    ) external onlyOwner nonReentrant whenNotPaused {
        // Validate inputs
        if (swaps.length < 2) revert InvalidPath();
        
        // Record balance before
        uint256 balanceBefore = IERC20(tokenIn).balanceOf(address(this));
        if (balanceBefore < amountIn) revert InsufficientBalance();

        // Execute each swap in sequence
        for (uint8 i = 0; i < swaps.length; i++) {
            (bool success, ) = swaps[i].router.call(swaps[i].swapData);
            if (!success) revert SwapFailed(i);
        }

        // Record balance after
        uint256 balanceAfter = IERC20(tokenIn).balanceOf(address(this));

        // CRITICAL: Atomic profit check - reverts entire transaction if no profit
        if (balanceAfter <= balanceBefore) revert NoProfitRealized();
        
        uint256 profit = balanceAfter - balanceBefore;
        
        // Extra safety: ensure minimum profit threshold is met
        if (profit < minProfit) revert NoProfitRealized();

        emit ArbitrageExecuted(tokenIn, amountIn, profit, block.timestamp);
    }

    /// @notice Approve a token for a specific router (for new pairs)
    /// @param token Token address to approve
    /// @param router Router address to approve for
    function approveToken(
        address token,
        address router
    ) external onlyOwner {
        IERC20(token).approve(router, type(uint256).max);
    }

    /// @notice Revoke approval for a token/router pair
    /// @param token Token address
    /// @param router Router address
    function revokeApproval(
        address token,
        address router
    ) external onlyOwner {
        IERC20(token).approve(router, 0);
    }

    // ============ EMERGENCY FUNCTIONS ============

    /// @notice Pause the contract (emergency stop)
    function pause() external onlyOwner {
        _pause();
    }

    /// @notice Unpause the contract
    function unpause() external onlyOwner {
        _unpause();
    }

    /// @notice Withdraw ERC20 tokens from contract
    /// @param token Token address to withdraw
    /// @param amount Amount to withdraw
    function withdrawToken(
        address token,
        uint256 amount
    ) external onlyOwner {
        uint256 balance = IERC20(token).balanceOf(address(this));
        if (amount > balance) revert InsufficientBalance();
        IERC20(token).safeTransfer(msg.sender, amount);
        emit TokenWithdrawn(token, amount);
    }

    /// @notice Withdraw all of a specific token
    /// @param token Token address to withdraw
    function withdrawAllToken(address token) external onlyOwner {
        uint256 balance = IERC20(token).balanceOf(address(this));
        if (balance == 0) revert InsufficientBalance();
        IERC20(token).safeTransfer(msg.sender, balance);
        emit TokenWithdrawn(token, balance);
    }

    /// @notice Withdraw ETH from contract
    function withdrawETH() external onlyOwner {
        uint256 balance = address(this).balance;
        if (balance == 0) revert InsufficientBalance();
        (bool success, ) = msg.sender.call{value: balance}("");
        require(success, "ETH transfer failed");
        emit ETHWithdrawn(balance);
    }

    // ============ VIEW FUNCTIONS ============

    /// @notice Get token balance of this contract
    /// @param token Token address to check
    function getBalance(address token) external view returns (uint256) {
        return IERC20(token).balanceOf(address(this));
    }

    /// @notice Get ETH balance of this contract
    function getETHBalance() external view returns (uint256) {
        return address(this).balance;
    }

    // ============ RECEIVE ============
    receive() external payable {}
}
