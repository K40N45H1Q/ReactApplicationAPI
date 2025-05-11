from os import getenv
from httpx import AsyncClient
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

load_dotenv()

BOT_TOKEN = getenv("BOT_TOKEN")
BOT_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

api = FastAPI()

@api.get("/get_avatar/{user_id}")
async def get_avatar(user_id: int):
    async with AsyncClient() as client:
        response = await client.get(
            f"{BOT_API}/getUserProfilePhotos",
            params={"user_id": user_id, "limit": 1}
        )
        data = response.json()

    if not data.get("ok") or not data["result"]["total_count"]:
        raise HTTPException(status_code=404, detail="Avatar not found!")

    file_id = data["result"]["photos"][0][0]["file_id"]

    async with AsyncClient() as client:
        response = await client.get(
            f"{BOT_API}/getFile",
            params={"file_id": file_id}
        )
        file_data = response.json()

    if not file_data.get("ok"):
        raise HTTPException(status_code=500, detail="Failed to get file info")

    file_path = file_data["result"]["file_path"]

    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    return {"avatar_url": file_url}