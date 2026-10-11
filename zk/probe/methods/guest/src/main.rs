//! Cost probe guest (lead-owned, throwaway). Implements docs/zk_interface.md for measurement;
//! Agent A writes the production guest in zk/guest/.
use risc0_zkvm::guest::env;
use risc0_zkvm::sha::{Impl, Sha256};

const D_IN: usize = 64;
const D_H: usize = 32;
const D_OUT: usize = 10;
const NP: usize = D_H * D_IN + D_H + D_OUT * D_H + D_OUT;
const ONE: i64 = 1 << 16;

fn sha(b: &[u8]) -> [u8; 32] {
    let d = Impl::hash_bytes(b);
    let mut o = [0u8; 32];
    o.copy_from_slice(d.as_bytes());
    o
}

struct Rd<'a> {
    b: &'a [u8],
    p: usize,
}
impl<'a> Rd<'a> {
    fn take(&mut self, n: usize) -> &'a [u8] {
        let s = &self.b[self.p..self.p + n];
        self.p += n;
        s
    }
    fn u32(&mut self) -> u32 {
        u32::from_le_bytes(self.take(4).try_into().unwrap())
    }
    fn u64(&mut self) -> u64 {
        u64::from_le_bytes(self.take(8).try_into().unwrap())
    }
    fn i64s(&mut self, n: usize) -> Vec<i64> {
        self.take(8 * n).chunks_exact(8).map(|c| i64::from_le_bytes(c.try_into().unwrap())).collect()
    }
    fn h(&mut self) -> [u8; 32] {
        self.take(32).try_into().unwrap()
    }
}

fn maxabs(a: &[i64]) -> u128 {
    a.iter().map(|v| v.unsigned_abs() as u128).max().unwrap_or(0)
}
fn guard(a: &[i64], b: &[i64], terms: u128) {
    let p = maxabs(a).checked_mul(maxabs(b)).and_then(|v| v.checked_mul(terms)).expect("guard overflow");
    assert!(p < (1u128 << 62), "fixed-point guard");
}

/// One SGD step (docs/zk_interface.md section 4).
fn step(w: &mut [i64], x: &[i64], y: &[u32], lr: i64, shift: u32) {
    let bs = y.len();
    let (w1, rest) = w.split_at(D_H * D_IN);
    let (b1, rest) = rest.split_at(D_H);
    let (w2, b2) = rest.split_at(D_OUT * D_H);
    guard(x, w1, D_IN as u128);
    let mut pre = vec![0i64; bs * D_H];
    let mut h = vec![0i64; bs * D_H];
    for b in 0..bs {
        for k in 0..D_H {
            let mut acc = 0i64;
            for i in 0..D_IN {
                acc = acc.wrapping_add(x[b * D_IN + i].wrapping_mul(w1[k * D_IN + i]));
            }
            let v = (acc >> 16).checked_add(b1[k]).unwrap();
            pre[b * D_H + k] = v;
            h[b * D_H + k] = v.max(0);
        }
    }
    guard(&h, w2, D_H as u128);
    let mut dout = vec![0i64; bs * D_OUT];
    for b in 0..bs {
        for o in 0..D_OUT {
            let mut acc = 0i64;
            for k in 0..D_H {
                acc = acc.wrapping_add(h[b * D_H + k].wrapping_mul(w2[o * D_H + k]));
            }
            let out = (acc >> 16).checked_add(b2[o]).unwrap();
            let t = if y[b] as usize == o { ONE } else { 0 };
            dout[b * D_OUT + o] = out.checked_sub(t).unwrap();
        }
    }
    guard(&dout, w2, D_OUT as u128);
    let mut dh = vec![0i64; bs * D_H];
    for b in 0..bs {
        for k in 0..D_H {
            let mut acc = 0i64;
            for o in 0..D_OUT {
                acc = acc.wrapping_add(dout[b * D_OUT + o].wrapping_mul(w2[o * D_H + k]));
            }
            dh[b * D_H + k] = if pre[b * D_H + k] > 0 { acc >> 16 } else { 0 };
        }
    }
    guard(&dout, &h, bs as u128);
    guard(&dh, x, bs as u128);
    let mut g = vec![0i64; NP];
    for k in 0..D_H {
        for i in 0..D_IN {
            let mut acc = 0i64;
            for b in 0..bs {
                acc = acc.wrapping_add(dh[b * D_H + k].wrapping_mul(x[b * D_IN + i]));
            }
            g[k * D_IN + i] = (acc >> 16) >> shift;
        }
    }
    let o1 = D_H * D_IN;
    for k in 0..D_H {
        let s: i64 = (0..bs).map(|b| dh[b * D_H + k]).fold(0i64, |a, v| a.checked_add(v).unwrap());
        g[o1 + k] = s >> shift;
    }
    let o2 = o1 + D_H;
    for o in 0..D_OUT {
        for k in 0..D_H {
            let mut acc = 0i64;
            for b in 0..bs {
                acc = acc.wrapping_add(dout[b * D_OUT + o].wrapping_mul(h[b * D_H + k]));
            }
            g[o2 + o * D_H + k] = (acc >> 16) >> shift;
        }
    }
    let o3 = o2 + D_OUT * D_H;
    for o in 0..D_OUT {
        let s: i64 = (0..bs).map(|b| dout[b * D_OUT + o]).fold(0i64, |a, v| a.checked_add(v).unwrap());
        g[o3 + o] = s >> shift;
    }
    assert!((lr.unsigned_abs() as u128) * maxabs(&g) < (1u128 << 62), "fixed-point guard");
    for i in 0..NP {
        w[i] = w[i].checked_sub((lr * g[i]) >> 16).unwrap();
    }
}

