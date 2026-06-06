# Panduan Deployment: DeFi91 Arbitrage Engine (Base Network)

Bot arbitrase ini dirancang untuk berjalan 24/7 di **Railway.app** dengan pemantauan melalui **GitHub Pages**. Ikuti panduan naratif di bawah ini secara berurutan untuk memastikan deployment berjalan lancar dan aman.

## 1. Persiapan Wallet & Smart Contract

Langkah pertama yang harus dilakukan adalah menyiapkan dompet digital (wallet) khusus untuk bot ini. Buatlah address baru di MetaMask atau Rabby, dan jangan pernah menggunakan wallet utama Anda demi alasan keamanan. Isilah wallet tersebut dengan sedikit ETH di jaringan Base (sekitar 0.005 ETH atau setara $15) untuk menutupi biaya gas saat deployment dan eksekusi transaksi. Pastikan Anda menyimpan Private Key wallet ini dengan aman.

Selanjutnya, Anda perlu melakukan deployment Smart Contract `ArbitrageExecutor.sol`. Buka Remix IDE di browser Anda, buat file baru, dan salin seluruh kode dari folder `contracts/`. Lakukan kompilasi menggunakan Solidity versi `0.8.24` dengan mengaktifkan fitur Optimizer pada angka 200 runs. Setelah kompilasi berhasil, ubah environment menjadi "Injected Provider - MetaMask" dan pastikan jaringan MetaMask Anda berada di Base Mainnet. Klik tombol Deploy, dan setelah transaksi selesai, simpan alamat kontrak (Contract Address) tersebut.

Setelah kontrak berhasil di-deploy, Anda perlu menyuntikkan modal awal (funding). Kirimkan aset seperti USDC atau WETH langsung ke **alamat Smart Contract** yang baru saja Anda deploy, bukan ke alamat wallet Anda. Bot ini dirancang untuk hanya menggunakan dana yang berada di dalam Smart Contract, sehingga sangat aman dari potensi peretasan wallet.

## 2. Deployment Bot ke Railway.app

Untuk menjalankan engine Python secara terus-menerus, kita akan menggunakan Railway.app. Daftarlah menggunakan akun GitHub Anda dan buat proyek baru dengan memilih opsi "Deploy from GitHub repo". Pilih repositori `defi91-arbitrage-bot` yang telah Anda unggah sebelumnya.

Hal yang paling krusial dalam tahap ini adalah mengatur Environment Variables. Di dashboard Railway, masuklah ke menu Variables dan tambahkan parameter berikut:
*   `BASE_RPC_URL`: Isi dengan `https://mainnet.base.org` atau gunakan RPC pribadi dari Alchemy/QuickNode untuk kecepatan maksimal.
*   `PRIVATE_KEY`: Masukkan Private Key wallet bot Anda (tanpa awalan 0x).
*   `ARBITRAGE_CONTRACT`: Masukkan alamat Smart Contract yang Anda deploy pada langkah pertama.
*   `MIN_PROFIT_USD`: Atur ke `0.50` sebagai batas minimal profit bersih dalam USD per transaksi.
*   `MAX_GAS_GWEI`: Atur ke `0.5` sebagai batas maksimal harga gas.
*   `DRY_RUN`: Atur ke `false` untuk eksekusi nyata, atau `true` jika Anda hanya ingin melakukan simulasi.

Setelah variabel tersimpan, Railway akan otomatis mendeteksi file `railway.json` dan memulai proses build serta deploy. Anda dapat memeriksa tab Logs untuk memastikan bot telah berjalan dan menampilkan pesan bahwa pemindaian peluang arbitrase telah dimulai.

## 3. Setup Dashboard (GitHub Pages)

Untuk memantau performa bot, Anda dapat mengaktifkan GitHub Pages. Buka repositori GitHub Anda, lalu masuk ke menu Settings dan pilih bagian Pages. Pada bagian Source, pilih "Deploy from a branch". Pilih branch `main` dan arahkan ke folder `/dashboard`. Setelah Anda menyimpan pengaturan ini, dashboard pemantauan Anda akan dapat diakses secara publik melalui URL GitHub Pages Anda.

## 4. Operasional & Keamanan

Dalam pengoperasian sehari-hari, Anda dapat menarik keuntungan (withdraw) kapan saja menggunakan fungsi `withdrawToken` atau `withdrawETH` langsung dari Smart Contract melalui Basescan atau antarmuka Remix. Perlu diingat bahwa hanya Anda sebagai *Owner* yang memiliki akses untuk memanggil fungsi ini.

Jika terjadi anomali pasar yang ekstrem, Anda memiliki opsi untuk menghentikan sementara aktivitas bot dengan memanggil fungsi `pause()` pada Smart Contract. Selain itu, jika Anda melihat di log bahwa bot sering mengalami *rate limit*, segera ganti `BASE_RPC_URL` di Railway dengan penyedia RPC berbayar atau node pribadi untuk menjaga stabilitas.

Bot ini dilengkapi dengan proteksi *Atomic Revert*. Artinya, jika sebuah peluang arbitrase dieksekusi namun gagal menghasilkan profit karena keduluan oleh bot lain, transaksi tersebut akan otomatis dibatalkan (revert) di level jaringan. Modal utama Anda akan tetap utuh, dan Anda hanya akan menanggung biaya gas yang sangat kecil, biasanya di bawah $0.01 di jaringan Base.
