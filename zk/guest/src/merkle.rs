//! Merkle verification (docs/zk_interface.md section 6): domain-separated leaves and nodes.
use crate::sha::{sha_inplace, words_for};

/// ceil(log2(n)), 0 for n = 1.
pub fn depth(n: u32) -> usize {
    if n <= 1 {
        0
    } else {
        (32 - (n - 1).leading_zeros()) as usize
    }
}

pub struct Hasher {
    leaf: Vec<u64>,
    node: [u64; words_for(65)],
}

impl Hasher {
    pub fn new() -> Self {
        Hasher { leaf: vec![0u64; words_for(517)], node: [0; words_for(65)] }
    }

    /// SHA256(0x00 || x (512 bytes LE) || y u32 LE).
    pub fn leaf_hash(&mut self, x: &[u8], y: u32) -> [u8; 32] {
        let b = bytemuck::cast_slice_mut::<u64, u8>(&mut self.leaf);
        b[0] = 0;
        b[1..513].copy_from_slice(x);
        b[513..517].copy_from_slice(&y.to_le_bytes());
        sha_inplace(&mut self.leaf, 517)
    }

    /// SHA256(0x01 || l || r).
    pub fn node_hash(&mut self, l: &[u8], r: &[u8]) -> [u8; 32] {
        let b = bytemuck::cast_slice_mut::<u64, u8>(&mut self.node);
        b[0] = 1;
        b[1..33].copy_from_slice(l);
        b[33..65].copy_from_slice(r);
        sha_inplace(&mut self.node, 65)
    }

    /// Verify record (idx, x, y) with `path` (exactly depth(n_c) siblings, leaf level first) against root.
    /// The caller guarantees path.len() is a multiple of 32 of the right depth and idx < n_c.
    pub fn verify(&mut self, idx: u32, x: &[u8], y: u32, path: &[u8], root: &[u8; 32]) -> bool {
        let mut h = self.leaf_hash(x, y);
        let mut i = idx;
        for sib in path.chunks_exact(32) {
            h = if i & 1 == 0 { self.node_hash(&h, sib) } else { self.node_hash(sib, &h) };
            i >>= 1;
        }
        h == *root
    }
}

impl Default for Hasher {
    fn default() -> Self {
        Self::new()
    }
}