struct Rec {
    x: Vec<i64>,
    y: u32,
}

fn main() {
    let nbytes: u32 = env::read();
    let mut words = vec![0u32; (nbytes as usize + 3) / 4];
    env::read_slice(&mut words);
    let mut buf: Vec<u8> = Vec::with_capacity(words.len() * 4);
    for wd in &words {
        buf.extend_from_slice(&wd.to_le_bytes());
    }
    buf.truncate(nbytes as usize);
    let mut r = Rd { b: &buf, p: 0 };
    assert_eq!(r.take(4), b"QSZK");
    let ver = r.take(1)[0];
    let rel = r.take(1)[0];
    assert!(ver == 1 && (rel == 1 || rel == 2));
    let t = r.u32();
    let c = r.u32();
    let n = r.u32();
    let k = r.u32();
    let batch = r.u32();
    let seed = r.u64();
    let lr = r.u64() as i64;
    let b2 = r.u64();
    let hw = r.h();
    let cm = r.h();
    let root = r.h();
    let public = &buf[..146];
    let nonce = r.h();
    let w0 = if rel == 1 { r.i64s(NP) } else { vec![] };
    let delta = r.i64s(NP);

    // (a) opening
    let mut pre = b"QSFL-upd".to_vec();
    for v in &delta {
        pre.extend_from_slice(&v.to_le_bytes());
    }
    pre.extend_from_slice(&nonce);
    assert_eq!(sha(&pre), cm, "commitment");
    // (b) norm
    let mut s: u128 = 0;
    for v in &delta {
        assert!(v.unsigned_abs() < (1 << 25));
        s += (v.unsigned_abs() as u128) * (v.unsigned_abs() as u128);
    }
    assert!(b2 < (1u64 << 50) && s <= b2 as u128, "norm");

    if rel == 1 {
        let mut wb = Vec::with_capacity(8 * NP);
        for v in &w0 {
            wb.extend_from_slice(&v.to_le_bytes());
        }
        assert_eq!(sha(&wb), hw, "model hash");
        assert!(k >= 1 && batch.is_power_of_two() && lr > 0);
        let shift = batch.trailing_zeros();
        let mut depth = 0usize;
        let mut m = 1u32;
        while m < n {
            m *= 2;
            depth += 1;
        }
        let n_open = r.u32() as usize;
        let mut seen: Vec<(u32, Rec)> = Vec::new();
        let mut w = w0.clone();
        for s in 0..k {
            let mut xs = Vec::with_capacity(batch as usize * D_IN);
            let mut ys = Vec::with_capacity(batch as usize);
            for j in 0..batch {
                let mut m = b"QSFL-idx".to_vec();
                for v in [t, c, s, j] {
                    m.extend_from_slice(&v.to_le_bytes());
                }
                let mut msg = b"QSFL-idx".to_vec();
                msg.extend_from_slice(&seed.to_le_bytes());
                msg.extend_from_slice(&m[8..]);
                let hh = sha(&msg);
                let idx = (u64::from_le_bytes(hh[..8].try_into().unwrap()) % n as u64) as u32;
                let pos = match seen.iter().position(|(i, _)| *i == idx) {
                    Some(p) => p,
                    None => {
                        let oi = r.u32();
                        assert_eq!(oi, idx, "opening order");
                        let x = r.i64s(D_IN);
                        let y = r.u32();
                        assert!(y < 10);
                        let mut lb = vec![0u8];
                        for v in &x {
                            lb.extend_from_slice(&v.to_le_bytes());
                        }
                        lb.extend_from_slice(&y.to_le_bytes());
                        let mut hcur = sha(&lb);
                        let mut i = idx;
                        for _ in 0..depth {
                            let sib = r.h();
                            let mut nb = vec![1u8];
                            if i % 2 == 0 {
                                nb.extend_from_slice(&hcur);
                                nb.extend_from_slice(&sib);
                            } else {
                                nb.extend_from_slice(&sib);
                                nb.extend_from_slice(&hcur);
                            }
                            hcur = sha(&nb);
                            i /= 2;
                        }
                        assert_eq!(hcur, root, "merkle");
                        seen.push((idx, Rec { x, y }));
                        seen.len() - 1
                    }
                };
                xs.extend_from_slice(&seen[pos].1.x);
                ys.push(seen[pos].1.y);
            }
            step(&mut w, &xs, &ys, lr, shift);
        }
        assert_eq!(seen.len(), n_open, "opening count");
        for i in 0..NP {
            assert_eq!(w[i].checked_sub(w0[i]).unwrap(), delta[i], "delta");
        }
    }
    assert_eq!(r.p, buf.len(), "trailing");
    env::commit_slice(public);
}
