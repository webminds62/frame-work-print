import asyncio, base64, os, requests
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
key = os.environ["EMERGENT_LLM_KEY"]
img = requests.get("https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=500&q=70").content
b64 = base64.b64encode(img).decode()

async def test(model, with_ref):
    try:
        chat = LlmChat(api_key=key, session_id="t", system_message="art studio").with_model("gemini", model).with_params(modalities=["image", "text"])
        if with_ref:
            msg = UserMessage(text="Turn this photo into an elegant watercolor painting.", file_contents=[ImageContent(b64)])
        else:
            msg = UserMessage(text="A watercolor painting of a golden retriever, plain white background.")
        _, images = await chat.send_message_multimodal_response(msg)
        print("gemini", model, "ref=" + str(with_ref), "=> OK images:", len(images) if images else 0)
    except Exception as e:
        print("gemini", model, "ref=" + str(with_ref), "=> ERR:", str(e)[:200])

async def main():
    await test("gemini-3.1-flash-image-preview", False)
    await test("gemini-3.1-flash-image-preview", True)
    await test("gemini-2.5-flash-image-preview", True)

asyncio.run(main())
