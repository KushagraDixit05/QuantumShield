//! Cost probe host (lead-owned, throwaway): probe_host <input.bin> <po2> <composite|succinct>
use methods::{PROBE_GUEST_ELF, PROBE_GUEST_ID};
use risc0_zkvm::{default_prover, ExecutorEnv, ProverOpts};

fn hwm_kb() -> u64 {
    std::fs::read_to_string("/proc/self/status")
        .ok()
        .and_then(|s| s.lines().find(|l| l.starts_with("VmHWM")).map(|l| l.split_whitespace().nth(1).unwrap().parse().unwrap()))
        .unwrap_or(0)
}

fn pad_words(b: &[u8]) -> Vec<u32> {
    let mut v = b.to_vec();
    while v.len() % 4 != 0 {
        v.push(0);
    }
    v.chunks_exact(4).map(|c| u32::from_le_bytes(c.try_into().unwrap())).collect()
}

fn main() {
    assert!(std::env::var("RISC0_DEV_MODE").is_err(), "dev mode set: refusing");
    let a: Vec<String> = std::env::args().collect();
    let input = std::fs::read(&a[1]).unwrap();
    let po2: u32 = a[2].parse().unwrap();
    let kind = a[3].as_str();
    let env = ExecutorEnv::builder().segment_limit_po2(po2).write(&(input.len() as u32)).unwrap().write_slice(&pad_words(&input)).build().unwrap();
    let opts = match kind {
        "succinct" => ProverOpts::succinct(),
        _ => ProverOpts::composite(),
    };
    let t0 = std::time::Instant::now();
    let info = default_prover().prove_with_opts(env, PROBE_GUEST_ELF, &opts).unwrap();
    let prove_s = t0.elapsed().as_secs_f64();
    let t1 = std::time::Instant::now();
    info.receipt.verify(PROBE_GUEST_ID).unwrap();
    let verify_ms = t1.elapsed().as_secs_f64() * 1e3;
    let ok = info.receipt.journal.bytes == input[..146];
    println!(
        "{{\"kind\":\"{}\",\"po2\":{},\"prove_s\":{:.2},\"verify_ms\":{:.1},\"receipt_bytes\":{},\"cycles\":{},\"user_cycles\":{},\"segments\":{},\"vmhwm_kb\":{},\"journal_ok\":{}}}",
        kind, po2, prove_s, verify_ms, bincode::serialize(&info.receipt).unwrap().len(),
        info.stats.total_cycles, info.stats.user_cycles, info.stats.segments, hwm_kb(), ok
    );
}
