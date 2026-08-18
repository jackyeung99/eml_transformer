from typing import Any

from eml_transformer.modeling.models.base import (
    BaseForecastModel,
    FloatArray,
)


class StageTwoForecastModel(BaseForecastModel):
    """Placeholder for the stage-two forecasting model."""

    @property
    def requires_exogenous(self) -> bool:
        return False

    def _fit_model(
        self,
        X: FloatArray | None,
        y: FloatArray,
    ) -> None:
        raise NotImplementedError(
            "Stage-two model fitting is not implemented"
        )

    def _forecast_model(
        self,
        *,
        steps: int,
        X: FloatArray | None,
    ) -> FloatArray:
        raise NotImplementedError(
            "Stage-two forecasting is not implemented"
        )

    def _build_diagnostics(
        self,
        X: FloatArray | None,
        y: FloatArray,
    ) -> dict[str, Any]:
        return {}
