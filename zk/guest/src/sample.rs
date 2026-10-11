//! Sample index rule (docs/zk_interface.md section 5).
use risc0_zkvm::sha::{Block, Impl, Sha256, SHA256_INIT};

/// idx = u64_le(SHA256("QSFL-idx" || seed u64 || t || c || s || j)[0..8]) mod n_c.
/// The 32-byte message plus padding is exactly one block, built directly as words.
pub fn index(seed: u64, t: u32, c: u32, s: u32, j: u32, n_c: u32) -> u32 {
    let mut b = [0u32; 16];
    b[0] = u32::from_le_bytes(*b"QSFL");
    b[1] = u32::from_le_bytes(*b"-idx");
    b[2] = seed as u32;
    b[3] = (seed >> 32) as u32;
    b[4] = t;
    b[5] = c;
    b[6] = s;
    b[7] = j;
    b[8] = 0x80; // little-endian memory: byte 0x80 first
    b[15] = 256u32.to_be(); // message length in bits, big-endian
    let blk = [Block::from(b)];
    let d = Impl::compress_slice(&SHA256_INIT, &blk);
    let h = d.as_bytes();
    let v = u64::from_le_bytes(h[..8].try_into().unwrap());
    (v % n_c as u64) as u32
}
