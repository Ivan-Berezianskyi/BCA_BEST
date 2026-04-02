import httpx
from app.core.config import settings

class AIEngine:
    """AI Service to generate flight summaries using LLM."""
    def __init__(self, api_key: str = settings.AI_API_KEY):
        self.api_key = api_key
        
    async def get_flight_summary(self, metrics: dict) -> str:
        """Sends flight metrics to an LLM and returns an analysis summary."""
        # TODO: Send prompt to OpenAI or Anthropic API
        prompt = f"Flight report: Speed {metrics.get('max_horizontal_speed')} ..., suggest if it was successful."
        # result = await self.call_ai(prompt)
        return "AI analysis placeholder: Flight seems normal."
