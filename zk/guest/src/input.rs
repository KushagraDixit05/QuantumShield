//! Input blob parsing (docs/zk_interface.md section 2).
use crate::fixed::R;

pub const HEADER_LEN: usize = 146;

pub struct Reader<'a> {
    b: &'a [u8],
    p: usize,
}

impl<'a> Reader<'a> {
    pub fn new(b: &'a [u8]) -> Self {
        Reader { b, p: 0 }
    }
    pub fn remaining(&self) -> usize {
        self.b.len() - self.p
    }
    #[inline]
    pub fn take(&mut self, n: usize) -> R<&'a [u8]> {
        if n > self.remaining() {
            return Err("short input");
        }
        let s = &self.b[self.p..self.p + n];
        self.p += n;
        Ok(s)
    }
    pub fn u32(&mut self) -> R<u32> {
        Ok(u32::from_le_bytes(self.take(4)?.try_into().unwrap()))
    }
    pub fn u64(&mut self) -> R<u64> {
        Ok(u64::from_le_bytes(self.take(8)?.try_into().unwrap()))
    }
    pub fn h32(&mut self) -> R<[u8; 32]> {
        Ok(self.take(32)?.try_into().unwrap())
    }
}

/// The public part (bytes 0..146), validated.
pub struct Header {
    pub public: [u8; HEADER_LEN],
    pub relation: u8,
    pub t: u32,
    pub c: u32,
    pub n_c: u32,
    pub k: u32,
    pub batch: u32,
    pub seed: u64,
    pub lr_fx: i64,
    pub b2: u64,
    pub h_w: [u8; 32],
    pub commit: [u8; 32],
    pub root: [u8; 32],
}

impl Header {
    pub fn parse(rd: &mut Reader) -> R<Header> {
        let public: [u8; HEADER_LEN] = rd.take(HEADER_LEN)?.try_into().unwrap();
        let mut h = Reader::new(&public);
        if h.take(4)? != b"QSZK" {
            return Err("magic");
        }
        let ver = h.take(1)?[0];
        let relation = h.take(1)?[0];
        if ver != 1 || (relation != 1 && relation != 2) {
            return Err("version or relation");
        }
        let t = h.u32()?;
        let c = h.u32()?;
        let n_c = h.u32()?;
        let k = h.u32()?;
        let batch = h.u32()?;
        let seed = h.u64()?;
        let lr_fx = h.u64()? as i64;
        let b2 = h.u64()?;
        let h_w = h.h32()?;
        let commit = h.h32()?;
        let root = h.h32()?;
        if n_c < 1 {
            return Err("n_c");
        }
        if lr_fx <= 0 {
            return Err("lr_fx");
        }
        if b2 >= 1 << 50 {
            return Err("B2");
        }
        if relation == 1 {
            if k < 1 || !batch.is_power_of_two() {
                return Err("K or batch");
            }
        } else if k != 0 || batch != 0 {
            return Err("K or batch must be 0");
        }
        Ok(Header { public, relation, t, c, n_c, k, batch, seed, lr_fx, b2, h_w, commit, root })
    }
}
