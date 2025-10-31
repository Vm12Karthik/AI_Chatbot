
# Option 1 (Recommended): Use an environment variable for safety
import os

OPENAI_API_KEY = "Your API Key"

# Option 2: Directly set your OpenAI API key here (less secure)
if not OPENAI_API_KEY:
    raise ValueError("❌ OpenAI API key not found! Please set it in your environment or directly in config.py")
