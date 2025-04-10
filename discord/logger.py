import asyncio
import discord
import os
from datetime import datetime
import aiohttp

class Logger:
    def __init__(self):
        self.file = open("logging.txt", "a")
        self.test_mode = os.getenv("TEST_MODE") == "True"

    def log_message(self, message, context):
        timestamp = datetime.now().strftime("[%m/%d|%H:%M:%S]")
        formatted_message = f"{timestamp} | {context} | {message}"
        print(formatted_message, file=self.file, flush=True)
        print(formatted_message)

        if context in ["SUCCESS", "SETUP_COMPLETION", "ERROR"]:
            webhook_url = os.getenv("LOG_WEBHOOK_URL_TEST") if self.test_mode else os.getenv("LOG_WEBHOOK_URL")
            if webhook_url:
                asyncio.create_task(self.send_log_message(message, context, webhook_url))

    async def send_log_message(self, message, context, webhook_url):
        content = f"[{context}] {message}"
        async with aiohttp.ClientSession() as session:
            try:
                webhook = discord.Webhook.from_url(webhook_url, session=session)
                await webhook.send(content=content, username="Bot Logger")
            except Exception as e:
                print(f"Failed to send webhook message: {e}")

    def close(self):
        if not self.file.closed:
            self.file.close()

