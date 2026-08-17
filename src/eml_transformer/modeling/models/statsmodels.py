# modeling/models/statsmodels.py

from __future__ import annotations

from typing import Any

import numpy as np


def extract_statsmodels_diagnostics(
    results: Any,
) -> dict[str, Any]:
    parameters = {
        str(name): float(value)
        for name, value in zip(
            results.param_names,
            results.params,
            strict=True,
        )
    }

    standard_errors = {
        str(name): float(value)
        for name, value in zip(
            results.param_names,
            results.bse,
            strict=True,
        )
    }

    p_values = {
        str(name): float(value)
        for name, value in zip(
            results.param_names,
            results.pvalues,
            strict=True,
        )
    }

    residuals = np.asarray(results.resid, dtype=float)
    residuals = residuals[np.isfinite(residuals)]

    diagnostics: dict[str, Any] = {
        "parameters": parameters,
        "standard_errors": standard_errors,
        "p_values": p_values,
        "aic": float(results.aic),
        "bic": float(results.bic),
        "hqic": float(results.hqic),
        "log_likelihood": float(results.llf),
        "residual_count": int(len(residuals)),
    }

    if residuals.size:
        diagnostics.update(
            {
                "residual_mean": float(
                    np.mean(residuals)
                ),
                "residual_std": float(
                    np.std(residuals, ddof=1)
                ),
                "residual_min": float(
                    np.min(residuals)
                ),
                "residual_max": float(
                    np.max(residuals)
                ),
            }
        )

    optimizer_results = getattr(
        results,
        "mle_retvals",
        None,
    )

    if isinstance(optimizer_results, dict):
        if "converged" in optimizer_results:
            diagnostics["converged"] = bool(
                optimizer_results["converged"]
            )

        if "iterations" in optimizer_results:
            diagnostics["iterations"] = int(
                optimizer_results["iterations"]
            )

    return diagnostics