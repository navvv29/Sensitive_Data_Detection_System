"""
LLM Client — Abstracted Language Model Interface
==================================================
Provides a unified interface to LLM providers (Gemini default, OpenAI alternative).
The provider is configurable via environment variables, making it swappable
without changing downstream code.

Provider selection:
- Set LLM_PROVIDER=gemini (default) and GEMINI_API_KEY
- Set LLM_PROVIDER=openai and OPENAI_API_KEY (alternative)

All LLM calls go through the `generate()` function which handles:
- Provider routing
- Error handling with retry/fallback
- Rate limiting awareness
"""

import os
import time
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class LLMClient:
    """Abstracted LLM client supporting multiple providers.
    
    Usage:
        client = LLMClient()
        response = client.generate("Summarize this document...")
    """
    
    def __init__(self, provider: Optional[str] = None, api_key: Optional[str] = None):
        """Initialize the LLM client.
        
        Args:
            provider: LLM provider ('gemini' or 'openai'). Defaults to env var.
            api_key: API key. Defaults to env var.
        """
        self.provider = provider or os.environ.get("LLM_PROVIDER", "gemini")
        self.api_key = api_key
        self.model_name = None
        self._client = None
        
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the provider-specific client."""
        if self.provider == "gemini":
            self._init_gemini()
        elif self.provider == "openai":
            self._init_openai()
        elif self.provider == "groq":
            self._init_groq()
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
    
    def _init_gemini(self):
        """Initialize Google Gemini client."""
        api_key = self.api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not found. Set it in .env or pass directly."
            )
        
        try:
            from google import genai
            self._client = genai.Client(api_key=api_key)
            self.model_name = "gemini-2.0-flash"
        except ImportError:
            raise ImportError("google-genai package not installed. Run: pip install google-genai")
    
    def _init_openai(self):
        """Initialize OpenAI client."""
        api_key = self.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY not found. Set it in .env or pass directly."
            )
        
        try:
            import openai
            self._client = openai.OpenAI(api_key=api_key)
            self.model_name = "gpt-4o-mini"
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")
            
    def _init_groq(self):
        """Initialize Groq client."""
        api_key = self.api_key or os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not found. Set it in .env or pass directly."
            )
        
        try:
            import groq
            self._client = groq.Groq(api_key=api_key)
            self.model_name = "llama-3.3-70b-versatile"
        except ImportError:
            raise ImportError("groq package not installed. Run: pip install groq")
    
    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_retries: int = 2,
        temperature: float = 0.3,
    ) -> str:
        """Generate a response from the LLM.
        
        Handles retries on transient failures and returns a fallback
        message if all attempts fail (never crashes).
        
        Args:
            prompt: The user prompt to send.
            system_instruction: Optional system-level instruction.
            max_retries: Number of retry attempts on failure.
            temperature: Sampling temperature (0=deterministic, 1=creative).
            
        Returns:
            Generated text response, or fallback error message.
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                if self.provider == "gemini":
                    return self._generate_gemini(prompt, system_instruction, temperature)
                elif self.provider == "openai":
                    return self._generate_openai(prompt, system_instruction, temperature)
                elif self.provider == "groq":
                    return self._generate_groq(prompt, system_instruction, temperature)
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    time.sleep(wait_time)
        
        # All retries exhausted — return graceful fallback
        return (
            f"⚠️ LLM Generation Failed\n\n"
            f"Unable to generate AI response after {max_retries + 1} attempts.\n"
            f"Error: {str(last_error)}\n\n"
            f"Please check your API key configuration and try again."
        )
    
    def _generate_gemini(
        self, prompt: str, system_instruction: Optional[str], temperature: float
    ) -> str:
        """Generate response using Google Gemini."""
        from google.genai import types
        
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=2048,
        )
        
        if system_instruction:
            config.system_instruction = system_instruction
        
        response = self._client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )
        
        return response.text
    
    def _generate_openai(
        self, prompt: str, system_instruction: Optional[str], temperature: float
    ) -> str:
        """Generate response using OpenAI."""
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=2048,
        )
        
        return response.choices[0].message.content
        
    def _generate_groq(
        self, prompt: str, system_instruction: Optional[str], temperature: float
    ) -> str:
        """Generate response using Groq."""
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=2048,
        )
        
        return response.choices[0].message.content
    
    def is_available(self) -> bool:
        """Check if the LLM client is properly configured and reachable.
        
        Returns:
            True if client can generate responses.
        """
        try:
            response = self.generate("Hello, respond with 'OK'.", max_retries=0)
            return "OK" in response or (len(response) > 0 and not response.startswith("⚠️"))
        except Exception:
            return False
