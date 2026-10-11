//! QuantumShield zk guest logic (docs/zk_interface.md). Integer only; no floating point.
//! `run` takes the raw input blob and returns the 146-byte journal, or a short failure message
//! (the zkVM entry point turns the message into a panic).
#[cfg(not(target_endian = "little"))]
compile_error!("little-endian targets only");

pub mod fixed;
pub mod input;
pub mod merkle;
pub mod sample;
pub mod sgd;
pub mod sha;

use fixed::R;
use input::{Header, Reader, HEADER_LEN};
use sgd::{D_IN, NP};

/// Run the relation on one input blob. Ok(journal) iff the relation holds.
pub fn run(inp: &[u8]) -> R<[u8; HEADER_LEN]> {
    let mut rd = Reader::new(inp);
    let hd = Header::parse(&mut rd)?;
    let nonce = rd.take(32)?;
    let rel1 = hd.relation == 1;
    // Fail on obviously short inputs before touching any big buffer.
    let need = if rel1 { 2 * 8 * NP + 4 } else { 8 * NP };
    if rd.remaining() < need {
        return Err("short input");
    }

    // W_t (relation 1): kept in a block-padded buffer so it can be hashed in place.
    let mut wbuf: Vec<u64> = Vec::new();
    if rel1 {
        wbuf = vec![0u64; sha::words_for(8 * NP)];
        bytemuck::cast_slice_mut::<u64, u8>(&mut wbuf)[..8 * NP].copy_from_slice(rd.take(8 * NP)?);
        if sha::sha_inplace(&mut wbuf, 8 * NP) != hd.h_w {
            return Err("model hash");
        }
    }
    // (a) commitment: SHA256("QSFL-upd" || delta || nonce), laid out as [prefix | delta | nonce | pad].
    let mut dbuf = vec![0u64; sha::words_for(8 + 8 * NP + 32)];
    {
        let db = bytemuck::cast_slice_mut::<u64, u8>(&mut dbuf);
        db[..8].copy_from_slice(b"QSFL-upd");
        db[8..8 + 8 * NP].copy_from_slice(rd.take(8 * NP)?);
        db[8 + 8 * NP..8 + 8 * NP + 32].copy_from_slice(nonce);
    }
    if sha::sha_inplace(&mut dbuf, 8 + 8 * NP + 32) != hd.commit {
        return Err("commitment");
    }
    let delta: &[i64] = bytemuck::cast_slice(&dbuf[1..1 + NP]);
    // (b) norm: each |d| < 2^25 so each square < 2^50 and the sum of 2410 squares < 2^62 fits u64 exactly.
    // Fast path when the OR bound proves |d| <= bound + 1 < 2^25 (then d fits i32); otherwise exact per-entry test.
    let ss: u64 = if fixed::bound(delta) < (1 << 25) - 1 {
        delta.iter().map(|&d| sgd::mul32(d as i32, d as i32) as u64).sum()
    } else {
        let mut ss = 0u64;
        for &d in delta {
            let a = d.unsigned_abs();
            if a >= 1 << 25 {
                return Err("entry too large");
            }
            ss += a * a;
        }
        ss
    };
    if ss > hd.b2 {
        return Err("norm bound");
    }

    if !rel1 {
        // Interface v1.3: relation 2 has no n_open field and no openings; trailing bytes are an error.
        if rd.remaining() != 0 {
            return Err("trailing bytes");
        }
        return Ok(hd.public);
    }

    // (c) local training consistency.
    let n_open = rd.u32()? as usize;
    let depth = merkle::depth(hd.n_c);
    let open_min = 4 + 8 * D_IN + 4 + 32 * depth;
    if n_open > rd.remaining() / open_min {
        return Err("opening count");
    }
    let bs = hd.batch as usize;
    let mut recs = vec![0i64; n_open * D_IN]; // verified records, first-appearance order
    let mut rec_or = vec![0u64; n_open]; // OR magnitude bound per record
    let mut rec_y = vec![0u32; n_open];
    let mut seen: Vec<u32> = Vec::with_capacity(n_open);
    let mut rows = vec![0usize; bs];
    let mut ys = vec![0u32; bs];
    let mut mk = merkle::Hasher::new();
    let mut sc = sgd::Scratch::new(bs);
    let mut w: Vec<i64> = bytemuck::cast_slice::<u64, i64>(&wbuf)[..NP].to_vec();
    let shift = hd.batch.trailing_zeros();

    for s in 0..hd.k {
        for j in 0..bs {
            let idx = sample::index(hd.seed, hd.t, hd.c, s, j as u32, hd.n_c);
            let pos = match seen.iter().position(|&i| i == idx) {
                Some(p) => p,
                None => {
                    let p = seen.len();
                    if p >= n_open {
                        return Err("opening count");
                    }
                    if rd.u32()? != idx {
                        return Err("opening order");
                    }
                    let xb = rd.take(8 * D_IN)?;
                    let y = rd.u32()?;
                    if y >= 10 {
                        return Err("label");
                    }
                    let path = rd.take(32 * depth)?;
                    if !mk.verify(idx, xb, y, path, &hd.root) {
                        return Err("merkle");
                    }
                    let dst = &mut recs[p * D_IN..(p + 1) * D_IN];
                    bytemuck::cast_slice_mut::<i64, u8>(dst).copy_from_slice(xb);
                    rec_or[p] = fixed::bound(dst);
                    rec_y[p] = y;
                    seen.push(idx);
                    p
                }
            };
            rows[j] = pos;
            ys[j] = rec_y[pos];
        }
        sgd::step(&mut w, &recs, &rec_or, &rows, &ys, hd.lr_fx, shift, &mut sc)?;
    }
    if seen.len() != n_open {
        return Err("opening count");
    }
    if rd.remaining() != 0 {
        return Err("trailing bytes");
    }
    let w0: &[i64] = &bytemuck::cast_slice::<u64, i64>(&wbuf)[..NP];
    for i in 0..NP {
        match w[i].checked_sub(w0[i]) {
            Some(d) if d == delta[i] => {}
            Some(_) => return Err("delta mismatch"),
            None => return Err("overflow"),
        }
    }
    Ok(hd.public)
}
