import base64, requests, litellm, io
from emergentintegrations.llm.utils import get_integration_proxy_url
from dotenv import load_dotenv
import os
load_dotenv("/app/backend/.env")
key = os.environ["EMERGENT_LLM_KEY"]
base = get_integration_proxy_url() + "/llm"
img = requests.get("https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=600&q=70").content
open("/tmp/in.png", "wb").write(img)

try:
    resp = litellm.image_edit(
        model="openai/gpt-image-1",
        image=open("/tmp/in.png", "rb"),
        prompt="Transform this into an elegant watercolor fine-art painting, gallery quality.",
        api_key=key,
        api_base=base,
        n=1,
        size="1024x1024",
    )
    d = resp.data[0]
    b64 = getattr(d, "b64_json", None)
    url = getattr(d, "url", None)
    print("OK  b64?", bool(b64), "url?", bool(url))
    if b64:
        print("b64 len", len(b64))
except Exception as e:
    print("ERR:", str(e)[:300])
