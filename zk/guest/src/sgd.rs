//! One fixed-point SGD step (docs/zk_interface.md section 4), integer only.
//!
//! Every product-sum is preceded by the guard (see fixed.rs). Once it passes, the exact i64
//! accumulation cannot overflow, so the inner loops use plain wrapping adds. When both operands are
//! known to fit in i32 the products are 32x32->64 multiplies (two multiply instructions on rv32
//! instead of three-plus for a full 64x64); the const generic `N` selects that path.
use crate::fixed::{bound, guard, maxabs, narrow, R};

pub const D_IN: usize = 64;
pub const D_H: usize = 32;
pub const D_OUT: usize = 10;
pub const NP: usize = D_H * D_IN + D_H + D_OUT * D_H + D_OUT; // 2410
const O_B1: usize = D_H * D_IN; // 2048
const O_W2: usize = O_B1 + D_H; // 2080
const O_B2: usize = O_W2 + D_OUT * D_H; // 2400
const ONE: i64 = 1 << 16;

/// Reusable buffers for one batch size (allocated once; the guest heap never frees).
pub struct Scratch {
    h: Vec<i64>,
    dout: Vec<i64>,
    dh: Vec<i64>,
    g: Vec<i64>,
}

impl Scratch {
    pub fn new(bs: usize) -> Self {
        Scratch { h: vec![0; bs * D_H], dout: vec![0; bs * D_OUT], dh: vec![0; bs * D_H], g: vec![0; NP] }
    }
}

/// Signed 32x32 -> 64 product. On rv32 this is exactly `mul` + `mulh` (two multiplies); the plain
/// Rust expression `(a as i64) * (b as i64)` compiles to four multiplies there.
#[inline(always)]
pub fn mul32(a: i32, b: i32) -> i64 {
    #[cfg(target_arch = "riscv32")]
    {
        let hi: i32;
        // SAFETY: pure register arithmetic.
        unsafe {
            core::arch::asm!("mulh {hi}, {a}, {b}", hi = out(reg) hi, a = in(reg) a, b = in(reg) b,
                options(pure, nomem, nostack));
        }
        ((hi as i64) << 32) | (a.wrapping_mul(b) as u32 as i64)
    }
    #[cfg(not(target_arch = "riscv32"))]
    {
        (a as i64) * (b as i64)
    }
}

/// Arithmetic shift right of an i64 by s (0 <= s < 64), done on 32-bit halves.
#[inline(always)]
fn sar(v: i64, s: u32) -> i64 {
    let lo = v as u32;
    let hi = (v >> 32) as i32;
    if s < 32 {
        let l = (lo >> s) | (((hi as u32) << 1) << (31 - s));
        (((hi >> s) as i64) << 32) | l as i64
    } else {
        let l = (hi >> (s - 32)) as i64; // sign-extended
        let h = (hi >> 31) as i64;
        (h << 32) | (l as u32 as i64)
    }
}

#[inline(always)]
fn mul<const N: bool>(a: i64, b: i64) -> i64 {
    if N {
        mul32(a as i32, b as i32)
    } else {
        a.wrapping_mul(b)
    }
}

#[inline(always)]
fn dot<const N: bool>(a: &[i64], b: &[i64]) -> i64 {
    let b = &b[..a.len()];
    let mut acc = 0i64;
    let mut ca = a.chunks_exact(4);
    let mut cb = b.chunks_exact(4);
    for (x, y) in (&mut ca).zip(&mut cb) {
        acc = acc
            .wrapping_add(mul::<N>(x[0], y[0]))
            .wrapping_add(mul::<N>(x[1], y[1]))
            .wrapping_add(mul::<N>(x[2], y[2]))
            .wrapping_add(mul::<N>(x[3], y[3]));
    }
    for (x, y) in ca.remainder().iter().zip(cb.remainder()) {
        acc = acc.wrapping_add(mul::<N>(*x, *y));
    }
    acc
}

#[inline(always)]
fn axpy<const N: bool>(acc: &mut [i64], d: i64, row: &[i64]) {
    let row = &row[..acc.len()];
    let mut ca = acc.chunks_exact_mut(2);
    let mut cr = row.chunks_exact(2);
    for (a, r) in (&mut ca).zip(&mut cr) {
        a[0] = a[0].wrapping_add(mul::<N>(d, r[0]));
        a[1] = a[1].wrapping_add(mul::<N>(d, r[1]));
    }
    for (a, r) in ca.into_remainder().iter_mut().zip(cr.remainder()) {
        *a = a.wrapping_add(mul::<N>(d, *r));
    }
}

macro_rules! dispatch {
    ($n:expr, $f:ident ( $($a:expr),* )) => {
        if $n { $f::<true>($($a),*) } else { $f::<false>($($a),*) }
    };
}

#[inline(always)]
fn xrow(recs: &[i64], r: usize) -> &[i64] {
    &recs[r * D_IN..r * D_IN + D_IN]
}

