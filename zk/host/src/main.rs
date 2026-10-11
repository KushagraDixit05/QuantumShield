//! qs-zk: host CLI for the QuantumShield update-verification guest (docs/zk_interface.md section 9).
use methods::{QS_GUEST_ELF, QS_GUEST_ID};
use risc0_zkvm::{default_executor, default_prover, Digest, ExecutorEnv, ProverOpts, Receipt};
use std::collections::HashMap;
use std::fs::{self, File, OpenOptions};
use std::path::{Path, PathBuf};
use std::process::exit;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

const MIN_INPUT: usize = 178;
const JOURNAL_LEN: usize = 146;

fn die(code: i32, msg: &str) -> ! {
    eprintln!("{}", msg);
    exit(code)
}

fn usage() -> ! {
    die(
        2,
        "usage:\n  qs-zk image-id\n  qs-zk prove --input in.bin --receipt r.bin --journal j.bin [--po2 N] [--kind composite|succinct] [--stats s.json] [--allow-dev]\n  qs-zk verify --receipt r.bin --expect pub.bin [--journal-out j.bin]\n  qs-zk execute --input in.bin --journal j.bin [--stats s.json]",
    )
}

/// Parse `--flag value` pairs; `bool_flags` take no value. Unknown or duplicate flags are errors (exit 2).
fn parse(args: &[String], valued: &[&str], bool_flags: &[&str]) -> HashMap<String, String> {
    let mut m = HashMap::new();
    let mut i = 0;
    while i < args.len() {
        let a = args[i].as_str();
        let name = match a.strip_prefix("--") {
            Some(n) => n,
            None => die(2, &format!("unexpected argument: {}", a)),
        };
        if m.contains_key(name) {
            die(2, &format!("duplicate flag: {}", a));
        }
        if bool_flags.contains(&name) {
            m.insert(name.to_string(), String::new());
            i += 1;
        } else if valued.contains(&name) {
            match args.get(i + 1) {
                Some(v) => {
                    m.insert(name.to_string(), v.clone());
                }
                None => die(2, &format!("missing value for {}", a)),
            }
            i += 2;
        } else {
            die(2, &format!("unknown flag: {}", a));
        }
    }
    m
}

fn need<'a>(m: &'a HashMap<String, String>, k: &str) -> &'a str {
    match m.get(k) {
        Some(v) => v.as_str(),
        None => die(2, &format!("missing required flag --{}", k)),
    }
}

fn image_id_hex() -> String {
    Digest::from(QS_GUEST_ID).as_bytes().iter().map(|b| format!("{:02x}", b)).collect()
}

fn read_input(path: &str) -> Vec<u8> {
    let b = match fs::read(path) {
        Ok(b) => b,
        Err(e) => die(2, &format!("cannot read input {}: {}", path, e)),
    };
    if b.len() < MIN_INPUT {
        die(2, &format!("input too short: {} bytes, need at least {}", b.len(), MIN_INPUT));
    }
    if &b[0..4] != b"QSZK" {
        die(2, "input does not start with magic QSZK");
    }
    b
}

fn pad_words(b: &[u8]) -> Vec<u32> {
    let mut v = b.to_vec();
    while v.len() % 4 != 0 {
        v.push(0);
    }
    v.chunks_exact(4).map(|c| u32::from_le_bytes(c.try_into().unwrap())).collect()
}

fn build_env(input: &[u8], po2: u32) -> ExecutorEnv<'static> {
    ExecutorEnv::builder()
        .segment_limit_po2(po2)
        .write(&(input.len() as u32))
        .unwrap()
        .write_slice(&pad_words(input))
        .build()
        .unwrap()
}

fn write_file(path: &str, data: &[u8]) {
    if let Err(e) = fs::write(path, data) {
        die(1, &format!("cannot write {}: {}", path, e));
    }
}

fn parse_po2(m: &HashMap<String, String>) -> u32 {
    match m.get("po2") {
        None => 18,
        Some(s) => match s.parse::<u32>() {
            Ok(n) if (13..=24).contains(&n) => n,
            _ => die(2, "--po2 must be an integer in 13..=24"),
        },
    }
}

fn status_kb(pid: u32, key: &str) -> Option<u64> {
    let s = fs::read_to_string(format!("/proc/{}/status", pid)).ok()?;
    let l = s.lines().find(|l| l.starts_with(key))?;
    l.split_whitespace().nth(1)?.parse().ok()
}

fn ppid_of(pid: u32) -> Option<u32> {
    let s = fs::read_to_string(format!("/proc/{}/stat", pid)).ok()?;
    // field 4 after the ")" closing the comm
    let rest = &s[s.rfind(')')? + 2..];
    rest.split_whitespace().nth(1)?.parse().ok()
}

