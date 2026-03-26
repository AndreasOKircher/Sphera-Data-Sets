import openai
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
API_USERNAME = os.getenv("API_USERNAME")

if not API_TOKEN or not API_USERNAME:
    raise ValueError("Missing API_TOKEN or API_USERNAME in the environment variables")

print("Hello World LLM", flush=True)
print("API_USERNAME:", API_USERNAME, flush=True)
print("API_TOKEN:", API_TOKEN[:5] + "..." + API_TOKEN[-5:], flush=True)

client = openai.OpenAI(
    api_key=API_TOKEN,
    base_url="https://vio.automotive-wan.com:446",
    default_headers={
        "useLegacyCompletionsEndpoint": "false",
        "X-Tenant-ID": "default_tenant"  # Replace if required
    }
)

try:
    models = client.models.list()
    available_models = [model.id for model in models.data]
    print("Available models:", available_models, flush=True)

    intended_model = "VIO:GPT-5-low"
    if intended_model not in available_models:
        raise Exception(f"Model '{intended_model}' not available.")

    print(f"Using model: {intended_model}", flush=True)

    response = client.chat.completions.create(
        model=intended_model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Explain quantum computing"}
        ]
    )
    print("Response:", response.choices[0].message.content, flush=True)

except Exception as e:
    print(f"Error occurred during processing: {e}", flush=True)