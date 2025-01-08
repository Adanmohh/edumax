import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

try:
    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input="Hello world"
    )
    print("OpenAI API key is valid!")
    print(response)
except Exception as e:
    print(f"Error: {str(e)}")
