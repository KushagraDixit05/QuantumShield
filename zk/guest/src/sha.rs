//! SHA-256 over block-aligned buffers using the risc0 `Sha256` trait (accelerated in the zkVM).
//! The message sits at the start of a u64-backed buffer; padding is written in place, so a
//! hash is one `compress_slice` call with no allocation and no extra copy.
use risc0_zkvm::sha::{Block, Impl, Sha256, SHA256_INIT};

/// Number of u64 words a buffer needs to hold a `len`-byte message plus SHA padding.
pub const fn words_for(len: usize) -> usize {
    ((len + 9 + 63) / 64) * 8
}

/// Hash the first `len` bytes of `buf` (padding is written into the following bytes of `buf`).
pub fn sha_inplace(buf: &mut [u64], len: usize) -> [u8; 32] {
    let end = (len + 9 + 63) / 64 * 64;
    let bytes = &mut bytemuck::cast_slice_mut::<u64, u8>(buf)[..end];
    bytes[len] = 0x80;
    bytes[len + 1..end - 4].fill(0);
    bytes[end - 4..].copy_from_slice(&((len as u32).wrapping_mul(8)).to_be_bytes());
    let blocks: &[Block] = bytemuck::cast_slice(bytes);
    let d = Impl::compress_slice(&SHA256_INIT, blocks);
    d.as_bytes().try_into().unwrap()
}

/// Convenience for tests and cold paths: SHA-256 of an arbitrary byte string.
pub fn sha256(msg: &[u8]) -> [u8; 32] {
    let mut buf = vec![0u64; words_for(msg.len())];
    bytemuck::cast_slice_mut::<u64, u8>(&mut buf)[..msg.len()].copy_from_slice(msg);
    sha_inplace(&mut buf, msg.len())
}
