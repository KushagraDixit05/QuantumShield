import oqs
import torch

ALG = "ML-DSA-65"


def test_mldsa_sign_verify_and_tamper():
    with oqs.Signature(ALG) as signer:
        pk = signer.generate_keypair()
        msg = b"quantumshield hello"
        sig = signer.sign(msg)
    with oqs.Signature(ALG) as verifier:
        assert verifier.verify(msg, sig, pk)
        assert not verifier.verify(msg + b"x", sig, pk)
        bad = bytearray(sig); bad[0] ^= 1
        assert not verifier.verify(msg, bytes(bad), pk)


def test_torch_imports():
    assert torch.zeros(2).sum().item() == 0.0
