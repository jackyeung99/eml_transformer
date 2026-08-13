from __future__ import annotations

from typing import Any, Protocol

import numpy as np
import pandas as pd
from numpy.typing import NDArray


class ForecastModel(Protocol):
    def fit(
        self,
        features: pd.DataFrame,
        target: pd.Series,
    ) -> Any:
        ...

    def predict(
        self,
        features: pd.DataFrame,
    ) -> NDArray[np.floating[Any]]:
        ...