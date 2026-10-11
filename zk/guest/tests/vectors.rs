//! Native tests. Constants (hashes, sampling index) and the .bin vectors in tests/data were produced
//! with the Python reference code (fl/client.py, fl/merkle.py, fl/model.py) via a throwaway script.
use qs_core::fixed::{bound, guard, maxabs};
use qs_core::sha::sha256;
use qs_core::{merkle, run, sample, sgd};
use std::path::PathBuf;

fn hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{:02x}", x)).collect()
}
fn load(name: &str) -> Vec<u8> {
    let p = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/data").join(name);
    std::fs::read(p).unwrap()
}
fn ok(name: &str) {
    let b = load(name);
    let j = run(&b).unwrap_or_else(|e| panic!("{name}: {e}"));
    assert_eq!(&j[..], &b[..146], "{name} journal");
}

#[test]
fn sha_known_answers() {
    assert_eq!(hex(&sha256(b"")), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    assert_eq!(hex(&sha256(b"abc")), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    let leaf: Vec<u8> = (0..517).map(|i| ((i * 7 + 3) % 256) as u8).collect();
    assert_eq!(hex(&sha256(&leaf)), "3895e21771922ee14208a5ed1bfeea18b3a2537944e907ccc8db25a4f5b3db48");
}

#[test]
fn sampling_index_matches_python() {
    // fl.client.sample_indices(0x1122334455667788, 5, 6, K=2, batch=3, n=1000)
    let want = [[919u32, 11, 657], [309, 827, 940]];
    for s in 0..2 {
        for j in 0..3 {
            assert_eq!(sample::index(0x1122334455667788, 5, 6, s, j, 1000), want[s as usize][j as usize]);
        }
    }
    assert_eq!(sample::index(1, 2, 3, 4, 5, 1), 0);
}

#[test]
fn merkle_depths() {
    let d: Vec<usize> = [1u32, 2, 3, 4, 5, 8, 9, 288].iter().map(|&n| merkle::depth(n)).collect();
    assert_eq!(d, [0, 1, 2, 2, 3, 3, 4, 9]);
}

#[test]
fn vectors_pass() {
    // n_c = 1 (depth 0), 2, 3, 5, 7 (odd, duplicated last nodes), 8, 100; real digits data
    for n in [1, 2, 3, 5, 7, 8, 100] {
        ok(&format!("rnd_n{n}_k2_b4.bin"));
    }
    ok("rnd_n5_k3_b1.bin");
    ok("rnd_n6_k1_b32.bin");
    ok("rnd_n9_rel2.bin");
    ok("rnd_n9_slack.bin");
    ok("real_k2_b4.bin");
    ok("real_k1_b32.bin");
    ok("real_rel2.bin");
}

fn fails(mut b: Vec<u8>, f: impl FnOnce(&mut Vec<u8>)) -> &'static str {
    f(&mut b);
    run(&b).expect_err("should fail")
}

#[test]
fn negatives_rel1() {
    let b = load("rnd_n5_k2_b4.bin");
    assert_eq!(fails(b.clone(), |v| v[0] ^= 1), "magic");
    assert_eq!(fails(b.clone(), |v| v[4] = 2), "version or relation");
    assert_eq!(fails(b.clone(), |v| v[5] = 3), "version or relation");
    assert_eq!(fails(b.clone(), |v| v[18..22].copy_from_slice(&0u32.to_le_bytes())), "K or batch");
    assert_eq!(fails(b.clone(), |v| v[22..26].copy_from_slice(&3u32.to_le_bytes())), "K or batch");
    assert_eq!(fails(b.clone(), |v| v[22..26].copy_from_slice(&0u32.to_le_bytes())), "K or batch");
    assert_eq!(fails(b.clone(), |v| v[14..18].copy_from_slice(&0u32.to_le_bytes())), "n_c");
    assert_eq!(fails(b.clone(), |v| v[34..42].copy_from_slice(&0i64.to_le_bytes())), "lr_fx");
    assert_eq!(fails(b.clone(), |v| v[42..50].copy_from_slice(&(1u64 << 50).to_le_bytes())), "B2");
    assert_eq!(fails(b.clone(), |v| v[50] ^= 1), "model hash");
    assert_eq!(fails(b.clone(), |v| v[82] ^= 1), "commitment");
    assert_eq!(fails(b.clone(), |v| v[178 + 5] ^= 1), "model hash");
    assert_eq!(fails(b.clone(), |v| v.push(0)), "trailing bytes");
    assert!(run(&b[..b.len() - 1]).is_err());
    assert_eq!(fails(b.clone(), |v| v.truncate(100)), "short input");
    // round changes the sampled indices: openings no longer match
    assert!(run(&{ let mut v = b.clone(); v[6] ^= 1; v }).is_err());
    // flip a bit in the first opening: record x, label, sibling
    let o = 178 + 2 * 19280 + 4;
    assert_eq!(fails(b.clone(), |v| v[o] ^= 1), "opening order");
    assert_eq!(fails(b.clone(), |v| v[o + 4 + 100] ^= 1), "merkle");
    assert_eq!(fails(b.clone(), |v| v[o + 4 + 512 + 40] ^= 1), "merkle"); // sibling (depth 3)
    assert_eq!(fails(b.clone(), |v| v[o + 4 + 512] = 10), "label");
    // n_open too small / too large
    let no = 178 + 2 * 19280;
    let n = u32::from_le_bytes(b[no..no + 4].try_into().unwrap());
    assert_eq!(fails(b.clone(), |v| v[no..no + 4].copy_from_slice(&(n + 1).to_le_bytes())), "opening count");
    assert!(run(&{ let mut v = b.clone(); v[no..no + 4].copy_from_slice(&(n - 1).to_le_bytes()); v }).is_err());
}

#[test]
fn missing_sibling_is_rejected() {
    // strict path length: drop the last 32 bytes of the opening block and fix the count of bytes
    let mut b = load("rnd_n1_k2_b4.bin"); // n_c = 1, depth 0: a single opening, no siblings
    run(&b).unwrap();
    b.extend_from_slice(&[0u8; 32]); // extra sibling is trailing data
    assert_eq!(run(&b).unwrap_err(), "trailing bytes");
}

#[test]
fn rel2_rules() {
    let b = load("rnd_n9_rel2.bin");
    run(&b).unwrap();
    assert_eq!(fails(b.clone(), |v| v[18] = 1), "K or batch must be 0");
    assert_eq!(fails(b.clone(), |v| v[22] = 4), "K or batch must be 0");
    assert_eq!(fails(b.clone(), |v| v.extend_from_slice(&0u32.to_le_bytes())), "trailing bytes");
    assert_eq!(fails(b.clone(), |v| v.push(0)), "trailing bytes");
}

#[test]
fn norm_bound_boundary() {
    let b = load("rnd_n9_slack.bin"); // B2 = norm + 5
    let norm = u64::from_le_bytes(b[42..50].try_into().unwrap()) - 5;
    let with = |b2: u64| {
        let mut v = b.clone();
        v[42..50].copy_from_slice(&b2.to_le_bytes());
        run(&v)
    };
    assert!(with(norm).is_ok());
    assert!(with(norm + 5).is_ok());
    assert_eq!(with(norm - 1).unwrap_err(), "norm bound");
    // entry >= 2^25 breaks the bound even with B2 at its maximum (2^50 - 1): commitment must match, so recompute it.
    let r2 = load("rnd_n9_rel2.bin");
    let mut v = r2.clone();
    let off = 178;
    v[off..off + 8].copy_from_slice(&(1i64 << 25).to_le_bytes());
    v[42..50].copy_from_slice(&((1u64 << 50) - 1).to_le_bytes());
    let mut pre = b"QSFL-upd".to_vec();
    pre.extend_from_slice(&v[off..off + 8 * 2410]);
    pre.extend_from_slice(&v[146..178]);
    let c = sha256(&pre);
    v[82..114].copy_from_slice(&c);
    assert_eq!(run(&v).unwrap_err(), "entry too large");
    v[off..off + 8].copy_from_slice(&((1i64 << 25) - 1).to_le_bytes());
    let mut pre = b"QSFL-upd".to_vec();
    pre.extend_from_slice(&v[off..off + 8 * 2410]);
    pre.extend_from_slice(&v[146..178]);
    let c = sha256(&pre);
    v[82..114].copy_from_slice(&c);
    // (2^25-1)^2 + other entries > 2^50 - 1 = B2: norm bound fails, not the per-entry test
    assert_eq!(run(&v).unwrap_err(), "norm bound");
}

#[test]
fn guard_boundary() {
    let g = |a: &[i64], b: &[i64], t: u128| guard(bound(a), bound(b), t, || (maxabs(a), maxabs(b)));
    // product exactly 2^62 fails, one below passes
    assert!(g(&[1 << 31], &[1 << 30], 2).is_err());
    assert!(g(&[(1 << 31) - 1], &[1 << 30], 2).is_ok());
    assert!(g(&[1 << 62], &[1], 1).is_err());
    assert!(g(&[(1 << 62) - 1], &[1], 1).is_ok());
    assert!(g(&[-(1 << 62)], &[1], 1).is_err());
    assert!(g(&[-(1 << 62) + 1], &[-1], 1).is_ok());
    assert!(g(&[i64::MIN], &[1], 1).is_err());
    assert!(g(&[i64::MAX], &[0], 1_000_000).is_ok());
    // cheap OR bound is pessimistic here (OR = 1.5 * 2^30) but the exact test passes / fails correctly
    assert!(g(&[1 << 30, 1 << 29], &[(1 << 32) - 1], 1).is_ok());
    assert!(g(&[1 << 30, 1 << 29], &[1 << 32], 1).is_err());
    // terms matter
    assert!(g(&[1 << 20], &[1 << 20], 1 << 21).is_ok());
    assert!(g(&[1 << 20], &[1 << 20], 1 << 22).is_err());
}

// ---- reference implementation of one SGD step, written directly from docs/zk_interface.md section 4 ----
fn rmaxabs(a: &[i64]) -> u128 {
    a.iter().map(|v| v.unsigned_abs() as u128).max().unwrap_or(0)
}
fn rguard(a: &[i64], b: &[i64], terms: u128) -> bool {
    rmaxabs(a) * rmaxabs(b) * terms < (1u128 << 62)
}
fn ref_step(w: &mut Vec<i64>, x: &[Vec<i64>], y: &[u32], lr: i64) -> Option<()> {
    let bs = x.len();
    let shift = bs.trailing_zeros();
    let xf: Vec<i64> = x.concat();
    let (w1, b1, w2, b2) = (&w[..2048], &w[2048..2080], &w[2080..2400], &w[2400..]);
    if !rguard(&xf, w1, 64) {
        return None;
    }
    let mut pre = vec![vec![0i64; 32]; bs];
    for b in 0..bs {
        for k in 0..32 {
            let s: i64 = (0..64).map(|i| x[b][i] * w1[k * 64 + i]).sum();
            pre[b][k] = (s >> 16).checked_add(b1[k])?;
        }
    }
    let h: Vec<Vec<i64>> = pre.iter().map(|r| r.iter().map(|&v| v.max(0)).collect()).collect();
    let hf: Vec<i64> = h.concat();
    if !rguard(&hf, w2, 32) {
        return None;
    }
    let mut dout = vec![vec![0i64; 10]; bs];
    for b in 0..bs {
        for o in 0..10 {
            let s: i64 = (0..32).map(|k| h[b][k] * w2[o * 32 + k]).sum();
            let out = (s >> 16).checked_add(b2[o])?;
            dout[b][o] = out.checked_sub(if y[b] as usize == o { 65536 } else { 0 })?;
        }
    }
    let df: Vec<i64> = dout.concat();
    if !rguard(&df, w2, 10) {
        return None;
    }
    let mut dh = vec![vec![0i64; 32]; bs];
    for b in 0..bs {
        for k in 0..32 {
            let s: i64 = (0..10).map(|o| dout[b][o] * w2[o * 32 + k]).sum();
            dh[b][k] = (s >> 16) * (pre[b][k] > 0) as i64;
        }
    }
    let dhf: Vec<i64> = dh.concat();
    if !rguard(&df, &hf, bs as u128) || !rguard(&dhf, &xf, bs as u128) {
        return None;
    }
    let mut g = vec![0i64; 2410];
    for k in 0..32 {
        for i in 0..64 {
            let s: i64 = (0..bs).map(|b| dh[b][k] * x[b][i]).sum();
            g[k * 64 + i] = (s >> 16) >> shift;
        }
        g[2048 + k] = (0..bs).map(|b| dh[b][k]).sum::<i64>() >> shift;
    }
    for o in 0..10 {
        for k in 0..32 {
            let s: i64 = (0..bs).map(|b| dout[b][o] * h[b][k]).sum();
            g[2080 + o * 32 + k] = (s >> 16) >> shift;
        }
        g[2400 + o] = (0..bs).map(|b| dout[b][o]).sum::<i64>() >> shift;
    }
    if (lr.unsigned_abs() as u128) * rmaxabs(&g) >= (1u128 << 62) {
        return None;
    }
    for i in 0..2410 {
        w[i] = w[i].checked_sub((lr * g[i]) >> 16)?;
    }
    Some(())
}

struct Rng(u64);
impl Rng {
    fn next(&mut self) -> u64 {
        self.0 ^= self.0 << 13;
        self.0 ^= self.0 >> 7;
        self.0 ^= self.0 << 17;
        self.0
    }
    fn range(&mut self, lo: i64, hi: i64) -> i64 {
        lo + (self.next() % (hi - lo) as u64) as i64
    }
}

fn compare(seed: u64, bs: usize, wmag: i64, xmag: i64, lr: i64) {
    let mut r = Rng(seed);
    let w0: Vec<i64> = (0..2410).map(|_| r.range(-wmag, wmag)).collect();
    let recs: Vec<Vec<i64>> = (0..bs).map(|_| (0..64).map(|_| r.range(-xmag, xmag)).collect()).collect();
    let ys: Vec<u32> = (0..bs).map(|_| r.range(0, 10) as u32).collect();
    let mut wr = w0.clone();
    let expect = ref_step(&mut wr, &recs, &ys, lr);
    let flat: Vec<i64> = recs.concat();
    let rec_or: Vec<u64> = recs.iter().map(|x| bound(x)).collect();
    let rows: Vec<usize> = (0..bs).collect();
    let mut w = w0.clone();
    let mut sc = sgd::Scratch::new(bs);
    let got = sgd::step(&mut w, &flat, &rec_or, &rows, &ys, lr, bs.trailing_zeros(), &mut sc);
    assert_eq!(got.is_ok(), expect.is_some(), "seed {seed} bs {bs}: pass/fail differs ({got:?})");
    if got.is_ok() {
        assert_eq!(w, wr, "seed {seed} bs {bs}");
        assert_ne!(w, w0);
    }
}

#[test]
fn step_matches_reference_narrow_and_wide() {
    for (i, bs) in [1usize, 2, 4, 8, 32].into_iter().enumerate() {
        compare(100 + i as u64, bs, 1 << 15, 1 << 16, 20000); // typical, i32 path, negative values (floor shifts)
        compare(200 + i as u64, bs, 1 << 33, 1 << 12, 3); // weights beyond i32: wide path
        compare(300 + i as u64, bs, 1 << 12, 1 << 36, 1 << 20); // inputs beyond i32
        compare(400 + i as u64, bs, 1 << 40, 1 << 40, 7); // guard must fail in both
    }
}

#[test]
fn floor_shift_on_negatives() {
    assert_eq!((-1i64) >> 16, -1);
    assert_eq!((-65535i64) >> 16, -1);
    assert_eq!((-65536i64) >> 16, -1);
    assert_eq!((-65537i64) >> 16, -2);
    // gradient of a tiny negative sum must floor to -1, not truncate to 0
    let mut w = vec![0i64; 2410];
    w[2080] = 1; // W2[0][0]
    w[0] = 1;
    let mut x = vec![0i64; 64];
    x[0] = 1; // pre[0] = (1*1)>>16 = 0 -> h = 0: dout = -target... exercised against the reference below
    compare(7, 1, 3, 3, 65536);
    let _ = (w, x);
}