fn fwd1<const N: bool>(recs: &[i64], rows: &[usize], w1: &[i64], b1: &[i64], h: &mut [i64]) -> R<u64> {
    let mut oh = 0u64;
    for (b, hrow) in h.chunks_exact_mut(D_H).enumerate() {
        let x = xrow(recs, rows[b]);
        for (k, (wrow, &bias)) in w1.chunks_exact(D_IN).zip(b1).enumerate() {
            let v = (dot::<N>(x, wrow) >> 16).checked_add(bias).ok_or("overflow")?;
            let hv = if v > 0 { v } else { 0 };
            hrow[k] = hv;
            oh |= hv as u64;
        }
    }
    Ok(oh)
}

fn fwd2<const N: bool>(h: &[i64], w2: &[i64], b2: &[i64], ys: &[u32], dout: &mut [i64]) -> R<()> {
    for ((hrow, drow), &y) in h.chunks_exact(D_H).zip(dout.chunks_exact_mut(D_OUT)).zip(ys) {
        for (o, (wrow, &bias)) in w2.chunks_exact(D_H).zip(b2).enumerate() {
            let out = (dot::<N>(hrow, wrow) >> 16).checked_add(bias).ok_or("overflow")?;
            let t = if o == y as usize { ONE } else { 0 };
            drow[o] = out.checked_sub(t).ok_or("overflow")?;
        }
    }
    Ok(())
}

fn bwd_h<const N: bool>(dout: &[i64], w2: &[i64], h: &[i64], dh: &mut [i64]) {
    let w2: &[i64; D_OUT * D_H] = w2.try_into().unwrap();
    for ((drow, hrow), dhrow) in dout.chunks_exact(D_OUT).zip(h.chunks_exact(D_H)).zip(dh.chunks_exact_mut(D_H)) {
        let drow: &[i64; D_OUT] = drow.try_into().unwrap();
        for k in 0..D_H {
            // mask: pre > 0 iff h > 0 (h = max(pre, 0)); masked entries are exactly 0
            dhrow[k] = if hrow[k] > 0 {
                let mut acc = 0i64;
                for o in 0..D_OUT {
                    acc = acc.wrapping_add(mul::<N>(drow[o], w2[o * D_H + k]));
                }
                acc >> 16
            } else {
                0
            };
        }
    }
}

fn acc_w1<const N: bool>(recs: &[i64], rows: &[usize], dh: &[i64], g: &mut [i64]) {
    for (&r, dhrow) in rows.iter().zip(dh.chunks_exact(D_H)) {
        let x = xrow(recs, r);
        for (&d, grow) in dhrow.iter().zip(g.chunks_exact_mut(D_IN)) {
            if d != 0 {
                axpy::<N>(grow, d, x);
            }
        }
    }
}

fn acc_w2<const N: bool>(dout: &[i64], h: &[i64], g: &mut [i64]) {
    for (drow, hrow) in dout.chunks_exact(D_OUT).zip(h.chunks_exact(D_H)) {
        for (&d, grow) in drow.iter().zip(g.chunks_exact_mut(D_H)) {
            if d != 0 {
                axpy::<N>(grow, d, hrow);
            }
        }
    }
}

fn update<const N: bool>(w: &mut [i64], g: &[i64], lr: i64) -> R<()> {
    for (wi, &gi) in w.iter_mut().zip(g) {
        *wi = wi.checked_sub(mul::<N>(lr, gi) >> 16).ok_or("overflow")?;
    }
    Ok(())
}

