import discord
from discord.ext import commands, tasks
from datetime import datetime, time, timedelta
import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
import util
import aiohttp
import asyncio
from logger import Logger

# Set TEST_MODE to True for testing (loads dummy data)
load_dotenv()
TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"
STAGE = os.getenv("STAGE", "true").lower() == "true"
if TEST_MODE or STAGE:
    file = "test_guilds.json"
else:
    file = "guilds.json"
logger = Logger()
logger.log_message(f"TEST_MODE={TEST_MODE} using file {file}", "DEBUG")

# Define times for the loop (use 12:00 UTC daily for production)
times = [time(hour=2, minute=15, second=0)]

class PostListings(commands.Cog):
     # ──────────────────────────────────────────────────────────────────────────
    # Initializes the cog, starts the scheduled loop, and keeps a flag to avoid
    # duplicate posts when running in TEST_MODE every 5 s.
    # ──────────────────────────────────────────────────────────────────────────
    def __init__(self, bot):
        self.bot = bot
        logger.log_message("Initializing PostListings cog - Bot Restarted!", "INFO")
        self.posted_today = False  # Prevent multiple posts in TEST_MODE change this back to false if you would like to test the notifs
        self.post_listings.start()

# ──────────────────────────────────────────────────────────────────────────
    # Gracefully shuts down: stops the loop and closes the custom logger.
    # ──────────────────────────────────────────────────────────────────────────
    def cog_unload(self):
        logger.log_message("Unloading cog. Stopping post_listings loop.", "SUCCESS")
        self.post_listings.cancel()
        logger.close()

