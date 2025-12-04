import os
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

# Get the key
my_key = os.getenv("API_KEY")

print(f"Key found: {my_key}")