/// Polls direct children (r0vm) of this process for VmHWM and keeps the maximum.
fn spawn_child_poller(stop: Arc<AtomicBool>, peak: Arc<AtomicU64>) -> std::thread::JoinHandle<()> {
    let me = std::process::id();
    std::thread::spawn(move || {
        while !stop.load(Ordering::Relaxed) {
            if let Ok(rd) = fs::read_dir("/proc") {
                for e in rd.flatten() {
                    if let Some(pid) = e.file_name().to_str().and_then(|n| n.parse::<u32>().ok()) {
                        if pid != me && ppid_of(pid) == Some(me) {
                            if let Some(kb) = status_kb(pid, "VmHWM") {
                                peak.fetch_max(kb, Ordering::Relaxed);
                            }
                        }
                    }
                }
            }
            std::thread::sleep(Duration::from_millis(200));
        }
    })
}

fn children_maxrss_kb() -> u64 {
    unsafe {
        let mut ru: libc::rusage = std::mem::zeroed();
        if libc::getrusage(libc::RUSAGE_CHILDREN, &mut ru) == 0 {
            ru.ru_maxrss as u64 // Linux: kilobytes
        } else {
            0
        }
    }
}

fn dev_env_set() -> bool {
    std::env::var_os("RISC0_DEV_MODE").is_some()
}

fn repo_root() -> PathBuf {
    // zk/host -> repo root, resolved at build time
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..").components().collect::<PathBuf>()
}

fn take_lock() -> File {
    let path = match std::env::var_os("QS_ZK_LOCK") {
        Some(p) => PathBuf::from(p),
        None => repo_root().join(".zk_prove.lock"),
    };
    let f = match OpenOptions::new().create(true).write(true).open(&path) {
        Ok(f) => f,
        Err(e) => die(6, &format!("cannot open lock {}: {}", path.display(), e)),
    };
    use std::os::unix::io::AsRawFd;
    if unsafe { libc::flock(f.as_raw_fd(), libc::LOCK_EX) } != 0 {
        die(6, &format!("cannot lock {}", path.display()));
    }
    f
}

/// Execute only. Exits 3 with the guest message on any execution failure.
fn run_execute(input: &[u8], po2: u32) -> (Vec<u8>, u64, u64, usize) {
    let env = build_env(input, po2);
    match default_executor().execute(env, QS_GUEST_ELF) {
        Ok(info) => {
            let user: u64 = info.cycles();
            let n = info.segments.len();
            let total: u64 = info.segments.iter().map(|s| 1u64 << s.po2).sum();
            (info.journal.bytes.clone(), user, total, n)
        }
        Err(e) => die(3, &format!("guest-failed: {:#}", e)),
    }
}

fn check_journal_len(j: &[u8]) {
    if j.len() != JOURNAL_LEN {
        die(1, &format!("unexpected journal length {}", j.len()));
    }
}

fn cmd_execute(args: &[String]) {
    let m = parse(args, &["input", "journal", "stats", "po2"], &[]);
    let (inp, jp) = (need(&m, "input"), need(&m, "journal"));
    let po2 = parse_po2(&m);
    let input = read_input(inp);
    let t0 = Instant::now();
    let (journal, user, total, segs) = run_execute(&input, po2);
    let exec_s = t0.elapsed().as_secs_f64();
    check_journal_len(&journal);
    write_file(jp, &journal);
    let stats = format!(
        "{{\"mode\":\"execute\",\"execute_s\":{:.3},\"cycles\":{},\"user_cycles\":{},\"segments\":{},\"po2\":{},\"image_id\":\"{}\"}}",
        exec_s, total, user, segs, po2, image_id_hex()
    );
    if let Some(sp) = m.get("stats") {
        write_file(sp, stats.as_bytes());
    }
    println!("{}", stats);
}

