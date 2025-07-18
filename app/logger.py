import asyncio
import discord
import os
from datetime import datetime
import aiohttp


LOG_PING_ID = int(os.getenv("LOG_PING_ID", "0"))


class Logger:
    # ──────────────────────────────────────────────────────────────────────
    # Creates/opens the local log file and inspects TEST_MODE.
    # • TEST_MODE true  → route webhooks to LOG_WEBHOOK_URL_TEST
    # • TEST_MODE false → route webhooks to LOG_WEBHOOK_URL
    # ──────────────────────────────────────────────────────────────────────
    def __init__(self):
        self.file = open("logging.txt", "a")
        self.test_mode = os.getenv("TEST_MODE", "true").lower() == "true"

    # ──────────────────────────────────────────────────────────────────────
    # Core public API
    # log_message(msg, context="INFO")
    #   1. Print to file AND stdout with timestamp
    #   2. Mirror to Discord for high-priority contexts
    #      ("SUCCESS", "SETUP_COMPLETION", "ERROR", "INFO")
    #      via an async webhook task
    # ──────────────────────────────────────────────────────────────────────
    def log_message(self, message: str, context: str = "INFO"):
        timestamp = datetime.now().strftime("[%m/%d|%H:%M:%S]")
        formatted_message = f"{timestamp} | {context} | {message}"
        print(formatted_message, file=self.file, flush=True)
        print(formatted_message)

        if context in ["SUCCESS", "SETUP_COMPLETION", "ERROR", "INFO", "WARNING", "DEBUG"]:
            webhook_url = (
                os.getenv("LOG_WEBHOOK_URL_TEST")
                if self.test_mode
                else os.getenv("LOG_WEBHOOK_URL")
            )
            if webhook_url:
                # fire-and-forget; we don’t await so log_message stays sync-friendly
                asyncio.create_task(
                    self.send_log_message(message, context, webhook_url)
                )

    # ──────────────────────────────────────────────────────────────────────
    # Helper coroutine: actually performs the Discord webhook POST.
    # Adds a role ping when context == "ERROR" so humans notice quickly.
    # ──────────────────────────────────────────────────────────────────────
    async def send_log_message(self, message, context, webhook_url):
        role_mention = f"<@&{LOG_PING_ID}>"
        content = (
            f"{role_mention} [{context}] {message}"
            if context == "ERROR"
            else f"[{context}] {message}"
        )
        async with aiohttp.ClientSession() as session:
            try:
                webhook = discord.Webhook.from_url(webhook_url, session=session)
                await webhook.send(content=content, username="Bot Logger")
            except Exception as e:
                # Fallback to console; avoids recursion back into log_message
                print(f"Failed to send webhook message: {e}")

    # ──────────────────────────────────────────────────────────────────────
    # Flush/close the log file (call on cog_unload / graceful shutdown).
    # ──────────────────────────────────────────────────────────────────────
    def close(self):
        if not self.file.closed:
            self.file.close()

