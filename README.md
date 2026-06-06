# DeFi91 Arbitrage Engine

**Atomic Backrunning Arbitrage Bot untuk Base Network**

Bot ini secara otomatis mendeteksi dan mengeksploitasi perbedaan harga (price discrepancy) antara **Uniswap V3** dan **Aerodrome Slipstream** di jaringan Base. Seluruh eksekusi bersifat atomik: jika tidak ada profit, transaksi otomatis dibatalkan (revert) tanpa kehilangan modal.

## Arsitektur

```
┌─────────────────────────────────────────────────────────┐
│                  DeFi91 Arbitrage Engine                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐  │
│  │ Scanner  │───>│ Executor │───>│ ArbitrageExecutor│  │
│  │ (Python) │    │ (Python) │    │   (Solidity)     │  │
│  └──────────┘    └──────────┘    └──────────────────┘  │
│       │                                    │            │
│       ▼                                    ▼            │
│  ┌──────────┐                    ┌──────────────────┐  │
│  │  Logger  │                    │   Base Network   │  │
│  │  (JSON)  │                    │  (Uniswap V3 +   │  │
│  └──────────┘                    │   Aerodrome)     │  │
│       │                          └──────────────────┘  │
│       ▼                                                 │
│  ┌──────────────────┐                                   │
│  │    Dashboard     │                                   │
│  │  (GitHub Pages)  │                                   │
│  └──────────────────┘                                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Struktur Proyek

| Folder/File | Deskripsi |
| :--- | :--- |
| `contracts/ArbitrageExecutor.sol` | Smart Contract utama (Solidity 0.8.24) |
| `searcher/config.py` | Konfigurasi: alamat kontrak, ABI, parameter bot |
| `searcher/scanner.py` | Pemindai harga real-time via Multicall3 |
| `searcher/executor.py` | Pembuat dan pengirim transaksi arbitrase |
| `searcher/logger.py` | Pencatat aktivitas dan data dashboard |
| `searcher/main.py` | Entry point utama bot |
| `dashboard/index.html` | Dashboard pemantauan (GitHub Pages) |
| `dashboard/data.json` | Data real-time untuk dashboard |
| `DEPLOYMENT_GUIDE.md` | Panduan deployment lengkap |
| `railway.json` | Konfigurasi Railway.app |
| `requirements.txt` | Dependensi Python |

## Fitur Utama

| Fitur | Deskripsi |
| :--- | :--- |
| Atomic Revert | Transaksi otomatis batal jika tidak profit |
| Multicall Scanning | Baca harga dari banyak pool dalam 1 RPC call |
| Flashblock-Aware | Dioptimalkan untuk block time 200ms Base |
| Dry Run Mode | Mode simulasi tanpa transaksi nyata |
| Dashboard Real-time | Pemantauan via GitHub Pages |
| Emergency Pause | Hentikan bot kapan saja via Smart Contract |

## Cara Menjalankan (Lokal)

```bash
# Install dependencies
pip install -r requirements.txt

# Jalankan dalam mode simulasi (DRY RUN)
cd searcher
DRY_RUN=true python main.py

# Jalankan dalam mode live (HATI-HATI!)
DRY_RUN=false PRIVATE_KEY=xxx ARBITRAGE_CONTRACT=xxx python main.py
```

## Deployment

Lihat **[DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)** untuk panduan lengkap deployment ke Railway.app dan GitHub Pages.

## Keamanan

Smart Contract dilengkapi dengan mekanisme keamanan berlapis dari OpenZeppelin: `Ownable` (hanya owner yang dapat mengeksekusi), `ReentrancyGuard` (mencegah serangan reentrancy), dan `Pausable` (emergency stop). Seluruh dana hanya dapat ditarik oleh owner kontrak.

---

**Owner:** Karman | **Network:** Base Mainnet (Chain ID: 8453) | **Version:** 1.0
