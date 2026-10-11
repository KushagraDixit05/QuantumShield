//! zkVM entry point. All logic lives in the `qs_core` library (see lib.rs) so it can be tested natively.
use risc0_zkvm::guest::env;

fn main() {
    // Transport (docs/zk_interface.md section 2): u32 byte length, then ceil(n/4) little-endian words.
    let n: u32 = env::read();
    let n = n as usize;
    let mut words = vec![0u32; (n + 3) / 4];
    env::read_slice(&mut words);
    let bytes: &[u8] = &bytemuck::cast_slice::<u32, u8>(&words)[..n];
    match qs_core::run(bytes) {
        Ok(journal) => env::commit_slice(&journal),
        Err(msg) => panic!("{}", msg),
    }
}