fn cmd_prove(args: &[String]) {
    let m = parse(args, &["input", "receipt", "journal", "po2", "kind", "stats"], &["allow-dev"]);
    let (inp, rp, jp) = (need(&m, "input"), need(&m, "receipt"), need(&m, "journal"));
    let po2 = parse_po2(&m);
    let kind = m.get("kind").map(|s| s.as_str()).unwrap_or("composite");
    let opts = match kind {
        "composite" => ProverOpts::composite(),
        "succinct" => ProverOpts::succinct(),
        _ => die(2, "--kind must be composite or succinct"),
    };
    let dev = dev_env_set();
    let allow_dev = m.contains_key("allow-dev");
    if dev && !allow_dev {
        die(6, "dev mode environment variable is set: refusing to prove (pass --allow-dev for tests)");
    }
    if dev && !rp.ends_with(".dev") {
        die(2, "with --allow-dev the receipt file name must end in .dev");
    }
    let input = read_input(inp);

    let _lock = take_lock(); // held until the end of this function (after the receipt is written)

    // Execution first: any failure here is the relation being false (exit 3) and costs seconds.
    let (exec_journal, _, _, _) = run_execute(&input, po2);
    check_journal_len(&exec_journal);

    let stop = Arc::new(AtomicBool::new(false));
    let peak = Arc::new(AtomicU64::new(0));
    let poller = spawn_child_poller(stop.clone(), peak.clone());
    let env = build_env(&input, po2);
    let t0 = Instant::now();
    let res = default_prover().prove_with_opts(env, QS_GUEST_ELF, &opts);
    let prove_s = t0.elapsed().as_secs_f64();
    stop.store(true, Ordering::Relaxed);
    let _ = poller.join();
    let info = match res {
        Ok(i) => i,
        Err(e) => {
            let t = format!("{:#}", e);
            if t.to_lowercase().contains("guest panic") {
                die(3, &format!("guest-failed: {}", t));
            }
            die(1, &format!("prover error: {}", t));
        }
    };
    let peak_kb = peak.load(Ordering::Relaxed).max(children_maxrss_kb());
    let t1 = Instant::now();
    if let Err(e) = info.receipt.verify(QS_GUEST_ID) {
        die(4, &format!("freshly proved receipt does not verify: {}", e));
    }
    let verify_s = t1.elapsed().as_secs_f64();
    let rb = bincode::serialize(&info.receipt).unwrap();
    let journal = info.receipt.journal.bytes.clone();
    check_journal_len(&journal);
    write_file(rp, &rb);
    write_file(jp, &journal);
    let stats = format!(
        "{{\"mode\":\"prove\",\"prove_s\":{:.2},\"verify_s\":{:.4},\"cycles\":{},\"user_cycles\":{},\"segments\":{},\"receipt_bytes\":{},\"receipt_kind\":\"{}\",\"po2\":{},\"peak_rss_kb\":{},\"peak_rss_source\":\"r0vm child VmHWM polled every 200 ms, max with getrusage(RUSAGE_CHILDREN)\",\"host_rss_kb\":{},\"dev_mode\":{},\"image_id\":\"{}\"}}",
        prove_s,
        verify_s,
        info.stats.total_cycles,
        info.stats.user_cycles,
        info.stats.segments,
        rb.len(),
        kind,
        po2,
        peak_kb,
        status_kb(std::process::id(), "VmHWM").unwrap_or(0),
        dev,
        image_id_hex()
    );
    if let Some(sp) = m.get("stats") {
        write_file(sp, stats.as_bytes());
    }
    println!("{}", stats);
}

fn cmd_verify(args: &[String]) {
    let m = parse(args, &["receipt", "expect", "journal-out"], &[]);
    if dev_env_set() {
        // dev mode would let a fake receipt verify: an aggregator must never run in it
        die(6, "RISC0_DEV_MODE is set: refusing to verify");
    }
    let (rp, ep) = (need(&m, "receipt"), need(&m, "expect"));
    let expect = match fs::read(ep) {
        Ok(b) => b,
        Err(e) => die(2, &format!("cannot read --expect {}: {}", ep, e)),
    };
    if expect.len() != JOURNAL_LEN {
        die(2, &format!("--expect must be {} bytes, got {}", JOURNAL_LEN, expect.len()));
    }
    let rb = match fs::read(rp) {
        Ok(b) => b,
        Err(e) => die(2, &format!("cannot read receipt {}: {}", rp, e)),
    };
    let receipt: Receipt = match bincode::deserialize(&rb) {
        Ok(r) => r,
        Err(e) => die(4, &format!("receipt undecodable: {}", e)),
    };
    let t0 = Instant::now();
    if let Err(e) = receipt.verify(QS_GUEST_ID) {
        die(4, &format!("receipt does not verify: {}", e));
    }
    let verify_s = t0.elapsed().as_secs_f64();
    let journal = &receipt.journal.bytes;
    if let Some(jo) = m.get("journal-out") {
        write_file(jo, journal);
    }
    if journal != &expect {
        die(5, "receipt verifies but the journal differs from --expect");
    }
    println!("{{\"mode\":\"verify\",\"verify_s\":{:.4},\"journal_match\":true,\"image_id\":\"{}\"}}", verify_s, image_id_hex());
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let Some(cmd) = args.first() else { usage() };
    let rest = &args[1..];
    match cmd.as_str() {
        "image-id" => {
            if !rest.is_empty() {
                die(2, "image-id takes no arguments");
            }
            println!("{}", image_id_hex());
        }
        "prove" => cmd_prove(rest),
        "verify" => cmd_verify(rest),
        "execute" => cmd_execute(rest),
        _ => usage(),
    }
}