/// One SGD step on the batch given by `rows` (record indices into `recs`, 64 values each) and labels `ys`
/// (all < 10, checked when a record is opened). `shift` = log2(batch). Updates `w` in place.
#[allow(clippy::too_many_arguments)]
pub fn step(
    w: &mut [i64],
    recs: &[i64],
    rec_or: &[u64],
    rows: &[usize],
    ys: &[u32],
    lr: i64,
    shift: u32,
    sc: &mut Scratch,
) -> R<()> {
    let bs = rows.len();
    let Scratch { h, dout, dh, g } = sc;
    let (ow_all, od, oh, odh);
    let x_exact = || rows.iter().map(|&r| maxabs(xrow(recs, r))).max().unwrap_or(0);
    let ox = rows.iter().fold(0u64, |a, &r| a | rec_or[r]);
    {
        let (w1, rest) = w.split_at(O_B1);
        let (b1, rest) = rest.split_at(D_H);
        let (w2, b2) = rest.split_at(D_OUT * D_H);
        let (ow1, ow2) = (bound(w1), bound(w2));
        ow_all = ow1 | ow2 | bound(b1) | bound(b2);

        // 1-2. pre = X W1^T >> 16 + b1 ; h = max(pre, 0)
        guard(ox, ow1, D_IN as u128, || (x_exact(), maxabs(w1)))?;
        oh = dispatch!(narrow(ox, ow1), fwd1(recs, rows, w1, b1, h))?;
        // 3-4. out = h W2^T >> 16 + b2 ; dout = out - target
        guard(oh, ow2, D_H as u128, || (maxabs(h), maxabs(w2)))?;
        dispatch!(narrow(oh, ow2), fwd2(h, w2, b2, ys, dout))?;
        // 5. dh = (dout W2 >> 16) * (pre > 0)
        od = bound(dout);
        guard(od, ow2, D_OUT as u128, || (maxabs(dout), maxabs(w2)))?;
        dispatch!(narrow(od, ow2), bwd_h(dout, w2, h, dh));
        // 6. gW2 = (dout^T h) >> 16 >> shift
        guard(od, oh, bs as u128, || (maxabs(dout), maxabs(h)))?;
        // 7. gW1 = (dh^T X) >> 16 >> shift
        odh = bound(dh);
        guard(odh, ox, bs as u128, || (maxabs(dh), x_exact()))?;
        g.fill(0);
        dispatch!(narrow(odh, ox), acc_w1(recs, rows, dh, &mut g[..O_B1]));
        dispatch!(narrow(od, oh), acc_w2(dout, h, &mut g[O_W2..O_B2]));
    }
    // 8. bias gradients: plain checked sums over the batch
    for drow in dh.chunks_exact(D_H) {
        for (gi, &d) in g[O_B1..O_W2].iter_mut().zip(drow) {
            *gi = gi.checked_add(d).ok_or("overflow")?;
        }
    }
    for drow in dout.chunks_exact(D_OUT) {
        for (gi, &d) in g[O_B2..].iter_mut().zip(drow) {
            *gi = gi.checked_add(d).ok_or("overflow")?;
        }
    }
    let s16 = 16 + shift;
    let olr = (lr - 1) as u64; // lr > 0, so |lr| <= olr + 1
    // Fast path: loose a-priori bound G >= |g| from the operand bounds already computed (each product
    // term is at most (bound_a + 1) * (bound_b + 1), so |sum| <= bs * that, then floor-shifted). If it shows
    // that g fits i32, |lr * g| < 2^46 and |w| < 2^62, shift, multiply and subtract fuse into one pass
    // with no overflow possible. Otherwise (or if the cheap bound is too loose) the exact path below runs.
    {
        let t = bs as u128;
        let sat = |a: u128, b: u128| a.saturating_mul(b);
        let g1 = (sat(t, sat(odh as u128 + 1, ox as u128 + 1)) >> s16) + 1;
        let g2 = (sat(t, sat(od as u128 + 1, oh as u128 + 1)) >> s16) + 1;
        let g3 = (sat(t, (odh as u128).max(od as u128) + 1) >> shift) + 1;
        let gmax = g1.max(g2).max(g3);
        if gmax < (1u128 << 31)
            && lr < (1i64 << 31)
            && (lr as u128) * gmax < (1u128 << 46)
            && ow_all < (1u64 << 62)
        {
            for (r, s) in [(0..O_B1, s16), (O_B1..O_W2, shift), (O_W2..O_B2, s16), (O_B2..NP, shift)] {
                fused_update(&mut w[r.clone()], &g[r], lr as i32, s);
            }
            return Ok(());
        }
    }
    // Exact path. Floor shifts: product sums shift by 16 + shift, bias sums by shift (floor of floor = one
    // floor); the OR bound of the shifted gradient is collected in the same pass.
    let mut og = 0u64;
    for (r, s) in [(0..O_B1, s16), (O_B1..O_W2, shift), (O_W2..O_B2, s16), (O_B2..NP, shift)] {
        for v in g[r].iter_mut() {
            let t = sar(*v, s);
            *v = t;
            og |= (t ^ (t >> 63)) as u64;
        }
    }
    // 9. W <- W - (lr * g) >> 16 ; guard (lr, g), terms 1.
    guard(olr, og, 1, || (lr as u128, maxabs(g)))?;
    dispatch!(narrow(olr, og), update(w, g, lr))
}

/// w[i] -= (lr * (acc[i] >> s)) >> 16 for accumulators whose shifted value is known to fit i32 and whose
/// product with lr is known to be below 2^46 (so the subtraction cannot overflow). 0 <= s < 48.
fn fused_update(w: &mut [i64], acc: &[i64], lr: i32, s: u32) {
    if s < 32 {
        for (wi, &a) in w.iter_mut().zip(acc) {
            let g = sar(a, s) as i32;
            *wi = wi.wrapping_sub(mul32(lr, g) >> 16);
        }
    } else {
        for (wi, &a) in w.iter_mut().zip(acc) {
            let g = (((a >> 32) as i32) >> (s - 32)) as i32;
            *wi = wi.wrapping_sub(mul32(lr, g) >> 16);
        }
    }
}
