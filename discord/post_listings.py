import discord
from discord.ext import commands, tasks
from datetime import datetime, time, timedelta
import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
import util


# Set TEST_MODE to True for testing (loads dummy data)
load_dotenv()
TEST_MODE = os.getenv("TEST_MODE") == "True"
file = open("logging.txt","a")




# Define times for the loop (use 12:00 UTC daily for production)
times = [time(hour=2, minute=15, second=0)]


class PostListings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.posted_today = False  # Prevent multiple posts in TEST_MODE
        self.log_message("Initializing PostListings cog", "INIT")
        self.post_listings.start()


    def log_message(self, message, context):
        timestamp = datetime.now().strftime("[%m/%d|%H:%M:%S]")
        formatted_message = f"{timestamp} | {context} | {message}"
        print(formatted_message,file=file, flush = True)
        print(formatted_message)

    def cog_unload(self):
        self.log_message("Unloading cog. Stopping post_listings loop.", "UNLOAD")
        self.post_listings.cancel()
        file.close()


    @tasks.loop(time=times) if not TEST_MODE else tasks.loop(seconds = 5)
    async def post_listings(self):
        """Posts job listings to the specified channel."""
        if TEST_MODE and self.posted_today:
            self.log_message("Skipping post: already posted today in TEST_MODE.", "POST_LISTINGS")
            return

        self.log_message("____Running post_listings loop____", "POST_LISTINGS")
        self.log_message("Test Mode is " + str(TEST_MODE), "POST_LISTINGS")

        try:
            
            # Load data
            if TEST_MODE:
                listings = [
                    {
                        "title": "Frontend Developer Intern",
                        "company_name": "TechWave",
                        "company_url": "https://www.techwave.com",
                        "url": "https://www.techwave.com/jobs/frontend-dev",
                        "date_posted": datetime.now().timestamp(),
                        "date_updated": datetime.now().timestamp(),
                        "locations": ["Austin, TX", "Remote"],
                        "terms": ["Summer 2025"],
                        "sponsorship": "Yes",
                        "active": True,
                        "is_visible": True,
                    },
                    {
                        "title": "Backend Developer Intern",
                        "company_name": "CodeLabs",
                        "company_url": "https://www.codelabs.com",
                        "url": "https://www.codelabs.com/jobs/backend-dev",
                        "date_posted": datetime.now().timestamp(),
                        "date_updated": datetime.now().timestamp(),
                        "locations": ["Seattle, WA", "Remote"],
                        "terms": ["Summer 2025"],
                        "sponsorship": "No",
                        "active": True,
                        "is_visible": True,
                    },
                    {
                        "title": "Machine Learning Intern",
                        "company_name": "DataMind",
                        "company_url": "https://www.datamind.com",
                        "url": "https://www.datamind.com/jobs/ml-intern",
                        "date_posted": datetime.now().timestamp(),
                        "date_updated": datetime.now().timestamp(),
                        "locations": ["New York, NY"],
                        "terms": ["Summer 2025"],
                        "sponsorship": "Yes",
                        "active": True,
                        "is_visible": True,
                    },
                    {
                        "title": "Game Developer Intern",
                        "company_name": "PixelWorks",
                        "company_url": "https://www.pixelworks.com",
                        "url": "https://www.pixelworks.com/jobs/game-dev",
                        "date_posted": datetime.now().timestamp(),
                        "date_updated": datetime.now().timestamp(),
                        "locations": ["Los Angeles, CA"],
                        "terms": ["Summer 2025"],
                        "sponsorship": "No",
                        "active": True,
                        "is_visible": True,
                    },
                    {
                        "title": "Full Stack Engineer Intern",
                        "company_name": "InnovateX",
                        "company_url": "https://www.innovatex.com",
                        "url": "https://www.innovatex.com/jobs/fullstack-intern",
                        "date_posted": datetime.now().timestamp(),
                        "date_updated": datetime.now().timestamp(),
                        "locations": ["San Francisco, CA"],
                        "terms": ["Summer 2025"],
                        "sponsorship": "Yes",
                        "active": True,
                        "is_visible": True,
                    },
                    {
                        "title": "Cloud Computing Intern",
                        "company_name": "Cloudify",
                        "company_url": "https://www.cloudify.com",
                        "url": "https://www.cloudify.com/jobs/cloud-intern",
                        "date_posted": datetime.now().timestamp(),
                        "date_updated": datetime.now().timestamp(),
                        "locations": ["Remote"],
                        "terms": ["Summer 2025"],
                        "sponsorship": "No",
                        "active": True,
                        "is_visible": True,
                    },
                    {
                        "title": "Cybersecurity Intern",
                        "company_name": "SecureTech",
                        "company_url": "https://www.securetech.com",
                        "url": "https://www.securetech.com/jobs/cyber-intern",
                        "date_posted": datetime.now().timestamp(),
                        "date_updated": datetime.now().timestamp(),
                        "locations": ["Boston, MA"],
                        "terms": ["Summer 2025"],
                        "sponsorship": "Yes",
                        "active": True,
                        "is_visible": True,
                    },
                    {
                        "title": "Mobile App Developer Intern",
                        "company_name": "Appify",
                        "company_url": "https://www.appify.com",
                        "url": "https://www.appify.com/jobs/mobile-dev",
                        "date_posted": datetime.now().timestamp(),
                        "date_updated": datetime.now().timestamp(),
                        "locations": ["Remote", "Chicago, IL"],
                        "terms": ["Summer 2025"],
                        "sponsorship": "No",
                        "active": True,
                        "is_visible": True,
                    },
                    {
                        "title": "Data Analyst Intern",
                        "company_name": "DataWorks",
                        "company_url": "https://www.dataworks.com",
                        "url": "https://www.dataworks.com/jobs/data-analyst",
                        "date_posted": datetime.now().timestamp(),
                        "date_updated": datetime.now().timestamp(),
                        "locations": ["Atlanta, GA"],
                        "terms": ["Summer 2025"],
                        "sponsorship": "Yes",
                        "active": True,
                        "is_visible": True,
                    },
                    {
                        "title": "Blockchain Developer Intern",
                        "company_name": "CryptoBuilders",
                        "company_url": "https://www.cryptobuilders.com",
                        "url": "https://www.cryptobuilders.com/jobs/blockchain-dev",
                        "date_posted": datetime.now().timestamp(),
                        "date_updated": datetime.now().timestamp(),
                        "locations": ["Miami, FL"],
                        "terms": ["Summer 2025"],
                        "sponsorship": "No",
                        "active": True,
                        "is_visible": True,
                    },
                    {
                        "title": "DevOps Engineer Intern",
                        "company_name": "CloudOps",
                        "company_url": "https://www.cloudops.com",
                        "url": "https://www.cloudops.com/jobs/devops-intern",
                        "date_posted": datetime.now().timestamp(),
                        "date_updated": datetime.now().timestamp(),
                        "locations": ["Seattle, WA"],
                        "terms": ["Summer 2025"],
                        "sponsorship": "Yes",
                        "active": True,
                        "is_visible": True,
                    },
                    {
                        "title": "AI Research Intern",
                        "company_name": "BrainAI",
                        "company_url": "https://www.brainai.com",
                        "url": "https://www.brainai.com/jobs/ai-research",
                        "date_posted": datetime.now().timestamp(),
                        "date_updated": datetime.now().timestamp(),
                        "locations": ["Remote"],
                        "terms": ["Summer 2025"],
                        "sponsorship": "No",
                        "active": True,
                        "is_visible": True,
                    },
                    {
                        "title": "Quality Assurance Engineer Intern",
                        "company_name": "Testify",
                        "company_url": "https://www.testify.com",
                        "url": "https://www.testify.com/jobs/qa-engineer",
                        "date_posted": datetime.now().timestamp(),
                        "date_updated": datetime.now().timestamp(),
                        "locations": ["Denver, CO"],
                        "terms": ["Summer 2025"],
                        "sponsorship": "Yes",
                        "active": True,
                        "is_visible": True,
                    }
                ]
            else:
                self.log_message("Fetching listings from S3.", "DATA_LOAD")
                listings = util.getDataFromJSON("listings.json")
                self.log_message(f"Number of listings succesfully fetched from S3: {len(listings)}", "DATA_LOAD") 
        except Exception as e:
            self.log_message(f"Error loading data: {e}", "ERROR")

        try:
            self.log_message("Sorting listings...", "DATA_PROCESS")
            util.sortListings(listings)
            today = datetime.now()
            # Subtract one day to get the previous day
            previous_day = today - timedelta(days=1)
            # Create a datetime object for 9 PM (21:00) on the previous day set to 2 bc of EC2 being on UTC time
            nine_pm_previous_day = datetime(previous_day.year, previous_day.month, previous_day.day, 2, 0, 0)
            # Convert to UNIX timestamp
            earliest_date = int(nine_pm_previous_day.timestamp()) if not TEST_MODE else 0
            self.log_message("UNIX timestamp for earliest_date: "+str(earliest_date), "DATA_PROCESS")
            listings = util.filterSummer(listings, "2025", earliest_date=earliest_date)

        except Exception as e:
            self.log_message("Error during filtering/sorting: " + str(e), "ERROR")

        if not listings:
            self.log_message("No listings to post.", "POST_LISTINGS")
            return
        
        self.log_message(f"{len(listings)} listings to post", "POST_LISTINGS")
        # Prepare embeds
        embeds = []
        for listing in listings:
            embed = self.create_embed(listing)
            embeds.append(embed)

        existing_guilds = util.getDataFromJSON("guilds.json")
        
        # Adding logic for exclusively running the bot in test mode
        if TEST_MODE:
            test_guild_id = int(os.getenv("TEST_GUILD_ID"))
            # replaces existing guilds with only the test guild by id
            existing_guilds = [g for g in existing_guilds if g['id'] == test_guild_id]

        self.log_message("Posting in the following guilds...", "CHANNEL")
        self.log_message(existing_guilds, "CHANNEL")

        for guild in existing_guilds:

            #TODO replace with role_id for specific server once scaling
            role_id = 1314054737863245986 #this is the ping ID for the UF ACM server
            role_mention = f"<@&{role_id}>"

            forum_channel = self.bot.get_channel(guild['channel'])

            if not forum_channel:
                self.log_message(f"Channel {guild['channel']} with ID {forum_channel.id} not found or inaccessible.", "CHANNEL")
                return

            # Determine the thread title based on the season
            thread_title = self.generate_thread_title(today)

            try:
                thread_with_message = await forum_channel.create_thread(
                    name=thread_title,
                    content=f"{role_mention} New internships posted for {thread_title}:"
                )
                thread = thread_with_message.thread  # Extract the thread object
                self.log_message(f"Thread created: {thread.jump_url}", "THREAD")

                # Send batches in the same thread
                await self.send_batches_in_thread(thread, embeds)

            except Exception as e:
                self.log_message(f"Error creating thread or posting messages: {e}")

            if TEST_MODE:
                self.posted_today = True



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
                self.log_message(f"Sent {len(current_batch)} embeds in a batch.", "BATCH")
                current_batch = []

            # Add the current embed to the batch
            current_batch.append(embed)

        self.log_message(f"Final batch size: {len(current_batch)}", "BATCH")
        # Post any remaining embeds
        if current_batch:
            acm_logo = discord.File("acm_logo.png", filename="acm_logo.png")
            await thread.send(embeds=current_batch, files=[acm_logo])
            self.log_message(f"Sent {len(current_batch)} embeds in the final batch.", "BATCH")


    def create_embed(self, listing):
        """Create a Discord Embed object for a job listing."""
        # Purple embed color
        embed = discord.Embed(
            title=listing["title"],
            url=listing["url"],
            description=f"Posted by **{listing['company_name']}**",
            color=0x5865f2,
            timestamp=datetime.fromtimestamp(listing["date_updated"])
        )
        # Add fields for job details
        embed.add_field(name="Locations", value=", ".join(listing["locations"]), inline=False)
        embed.add_field(name="Terms", value=", ".join(listing["terms"]), inline=False)
        embed.add_field(name="Sponsorship", value=listing["sponsorship"], inline=True)

        # Set author with company name and URL
        if listing["company_url"]:
            embed.set_author(name=listing["company_name"], url=listing["company_url"])
            
            # Set thumbnail with company logo
            company_logo = self.get_company_logo(listing)
            embed.set_thumbnail(url=company_logo)
        
        # Set footer with logo and last updated timestamp
        acm_logo_path = "acm_logo.png"
        embed.set_footer(
            text=f"Last updated • {datetime.fromtimestamp(listing['date_updated']).strftime('%m/%d/%Y %I:%M %p')}",
            icon_url=f"attachment://{acm_logo_path}"
        )
        return embed


    def get_company_logo(self, listing):
        """Gets the company logo for a listing"""
        # Check if company logo is already saved
        companies = util.getDataFromJSON("companies.json")
        for company in companies:
            if company['name'] == listing['company_name']:
                return company['logo_url']

        # Create request to Simplify company page, and scrape company logo
        if not listing['company_url'].startswith('https://simplify.jobs/c/'):
            return None
        
        self.log_message(f"Fetching logo for {listing['company_name']}...", "LOGO")
        soup = BeautifulSoup(requests.get(listing["company_url"]).text, 'html.parser')
        img = soup.find(name='img', attrs={'alt': listing['company_name']})
        company_logo = img['src']
        company = {
            'name': listing['company_name'],
            'logo_url': company_logo
        }
        companies.append(company)
        util.saveDataToJSON("companies.json", companies)
        self.log_message(f"Logo found and saved for {listing['company_name']}", "LOGO")

        return company_logo


    def generate_thread_title(self, today):
        """Generate a thread title based on the season and date."""
        def get_season(month):
            if 8 <= month <= 12:  # August to December
                return "FALL"
            elif 1 <= month <= 5:  # January to May
                return "SPRING"
            elif 6 <= month <= 7:  # June to July
                return "SUMMER"
            return "UNKNOWN"

        season = get_season(today.month)
        adjusted_date = today - timedelta(days=1)
        return f"{season} {adjusted_date.year % 100}: {adjusted_date.strftime('%B %d')}"

    @post_listings.before_loop
    async def before_post_listings(self):
        await self.bot.wait_until_ready()
        self.log_message("Bot is ready! Wating for 9:15EST...", "READY")


async def setup(bot):
    """Sets up the PostListings cog."""
    await bot.add_cog(PostListings(bot))
