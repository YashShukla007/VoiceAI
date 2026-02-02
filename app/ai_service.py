import random
import asyncio


class AIServiceError(Exception):
    pass


async def mock_transcribe(text: str) -> str:
    # simulate variable latency 1-3s
    await asyncio.sleep(random.uniform(1, 3))
    # 25% chance of failure
    if random.random() < 0.25:
        raise AIServiceError("503 Service Unavailable")
    # rudimentary 'transcription' - echo back
    return text[::-1]  # simple transformation to show work


async def transcribe_with_retry(text: str, max_attempts: int = 5) -> str:
    base = 0.5
    for attempt in range(1, max_attempts + 1):
        try:
            return await mock_transcribe(text)
        except AIServiceError:
            if attempt == max_attempts:
                raise
            await asyncio.sleep(base * (2 ** (attempt - 1)))
