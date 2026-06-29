"""Tensor-network-structured ansatz benchmark on a small TFIM.

Compares a nearest-neighbor Jastrow/MPS-style ansatz against a matched-parameter
hardware-efficient Ry + CX-chain ansatz. Both are optimized with the same
seeded coordinate-descent routine and compared to exact diagonalization.

Reads:  <root>/configs/config.json
Writes: <root>/results/metrics.json
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "configs" / "config.json"
RESULTS_PATH = ROOT / "results" / "metrics.json"

I2 = np.eye(2)
Z = np.array([[1.0, 0.0], [0.0, -1.0]])
X = np.array([[0.0, 1.0], [1.0, 0.0]])


def _kron_list(mats: list[np.ndarray]) -> np.ndarray:
    out = mats[0]
    for mat in mats[1:]:
        out = np.kron(out, mat)
    return out


def tfim_hamiltonian(n: int, j_coupling: float, h_field: float) -> np.ndarray:
    """H = -J sum_i Z_i Z_{i+1} - h sum_i X_i for an open chain."""
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


def parameter_count(n: int) -> int:
    return 2 * n - 1


def structured_state(params: np.ndarray, n: int) -> np.ndarray:
    """Nearest-neighbor Jastrow state, a compact MPS-style positive ansatz."""
    local = params[:n]
    pair = params[n:]
    amps = []
    for basis in range(2 ** n):
        z = np.array([1.0 if ((basis >> (n - 1 - k)) & 1) == 0 else -1.0 for k in range(n)])
        log_amp = float(np.dot(local, z))
        log_amp += sum(float(pair[i] * z[i] * z[i + 1]) for i in range(n - 1))
        amps.append(np.exp(np.clip(log_amp, -20.0, 20.0)))
    state = np.array(amps, dtype=float)
    return state / np.linalg.norm(state)


def hardware_efficient_state(params: np.ndarray, n: int) -> np.ndarray:
    """Matched-parameter Ry + CX-chain ansatz with 2n-1 trainable angles."""
    state = np.zeros(2 ** n)
    state[0] = 1.0
    for q in range(n):
        state = apply_single(state, ry(params[q]), q, n)
    for q in range(n - 1):
        state = apply_cx(state, q, q + 1, n)
    for q in range(n - 1):
        state = apply_single(state, ry(params[n + q]), q + 1, n)
    return state / np.linalg.norm(state)


def energy(params: np.ndarray, H: np.ndarray, n: int, ansatz: str) -> float:
    if ansatz == "structured":
        psi = structured_state(params, n)
    elif ansatz == "hardware_efficient":
        psi = hardware_efficient_state(params, n)
    else:
        raise ValueError(f"unknown ansatz: {ansatz}")
    return float(psi @ H @ psi)


def optimize(
    H: np.ndarray,
    n: int,
    ansatz: str,
    *,
    seed: int,
    max_iters: int,
    restarts: int,
    grid: int,
    param_range: list[float],
) -> tuple[float, np.ndarray]:
    """Random-restart coordinate descent over a fixed parameter grid."""
    rng = np.random.default_rng(seed)
    n_params = parameter_count(n)
    lo, hi = float(param_range[0]), float(param_range[1])
    values = np.linspace(lo, hi, grid)

    best_e = float("inf")
    best_p = np.zeros(n_params)
    for _ in range(restarts):
        params = rng.uniform(lo, hi, n_params)
        current = energy(params, H, n, ansatz)
        for _ in range(max_iters):
            improved = False
            for idx in range(n_params):
                best_local_e = current
                best_local_value = params[idx]
                for value in values:
                    trial = params.copy()
                    trial[idx] = value
                    trial_e = energy(trial, H, n, ansatz)
                    if trial_e < best_local_e:
                        best_local_e = trial_e
                        best_local_value = value
                if best_local_e < current - 1e-9:
                    params[idx] = best_local_value
                    current = best_local_e
                    improved = True
            if not improved:
                break
        if current < best_e:
            best_e = current
            best_p = params.copy()
    return best_e, best_p


def main() -> int:
    cfg = json.loads(CONFIG_PATH.read_text())
    n = int(cfg.get("n_spins", 3))
    j_coupling = float(cfg.get("j_coupling", 1.0))
    h_field = float(cfg.get("h_field", 1.0))
    seed = int(cfg.get("seed", 7))
    max_iters = int(cfg.get("max_iters", 20))
    restarts = int(cfg.get("restarts", 5))
    grid = int(cfg.get("grid", 21))
    stability_seeds = list(cfg.get("stability_seeds", [seed, seed + 1, seed + 2]))
    structured_range = list(cfg.get("structured_param_range", [-2.5, 2.5]))
    hardware_range = list(cfg.get("hardware_param_range", [0.0, 2 * np.pi]))

    t0 = time.time()
    H = tfim_hamiltonian(n, j_coupling, h_field)
    exact_energy = float(np.linalg.eigvalsh(H)[0])

    structured_energy, _ = optimize(
        H,
        n,
        "structured",
        seed=seed,
        max_iters=max_iters,
        restarts=restarts,
        grid=grid,
        param_range=structured_range,
    )
    hardware_energy, _ = optimize(
        H,
        n,
        "hardware_efficient",
        seed=seed,
        max_iters=max_iters,
        restarts=restarts,
        grid=grid,
        param_range=hardware_range,
    )

    stability = []
    for s in stability_seeds:
        e, _ = optimize(
            H,
            n,
            "structured",
            seed=int(s),
            max_iters=max_iters,
            restarts=max(1, restarts - 1),
            grid=grid,
            param_range=structured_range,
        )
        stability.append(e)

    runtime = time.time() - t0
    improvement = hardware_energy - structured_energy
    metrics = {
        "n_spins": n,
        "j_coupling": j_coupling,
        "h_field": h_field,
        "ansatz_layers": 1,
        "parameter_count": parameter_count(n),
        "structured_parameter_count": parameter_count(n),
        "hardware_parameter_count": parameter_count(n),
        "parameter_count_matched": True,
        "seed": seed,
        "exact_energy": round(exact_energy, 6),
        "vqe_energy": round(structured_energy, 6),
        "structured_ansatz_energy": round(structured_energy, 6),
        "baseline_energy": round(hardware_energy, 6),
        "hardware_efficient_energy": round(hardware_energy, 6),
        "energy_error": round(abs(structured_energy - exact_energy), 6),
        "baseline_error": round(abs(hardware_energy - exact_energy), 6),
        "improvement_over_baseline": round(improvement, 6),
        "structured_vs_hardware_delta": round(improvement, 6),
        "stability_seeds": stability_seeds,
        "stability_energies": [round(e, 6) for e in stability],
        "seed_stability_std": round(float(np.std(stability)), 6),
        "runtime_seconds": round(runtime, 3),
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(
        "Tensor ansatz done: "
        f"exact={metrics['exact_energy']} structured={metrics['structured_ansatz_energy']} "
        f"hardware={metrics['hardware_efficient_energy']} "
        f"delta={metrics['structured_vs_hardware_delta']} "
        f"runtime={metrics['runtime_seconds']}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
