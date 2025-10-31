import os

OPENAI_API_KEY = "OPENAI_API_KEY" # if you use OpenAI
GROQ_API_KEY   =  "Your groq API" # if you use GroqAI

if not GROQ_API_KEY and not OPENAI_API_KEY:
    raise ValueError("Set GROQ_API_KEY (or OPENAI_API_KEY).")