# ──────────────────────────────────────────────────────────────────────────
    # Main scheduled task: runs nightly (or every 5 s in TEST_MODE), fetches
    # listings, filters/sorts them, and posts to the configured Discord forums.
    # A heartbeat entry is logged every execution.
    # ──────────────────────────────────────────────────────────────────────────
    @tasks.loop(time=times) if not TEST_MODE else tasks.loop(seconds=15)
    async def post_listings(self):


        """Posts job listings to the specified channel."""
        if TEST_MODE and self.posted_today:
            logger.log_message("Skipping post: already posted today in TEST_MODE. (posted_today is True)", "POST_LISTINGS")
            return

        logger.log_message("____Running post_listings loop____", "POST_LISTINGS")
        logger.log_message("Test Mode is " + str(TEST_MODE), "POST_LISTINGS")

        try:
            # Load data depending on test mode
            logger.log_message("Fetching listings from S3.", "DATA_LOAD")
            listings = util.getDataFromJSON("listings.json")
            if listings is None:
                logger.log_message("Failed to fetch listings from S3", "ERROR")
                return
        except Exception as e:
            logger.log_message(f"Error loading data: {e}", "ERROR")
            return
        logger.log_message(f"Number of listings succesfully fetched from S3: {len(listings)}", "SUCCESS")

        try:
            logger.log_message("Sorting listings...", "DATA_PROCESS")
            util.sortListings(listings)
            # Simple 24-hour lookback for filtering recent listings
            twenty_four_hours_ago = datetime.now() - timedelta(hours=24)
            earliest_date = int(twenty_four_hours_ago.timestamp())
            logger.log_message("UNIX timestamp for earliest_date: " + str(earliest_date), "DATA_PROCESS")
            listings = util.filterByTime(listings, "2025", earliest_date=earliest_date)

        except Exception as e:
            logger.log_message("Error during filtering/sorting: " + str(e), "ERROR")

        if not listings:
            logger.log_message("No listings to post.", "INFO")
            return

        logger.log_message(f"{len(listings)} listings to post", "SUCCESS")
        # Prepare embeds
        embeds = []
        for listing in listings:
            embed = self.create_embed(listing)
            if embed is not None:
                embeds.append(embed)
            else:
                logger.log_message("Skipped invalid listing when creating embed", "WARNING")

        # Adding logic for exclusively running the bot in test mode

        existing_guilds = util.getDataFromJSON(file)
        if existing_guilds is None:
            logger.log_message(f"Failed to fetch guild data from {file}", "ERROR")
            return

        logger.log_message("Posting in the following guilds...", "CHANNEL")
        for guild_data in existing_guilds:
            guild_info = util.get_guild_info(guild_data, self.bot)
            logger.log_message(guild_info, "CHANNEL")

        for guild in existing_guilds:

            role_id = guild.get('role', 0)
            role_mention = f"<@&{role_id}>"

            if 'channel' not in guild:
                 logger.log_message(f"Guild with ID {guild['id']} has not yet configured a forum channel to post to.")
                 return

            forum_channel = self.bot.get_channel(guild['channel'])

            if not forum_channel:
                guild_info = util.get_guild_info(guild, self.bot)
                logger.log_message(f"Channel in guild {guild_info['guild']} with channel ID {guild['channel']} not found or inaccessible.", "WARNING")
                return

            # Determine the thread title based on the date
            today = datetime.now()
            thread_title = self.generate_thread_title(today)

            try:
                thread_with_message = await forum_channel.create_thread(
                    name=thread_title,
                    content=f"{role_mention} New internships posted for {thread_title}:"
                )
                thread = thread_with_message.thread  # Extract the thread object

                guild_info = util.get_guild_info(guild, self.bot)
                guildName = guild_info['guild']

                logger.log_message(f"Thread created: {thread.jump_url} in server: {guildName}", "POST_LISTINGS")

                # Send batches in the same thread
                await self.send_batches_in_thread(thread, embeds)

            except Exception as e:
                logger.log_message(f"Error creating thread or posting messages: {e}", "ERROR")

            guild_info = util.get_guild_info(guild, self.bot)
            guildName = guild_info['guild']

            logger.log_message(f"Job listings posted successfully to guild: {guildName} with id: {guild['id']}.", "SUCCESS")

            if TEST_MODE:
                self.posted_today = True

 # ──────────────────────────────────────────────────────────────────────────
    # Sends embeds in batches of ≤10 or ≤2000 characters inside one thread,
    # respecting Discord’s embed limits.
    # ──────────────────────────────────────────────────────────────────────────
    async def send_batches_in_thread(self, thread, embeds):
        """Send embeds in batches within the same thread."""
        MAX_EMBEDS = 10
        MAX_CHARACTERS = 2000
        current_batch = []

        def calculate_batch_size(embed_batch):
            total_size = 0
            for embed in embed_batch:
                total_size += len(embed.title or "") + len(embed.description or "")
                total_size += sum(len(field.name or "") + len(field.value or "") for field in embed.fields)
                total_size += len(embed.footer.text or "") if embed.footer else 0
            return total_size

        for embed in embeds:
            if len(current_batch) >= MAX_EMBEDS or calculate_batch_size(current_batch + [embed]) > MAX_CHARACTERS:
                # Post the current batch in the same thread
                acm_logo = discord.File("acm_logo.png", filename="acm_logo.png")
                await thread.send(embeds=current_batch, files=[acm_logo])
                logger.log_message(f"Sent {len(current_batch)} embeds in a batch.", "BATCH")
                current_batch = []

            # Add the current embed to the batch
            current_batch.append(embed)

        # Post any remaining embeds
        if current_batch:
            acm_logo = discord.File("acm_logo.png", filename="acm_logo.png")
            await thread.send(embeds=current_batch, files=[acm_logo])
            logger.log_message(f"Sent {len(current_batch)} embeds in the final batch.", "POST_LISTINGS")

 # ──────────────────────────────────────────────────────────────────────────
    # Builds a Discord Embed object from a single listing dictionary.
    # ──────────────────────────────────────────────────────────────────────────
    def create_embed(self, listing):
        """Create a Discord Embed object for a job listing."""
        # Defensive checks for required fields
        if not listing or not isinstance(listing, dict):
            logger.log_message("Invalid listing object passed to create_embed", "ERROR")
            return None
            
        # Purple embed color
        embed = discord.Embed(
            title=listing.get("title", "No Title"),
            url=listing.get("url", ""),
            description=f"Posted by **{listing.get('company_name', 'Unknown Company')}**",
            color=0x5865f2,
            timestamp=datetime.fromtimestamp(listing.get("date_updated", datetime.now().timestamp()))
        )
        # Add fields for job details
        locations = listing.get("locations", [])
        if locations and isinstance(locations, list):
            embed.add_field(name="Locations", value=", ".join(locations), inline=False)
        else:
            embed.add_field(name="Locations", value="Not specified", inline=False)
            
        terms = listing.get("terms", [])
        if terms and isinstance(terms, list):
            embed.add_field(name="Terms", value=", ".join(terms), inline=False)
        else:
            embed.add_field(name="Terms", value="Not specified", inline=False)
            
        embed.add_field(name="Sponsorship", value=listing.get("sponsorship", "Not specified"), inline=True)

        # Set author with company name and URL
        if listing.get("company_url"):
            embed.set_author(name=listing.get("company_name", "Unknown Company"), url=listing.get("company_url"))

            # Set thumbnail with company logo
            company_logo = self.get_company_logo(listing)
            if company_logo:
                embed.set_thumbnail(url=company_logo)

        # Set footer with logo and last updated timestamp
        acm_logo_path = "acm_logo.png"
        embed.set_footer(
            text=f"Last updated • {datetime.fromtimestamp(listing.get('date_updated', datetime.now().timestamp())).strftime('%m/%d/%Y %I:%M %p')}",
            icon_url=f"attachment://{acm_logo_path}"
        )
        return embed

