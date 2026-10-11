//! Fixed-point guard (docs/zk_interface.md section 4).
//!
//! The relation: before each product-sum, fail if max|a| * max|b| * terms >= 2^62 (u128 arithmetic).
//! Computing exact maxima costs a pass with an unsigned 64-bit compare per element, so a cheap
//! upper bound is tried first: `bound(a)` is the OR of `v ^ (v >> 63)` over the elements. For every
//! element |v| <= (v ^ (v>>63)) + 1 <= bound + 1, so (bound_a+1)*(bound_b+1)*terms < 2^62 implies the
//! exact test passes. Only when that sufficient test fails is the exact maximum computed, so the
//! outcome is identical to the exact rule.

pub type R<T> = Result<T, &'static str>;

pub const LIMIT: u128 = 1u128 << 62;

/// OR of one's-complement magnitudes. Upper bound: |v| <= bound + 1 for every element.
#[inline]
pub fn bound(a: &[i64]) -> u64 {
    let mut o = 0u64;
    for &v in a {
        o |= (v ^ (v >> 63)) as u64;
    }
    o
}

/// Exact max|v| (u128 to cover |i64::MIN| = 2^63 without wrapping).
pub fn maxabs(a: &[i64]) -> u128 {
    a.iter().map(|v| v.unsigned_abs() as u128).max().unwrap_or(0)
}

/// Check max|a| * max|b| * terms < 2^62. `ba`, `bb` are `bound()` values of the operands (ORed over all
/// pieces if an operand is split); `exact` returns the exact maxima and runs only when the cheap test fails.
#[inline]
pub fn guard(ba: u64, bb: u64, terms: u128, exact: impl FnOnce() -> (u128, u128)) -> R<()> {
    if (ba as u128 + 1).saturating_mul(bb as u128 + 1).saturating_mul(terms) < LIMIT {
        return Ok(());
    }
    let (ma, mb) = exact();
    match ma.checked_mul(mb).and_then(|p| p.checked_mul(terms)) {
        Some(p) if p < LIMIT => Ok(()),
        _ => Err("fixed-point guard"),
    }
}

/// True when every operand value of both sides fits in i32 (so a 32x32->64 multiply is exact).
#[inline]
pub fn narrow(ba: u64, bb: u64) -> bool {
    ba < 0x7fff_ffff && bb < 0x7fff_ffff
}
