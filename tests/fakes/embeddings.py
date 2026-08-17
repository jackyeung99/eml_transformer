

class FakeEmbeddingModel:
    def __init__(self, **kwargs):
        self.calls = []
        for key, value in kwargs.items():
            setattr(self, key, value)
        

    def embed(
        self,
        texts: list[str],
        batch_size: int,
    ) -> list[list[float]]:
        self.calls.append(
            {
                "texts": texts,
                "batch_size": batch_size,
            }
        )

        return [
            [0.1, 0.2, 0.3]
            for _ in texts
        ]