# ──────────────────────────────────────────────────────────────────────────
    # Retrieves (and caches) the company logo URL; scrapes Simplify if needed.
    # ──────────────────────────────────────────────────────────────────────────
    def get_company_logo(self, listing):
        """Gets the company logo for a listing"""
        # Defensive checks
        if not listing or not isinstance(listing, dict):
            return None
            
        company_name = listing.get('company_name')
        company_url = listing.get('company_url')
        
        if not company_name or not company_url:
            return None
        
        # Check if company logo is already saved
        companies = util.getDataFromJSON("companies.json")
        if companies is None:
            companies = []
        
        for company in companies:
            if company.get('name') == company_name:
                return company.get('logo_url')

        # Create request to Simplify company page, and scrape company logo
        if not company_url.startswith('https://simplify.jobs/c/'):
            return None

        try:
            logger.log_message(f"Fetching logo for {company_name}...", "LOGO")
            response = requests.get(company_url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            img = soup.find(name='img', attrs={'alt': company_name})
            
            if not img or 'src' not in img.attrs:
                logger.log_message(f"No logo found for {company_name}", "LOGO")
                return None
                
            company_logo = img['src']
            company = {
                'name': company_name,
                'logo_url': company_logo
            }
            companies.append(company)
            util.saveDataToJSON("companies.json", companies)
            logger.log_message(f"Logo found and saved for {company_name}", "LOGO")

            return company_logo
        except Exception as e:
            logger.log_message(f"Error fetching logo for {company_name}: {e}", "ERROR")
            return None

  # ──────────────────────────────────────────────────────────────────────────
    # Generates the thread title like “SPRING 25: April 26”, based on today’s
    # date and a simple season heuristic.
    # ──────────────────────────────────────────────────────────────────────────
    def generate_thread_title(self, today):
        """Generate a thread title based on the date."""
        adjusted_date = today - timedelta(days=1)
        return adjusted_date.strftime('%B %d, %Y')

 # ──────────────────────────────────────────────────────────────────────────
    # Waits until the bot is connected before starting the loop; logs readiness.
    # ──────────────────────────────────────────────────────────────────────────
    @post_listings.before_loop
    async def before_post_listings(self):
        await self.bot.wait_until_ready()
        logger.log_message("Bot is ready! Wating for 9:15EST...", "READY")

 # ──────────────────────────────────────────────────────────────────────────
    # Catches uncaught exceptions inside the scheduled loop, logs them, and
    # restarts the loop to prevent silent failures.
    # ──────────────────────────────────────────────────────────────────────────
    @post_listings.error
    async def post_error(self, exc):               # <─ NEW
        logger.log_message(f"post_listings crashed: {exc!r}", "ERROR")

        try:
            self.post_listings.restart()
            logger.log_message("post_listings loop restarted", "SUCCESS")
        except RuntimeError:
            pass


async def setup(bot):
    """Sets up the PostListings cog."""
    await bot.add_cog(PostListings(bot))
