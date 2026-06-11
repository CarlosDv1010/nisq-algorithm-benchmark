from typing import List, Dict, Any

import numpy as np
import scipy.stats as stats


def calculate_statistics(data: List[float], confidence: float = 0.95) -> Dict[str, Any]:
    """Resume una lista de fidelidades (en %) en estadísticas descriptivas con IC t-Student."""
    arr = np.array(data)
    n = len(arr)

    if n == 0:
        return {}

    mean = np.mean(arr)
    std = np.std(arr, ddof=1) if n > 1 else 0.0
    median = np.median(arr)
    q25 = np.percentile(arr, 25)
    q75 = np.percentile(arr, 75)

    # Intervalo de confianza basado en t-Student (válido para muestras pequeñas)
    se = std / np.sqrt(n) if n > 0 else 0
    ci_margin = se * stats.t.ppf((1 + confidence) / 2., n - 1) if n > 1 else 0

    return {
        'runs': n,
        'mean': mean,
        'std': std,
        'median': median,
        'min': np.min(arr),
        'max': np.max(arr),
        'q25': q25,
        'q75': q75,
        'ci_margin': ci_margin,
        'ci95_low': mean - ci_margin,
        'ci95_high': mean + ci_margin,
        'mean_ci_str': f"{mean:.4f} +/- {ci_margin:.4f}",
    }


def calculate_circuit_duration(transpiled_circuit, backend_durations) -> float:
    """Duración teórica del circuito en nanosegundos a partir de las latencias del backend."""
    try:
        duration_ns = transpiled_circuit.duration
        if duration_ns is None:
            # Estimación simple cuando no hay scheduling: 300ns por CX y 50ns por SX.
            ops = transpiled_circuit.count_ops()
            duration_ns = ops.get('cx', 0) * 300 + ops.get('sx', 0) * 50
        return float(duration_ns)
    except Exception:
        return 0.0
