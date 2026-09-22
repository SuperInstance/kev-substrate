# CUDACLAW Pointers — kev-substrate ecosystem

The kev-substrate interweave has been extended with three new projects per
Casey's directive (2026-09-22): "greatly improve it with a more gpu native
version like mojo for any vendor hardware... cudaclaw in engineering it's
horizontal abilities"

## The three projects

1. **[kev-substrate-mojo](https://github.com/SuperInstance/kev-substrate-mojo)**
   - Mojo port of kev-substrate
   - Same substrate, different language
   - Vendor-hardware GPU native (NVIDIA / AMD / Apple / Intel / CPU via MLIR)
   - 884 lines of Mojo across 6 source files + 12 tests

2. **[kev-substrate-competition](https://github.com/SuperInstance/kev-substrate-competition)**
   - Cross-API CUDA/PTX native competition
   - Model APIs compete on horizontal abilities (cells/sec × calibration / cost × power)
   - Three categories: A) Vendor CUDA/PTX, B) Mojo MLIR, C) Novel architectures
   - Prizes: Best Horizontal Abilities, Best Crab, Best Duck, Best Batten

3. **CUDACLAW doctrine**
   - Horizontal-abilities engineering
   - Many small kernels, peer-to-peer, no central coordinator
   - The substrate IS the coordination, not a coordinator
   - Pod, not pack. Claw, not fist.
   - Full docs: [CUDACLAW_DOCTRINE.md](https://github.com/SuperInstance/kev-substrate-competition/blob/main/CUDACLAW_DOCTRINE.md)

## How they interweave with this repo

```
┌─────────────────────────────────────────────────┐
│           SuperInstance/kev-substrate           │  ← YOU ARE HERE (Python)
│   (inference core: PyTorch + transformers)      │
└─────────────────────────────────────────────────┘
                    ▲
                    │ HTTP /v1/systemone
                    │
┌─────────────────────────────────────────────────┐
│      SuperInstance/kev-substrate-mojo           │  ← Sibling (Mojo)
│   (CUDA-native client + chain + canary)         │
└─────────────────────────────────────────────────┘
                    ▲
                    │ same canary hash
                    │ same substrate
                    │
┌─────────────────────────────────────────────────┐
│ SuperInstance/kev-substrate-competition         │  ← Sibling (competition)
│   (benchmark + leaderboard + outreach)          │
└─────────────────────────────────────────────────┘
```

All three speak the same substrate. Same FNV-1a canary. Same prev_hash chain.
Same `/v1/systemone` API. Just different languages and different concerns.

— Filed by Mavis, 2026-09-22
