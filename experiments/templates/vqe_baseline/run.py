"""VQE baseline experiment — variational ground state of a transverse-field
Ising model (TFIM) on a short open chain, compared against an exact
diagonalization reference AND an untrained-ansatz baseline.

This is intentionally TINY and CPU-only (a few 2^N x 2^N dense matrices,
N<=5). It is the runnable, reproducible smoke experiment for the Quantum
Research Hub. All parameters come from ``configs/config.json`` so the same
code is reused across generated experiments.

Reads:  <root>/configs/config.json
Writes: <root>/results/metrics.json   (and prints a one-line summary)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent          # experiment run folder
CONFIG_PATH = ROOT / "configs" / "config.json"
RESULTS_PATH = ROOT / "results" / "metrics.json"

I2 = np.eye(2)
Z = np.array([[1.0, 0.0], [0.0, -1.0]])
X = np.array([[0.0, 1.0], [1.0, 0.0]])


def _kron_list(mats: list[np.ndarray]) -> np.ndarray:
    out = mats[0]
    for m in mats[1:]:
        out = np.kron(out, m)
    return out


def tfim_hamiltonian(n: int, j_coupling: float, h_field: float) -> np.ndarray:
    """H = -J * sum_i Z_i Z_{i+1} - h * sum_i X_i  (open chain)."""
    dim = 2 ** n
    H = np.zeros((dim, dim))
    for i in range(n - 1):
        mats = [I2] * n
        mats[i] = Z
        mats[i + 1] = Z
        H -= j_coupling * _kron_list(mats)
    for i in range(n):
        mats = [I2] * n
        mats[i] = X
        H -= h_field * _kron_list(mats)
    return H


def ry(theta: float) -> np.ndarray:
    c, s = np.cos(theta / 2), np.sin(theta / 2)
    return np.array([[c, -s], [s, c]])


def apply_single(state: np.ndarray, gate: np.ndarray, q: int, n: int) -> np.ndarray:
    mats = [I2] * n
    mats[q] = gate
    return _kron_list(mats) @ state


def apply_cx(state: np.ndarray, control: int, target: int, n: int) -> np.ndarray:
    dim = 2 ** n
    op = np.zeros((dim, dim))
    for basis in range(dim):
        bits = [(basis >> (n - 1 - k)) & 1 for k in range(n)]
        if bits[control] == 1:
            bits[target] ^= 1
        out = 0
        for k in range(n):
            out = (out << 1) | bits[k]
        op[out, basis] = 1.0
    return op @ state


def ansatz_state(params: np.ndarray, n: int, layers: int) -> np.ndarray:
    """Hardware-efficient ansatz: per layer, Ry on each qubit then a CX chain."""
    state = np.zeros(2 ** n)
    state[0] = 1.0  # |00...0>
    p = params.reshape(layers, n)
    for layer in range(layers):
        for q in range(n):
            state = apply_single(state, ry(p[layer, q]), q, n)
        for q in range(n - 1):
            state = apply_cx(state, q, q + 1, n)
    return state


def energy(params: np.ndarray, H: np.ndarray, n: int, layers: int) -> float:
    psi = ansatz_state(params, n, layers)
    return float(psi @ H @ psi)


def optimize(H, n, layers, *, seed, max_iters, restarts, grid):
    """Random-restart coordinate descent (gradient-free, deterministic)."""
    rng = np.random.default_rng(seed)
    n_params = layers * n
    angles = np.linspace(0, 2 * np.pi, grid, endpoint=False)

    # Baseline = best of `restarts*max_iters//4` random parameter sets:
    # represents an *untrained* ansatz at the same parameter count.
    n_random = max(20, restarts * 10)
    baseline_energy = min(
        energy(rng.uniform(0, 2 * np.pi, n_params), H, n, layers) for _ in range(n_random)
    )

    best_e = float("inf")
    best_p = None
    for _ in range(restarts):
        p = rng.uniform(0, 2 * np.pi, n_params)
        e = energy(p, H, n, layers)
        for _ in range(max_iters):
            improved = False
            for idx in range(n_params):
                trial = p.copy()
                best_local_e, best_local_a = e, p[idx]
                for a in angles:
                    trial[idx] = a
                    te = energy(trial, H, n, layers)
                    if te < best_local_e:
                        best_local_e, best_local_a = te, a
                if best_local_e < e - 1e-9:
                    p[idx] = best_local_a
                    e = best_local_e
                    improved = True
            if not improved:
                break
        if e < best_e:
            best_e, best_p = e, p
    return best_e, baseline_energy, best_p


def main() -> int:
    cfg = json.loads(CONFIG_PATH.read_text())
    n = int(cfg.get("n_spins", 3))
    j_coupling = float(cfg.get("j_coupling", 1.0))
    h_field = float(cfg.get("h_field", 1.0))
    layers = int(cfg.get("ansatz_layers", 2))
    seed = int(cfg.get("seed", 7))
    max_iters = int(cfg.get("max_iters", 40))
    restarts = int(cfg.get("restarts", 3))
    grid = int(cfg.get("grid", 12))
    extra_seeds = list(cfg.get("stability_seeds", [seed, seed + 1, seed + 2]))

    t0 = time.time()
    H = tfim_hamiltonian(n, j_coupling, h_field)
    exact_energy = float(np.linalg.eigvalsh(H)[0])

    vqe_energy, baseline_energy, _ = optimize(
        H, n, layers, seed=seed, max_iters=max_iters, restarts=restarts, grid=grid
    )

    # Seed stability: rerun VQE across a few seeds, report spread.
    stability = []
    for s in extra_seeds:
        e, _, _ = optimize(H, n, layers, seed=s, max_iters=max_iters,
                           restarts=max(1, restarts - 1), grid=grid)
        stability.append(e)
    seed_std = float(np.std(stability))

    runtime = time.time() - t0
    metrics = {
        "n_spins": n,
        "j_coupling": j_coupling,
        "h_field": h_field,
        "ansatz_layers": layers,
        "parameter_count": layers * n,
        "seed": seed,
        "exact_energy": round(exact_energy, 6),
        "vqe_energy": round(vqe_energy, 6),
        "baseline_energy": round(baseline_energy, 6),
        "energy_error": round(abs(vqe_energy - exact_energy), 6),
        "baseline_error": round(abs(baseline_energy - exact_energy), 6),
        "improvement_over_baseline": round(baseline_energy - vqe_energy, 6),
        "stability_seeds": extra_seeds,
        "stability_energies": [round(e, 6) for e in stability],
        "seed_stability_std": round(seed_std, 6),
        "runtime_seconds": round(runtime, 3),
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(metrics, indent=2))
    print(
        f"VQE done: exact={metrics['exact_energy']} vqe={metrics['vqe_energy']} "
        f"err={metrics['energy_error']} baseline_err={metrics['baseline_error']} "
        f"runtime={metrics['runtime_seconds']}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
