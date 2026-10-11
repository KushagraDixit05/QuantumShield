//! CLI integration tests. None of these proves; `execute` runs only the zkVM executor.
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

const BIN: &str = env!("CARGO_BIN_EXE_qs-zk");

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..").canonicalize().unwrap()
}

fn tmp(name: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!("qs_zk_host_tests_{}", std::process::id()));
    std::fs::create_dir_all(&d).unwrap();
    d.join(name)
}

fn run(args: &[&str]) -> Output {
    Command::new(BIN).args(args).env_remove("RISC0_DEV_MODE").output().unwrap()
}

fn code(o: &Output) -> i32 {
    o.status.code().unwrap_or(-1)
}

fn make_input(k: &str, batch: &str, rel: &str, name: &str) -> PathBuf {
    let out = tmp(name);
    let py = root().join(".venv/bin/python");
    let st = Command::new(py)
        .current_dir(root())
        .args(["zk/probe/make_input.py", out.to_str().unwrap(), k, batch, rel])
        .status()
        .unwrap();
    assert!(st.success(), "make_input failed");
    out
}

#[test]
fn args_unknown_subcommand_is_2() {
    assert_eq!(code(&run(&["frobnicate"])), 2);
    assert_eq!(code(&run(&[])), 2);
}

#[test]
fn args_missing_and_bad_flags_are_2() {
    assert_eq!(code(&run(&["prove"])), 2);
    assert_eq!(code(&run(&["verify", "--receipt", "x"])), 2);
    assert_eq!(code(&run(&["execute", "--bogus", "1"])), 2);
    let inp = tmp("short_args.bin");
    std::fs::write(&inp, vec![0u8; 10]).unwrap();
    let (i, r, j) = (inp.to_str().unwrap(), tmp("r.bin"), tmp("j.bin"));
    let (r, j) = (r.to_str().unwrap(), j.to_str().unwrap());
    assert_eq!(code(&run(&["prove", "--input", i, "--receipt", r, "--journal", j, "--kind", "weird"])), 2);
    assert_eq!(code(&run(&["prove", "--input", i, "--receipt", r, "--journal", j, "--po2", "abc"])), 2);
}

#[test]
fn truncated_or_bad_magic_input_is_2() {
    let (j, r) = (tmp("j.bin"), tmp("r.bin"));
    let (j, r) = (j.to_str().unwrap(), r.to_str().unwrap());
    let short = tmp("short.bin");
    let mut b = b"QSZK".to_vec();
    b.resize(177, 0);
    std::fs::write(&short, &b).unwrap();
    let s = short.to_str().unwrap();
    assert_eq!(code(&run(&["execute", "--input", s, "--journal", j])), 2);
    assert_eq!(code(&run(&["prove", "--input", s, "--receipt", r, "--journal", j])), 2);
    let bad = tmp("badmagic.bin");
    std::fs::write(&bad, vec![0u8; 400]).unwrap();
    assert_eq!(code(&run(&["execute", "--input", bad.to_str().unwrap(), "--journal", j])), 2);
    assert_eq!(code(&run(&["execute", "--input", "/nonexistent/x.bin", "--journal", j])), 2);
}

#[test]
fn prove_refuses_dev_mode() {
    let inp = tmp("dev_in.bin");
    let mut b = b"QSZK".to_vec();
    b.resize(400, 0);
    std::fs::write(&inp, &b).unwrap();
    let (r, j) = (tmp("dev_r.bin"), tmp("dev_j.bin"));
    let o = Command::new(BIN)
        .args(["prove", "--input", inp.to_str().unwrap(), "--receipt", r.to_str().unwrap(), "--journal", j.to_str().unwrap()])
        .env("RISC0_DEV_MODE", "1")
        .output()
        .unwrap();
    assert_eq!(code(&o), 6, "{}", String::from_utf8_lossy(&o.stderr));
    assert!(!r.exists());
}

