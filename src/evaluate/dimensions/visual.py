"""V2 stub: visual evaluation. Activates when PIPELINE_VERSION=v2."""


class VisualEvaluator:
    """Visual dimension evaluation. Stub until V2."""

    async def evaluate(self, ad: object, image_url: str) -> None:
        raise NotImplementedError(
            "Visual evaluation activates in V2. Set PIPELINE_VERSION=v2."
        )
