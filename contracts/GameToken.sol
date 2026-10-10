// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {ERC20Capped} from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Capped.sol";
import {ERC20Burnable} from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import {ERC20Pausable} from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Pausable.sol";
import {ERC20Permit} from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

/// @title GameToken — moeda "hard" de um jogo (exemplo didático)
/// @notice Modelo de referência do estudo em docs/estudo-criptomoeda-jogo.md.
///         NÃO usar em produção sem auditoria independente.
/// @dev Fluxo de emissão: o backend autoritativo do jogo valida a conquista do
///      jogador e assina um "voucher" EIP-712. O jogador (ou um relayer) resgata
///      o voucher on-chain. Assim a chave do servidor nunca paga gás e cada
///      recompensa é única (nonce), com prazo de validade e teto diário global.
contract GameToken is ERC20, ERC20Capped, ERC20Burnable, ERC20Pausable, ERC20Permit, AccessControl {
    bytes32 public constant SIGNER_ROLE = keccak256("SIGNER_ROLE");
    bytes32 public constant TREASURY_ROLE = keccak256("TREASURY_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    bytes32 private constant CLAIM_TYPEHASH =
        keccak256("Claim(address player,uint256 amount,uint256 nonce,uint256 deadline)");

    /// @notice Teto de emissão por dia (faucet controlado — ver seção de tokenomics).
    uint256 public dailyMintLimit;
    mapping(uint256 day => uint256 minted) public mintedPerDay;
    mapping(uint256 nonce => bool used) public usedNonces;

    /// @notice Registro dos "sinks": queimas feitas pelo jogo (crafting, upgrades, taxas).
    event Sink(address indexed player, uint256 amount, bytes32 indexed reason);
    event RewardClaimed(address indexed player, uint256 amount, uint256 indexed nonce);
    event DailyMintLimitUpdated(uint256 newLimit);

    error VoucherExpired();
    error NonceAlreadyUsed();
    error InvalidSigner();
    error DailyLimitExceeded();

    constructor(address admin, address treasury, uint256 cap_, uint256 dailyLimit_)
        ERC20("Game Gold", "GGLD")
        ERC20Capped(cap_)
        ERC20Permit("Game Gold")
    {
        // Em produção, `admin` deve ser um multisig (ex.: Safe) atrás de um timelock.
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);
        _grantRole(TREASURY_ROLE, treasury);
        dailyMintLimit = dailyLimit_;
        emit DailyMintLimitUpdated(dailyLimit_);
    }

    // ---------------------------------------------------------------------
    // Faucet: recompensas de jogo via voucher assinado pelo servidor
    // ---------------------------------------------------------------------

    function claimReward(address player, uint256 amount, uint256 nonce, uint256 deadline, bytes calldata signature)
        external
    {
        if (block.timestamp > deadline) revert VoucherExpired();
        if (usedNonces[nonce]) revert NonceAlreadyUsed();

        bytes32 digest = _hashTypedDataV4(keccak256(abi.encode(CLAIM_TYPEHASH, player, amount, nonce, deadline)));
        address signer = ECDSA.recover(digest, signature);
        if (!hasRole(SIGNER_ROLE, signer)) revert InvalidSigner();

        uint256 today = block.timestamp / 1 days;
        if (mintedPerDay[today] + amount > dailyMintLimit) revert DailyLimitExceeded();

        usedNonces[nonce] = true;
        mintedPerDay[today] += amount;
        _mint(player, amount);
        emit RewardClaimed(player, amount, nonce);
    }

    // ---------------------------------------------------------------------
    // Sink: queima com motivo rastreável (bom para auditoria e contabilidade)
    // ---------------------------------------------------------------------

    function spend(uint256 amount, bytes32 reason) external {
        _burn(_msgSender(), amount);
        emit Sink(_msgSender(), amount, reason);
    }

    // ---------------------------------------------------------------------
    // Administração
    // ---------------------------------------------------------------------

    /// @notice Emissão da tesouraria (ex.: venda primária). Sujeita ao `cap`.
    function treasuryMint(address to, uint256 amount) external onlyRole(TREASURY_ROLE) {
        _mint(to, amount);
    }

    function setDailyMintLimit(uint256 newLimit) external onlyRole(DEFAULT_ADMIN_ROLE) {
        dailyMintLimit = newLimit;
        emit DailyMintLimitUpdated(newLimit);
    }

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    // ---------------------------------------------------------------------
    // Overrides exigidos pela herança múltipla (OpenZeppelin 5.x)
    // ---------------------------------------------------------------------

    function _update(address from, address to, uint256 value)
        internal
        override(ERC20, ERC20Capped, ERC20Pausable)
    {
        super._update(from, to, value);
    }
}