#[test]
fn allow_dev_needs_dev_suffix_dev_mode() {
    let inp = tmp("dev2_in.bin");
    let mut b = b"QSZK".to_vec();
    b.resize(400, 0);
    std::fs::write(&inp, &b).unwrap();
    let (r, j) = (tmp("dev2_r.bin"), tmp("dev2_j.bin"));
    let o = Command::new(BIN)
        .args(["prove", "--allow-dev", "--input", inp.to_str().unwrap(), "--receipt", r.to_str().unwrap(), "--journal", j.to_str().unwrap()])
        .env("RISC0_DEV_MODE", "1")
        .output()
        .unwrap();
    assert_eq!(code(&o), 2);
}

#[test]
fn verify_garbage_receipt_is_4() {
    let (r, e) = (tmp("garbage.bin"), tmp("pub.bin"));
    std::fs::write(&r, b"this is not a receipt").unwrap();
    std::fs::write(&e, vec![0u8; 146]).unwrap();
    let o = run(&["verify", "--receipt", r.to_str().unwrap(), "--expect", e.to_str().unwrap()]);
    assert_eq!(code(&o), 4);
    // bad --expect length is an argument error
    std::fs::write(&e, vec![0u8; 5]).unwrap();
    assert_eq!(code(&run(&["verify", "--receipt", r.to_str().unwrap(), "--expect", e.to_str().unwrap()])), 2);
}

#[test]
fn image_id_is_64_hex() {
    let o = run(&["image-id"]);
    assert_eq!(code(&o), 0);
    let s = String::from_utf8(o.stdout).unwrap();
    let s = s.trim();
    assert_eq!(s.len(), 64);
    assert!(s.chars().all(|c| c.is_ascii_hexdigit()));
}

fn execute_case(k: &str, batch: &str, rel: &str, tag: &str) {
    let inp = make_input(k, batch, rel, &format!("exec_{}.bin", tag));
    let j = tmp(&format!("exec_{}.journal", tag));
    let s = tmp(&format!("exec_{}.json", tag));
    let o = run(&["execute", "--input", inp.to_str().unwrap(), "--journal", j.to_str().unwrap(), "--stats", s.to_str().unwrap()]);
    assert_eq!(code(&o), 0, "{}", String::from_utf8_lossy(&o.stderr));
    let journal = std::fs::read(&j).unwrap();
    let input = std::fs::read(&inp).unwrap();
    assert_eq!(journal.len(), 146);
    assert_eq!(journal, &input[..146]);
    let stats = std::fs::read_to_string(&s).unwrap();
    assert!(stats.contains("\"user_cycles\"") && stats.contains("\"cycles\""));
    eprintln!("{}", stats);
}

#[test]
fn execute_relation1_k2_batch4_journal_matches_input() {
    execute_case("2", "4", "1", "r1");
}

#[test]
fn execute_relation2_journal_matches_input() {
    execute_case("2", "4", "2", "r2");
}

#[test]
fn execute_tampered_input_is_3() {
    let inp = make_input("2", "4", "2", "tamper");
    let mut b = std::fs::read(&inp).unwrap();
    b[82] ^= 1; // flip a bit of the commitment C
    std::fs::write(&inp, &b).unwrap();
    let j = tmp("tamper.journal");
    let o = run(&["execute", "--input", inp.to_str().unwrap(), "--journal", j.to_str().unwrap()]);
    assert_eq!(code(&o), 3);
    assert!(String::from_utf8_lossy(&o.stderr).contains("guest-failed"));
}

#[test]
fn verify_refuses_dev_mode() {
    let (r, e) = (tmp("vdev_r.bin"), tmp("vdev_e.bin"));
    std::fs::write(&r, b"x").unwrap();
    std::fs::write(&e, vec![0u8; 146]).unwrap();
    let o = Command::new(BIN)
        .args(["verify", "--receipt", r.to_str().unwrap(), "--expect", e.to_str().unwrap()])
        .env("RISC0_DEV_MODE", "1")
        .output()
        .unwrap();
    assert_eq!(code(&o), 6, "{}", String::from_utf8_lossy(&o.stderr));
}
