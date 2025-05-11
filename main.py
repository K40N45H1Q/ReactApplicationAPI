from os import getenv
from httpx import AsyncClient
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

load_dotenv()

BOT_TOKEN = getenv("BOT_TOKEN")
BOT_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
FILE_API = f"https://api.telegram.org/file/bot{BOT_TOKEN}"

api = FastAPI()

@api.get("/avatar/{user_id}")
async def get_avatar(user_id: int):
    async with AsyncClient() as client:
        # Получаем file_id
        resp_photos = await client.get(
            f"{BOT_API}/getUserProfilePhotos",
            params={"user_id": user_id, "limit": 1}
        )
        data = resp_photos.json()

        if not data.get("ok") or not data["result"]["total_count"]:
            raise HTTPException(status_code=404, detail="Avatar not found")

        file_id = data["result"]["photos"][0][0]["file_id"]

        # Получаем путь к файлу
        resp_file = await client.get(
            f"{BOT_API}/getFile",
            params={"file_id": file_id}
        )
        file_data = resp_file.json()

        if not file_data.get("ok"):
            raise HTTPException(status_code=500, detail="Failed to get file info")

        file_path = file_data["result"]["file_path"]
        file_url = f"{FILE_API}/{file_path}"

        # Загружаем сам файл
        file_resp = await client.get(file_url)
        if file_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to download avatar")

        # Отдаём как изображение
        return StreamingResponse(file_resp.aiter_bytes(), media_type="image/jpeg")
