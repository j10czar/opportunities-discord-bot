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
import time as time_module
from logger import Logger

# Load environment variables
load_dotenv()
TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"
STAGE = os.getenv("STAGE", "false").lower() == "true"

# Make TEST_MODE and STAGE mutually exclusive - TEST_MODE wins if both are true
if TEST_MODE and STAGE:
    STAGE = False

# Initialize logger
logger = Logger()

# Determine which guild file to use
if TEST_MODE or STAGE:
    file = "test_guilds.json"  # Both test and stage modes use test guilds
else:
    file = "guilds.json"  # Production uses production guilds

# Define times for the loop (use 12:00 UTC daily for production)
times = [time(hour=2, minute=15, second=0)]

# Configurable timeout values for HTTP requests
HTTP_REQUEST_TIMEOUT = int(os.getenv("HTTP_REQUEST_TIMEOUT", "10"))  # Default 10 seconds
HTTP_CONNECT_TIMEOUT = int(os.getenv("HTTP_CONNECT_TIMEOUT", "5"))   # Default 5 seconds

class PostListings(commands.Cog):
     # ──────────────────────────────────────────────────────────────────────────
    # Initializes the cog, starts the scheduled loop, and keeps a flag to avoid
    # duplicate posts when running in TEST_MODE every 5 s.
    # ──────────────────────────────────────────────────────────────────────────
    def __init__(self, bot):
        self.bot = bot
        logger.log_message("Initializing PostListings cog - Bot Restarted! Most likely due to codebase update.", "INFO")
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
    @tasks.loop(time=times) if not TEST_MODE else tasks.loop(seconds=5)
    async def post_listings(self):


        """Posts job listings to the specified channel."""
        if TEST_MODE and self.posted_today:
            logger.log_message("Skipping post: already posted today in TEST_MODE. (posted_today is True)", "POST_LISTINGS")
            return

        logger.log_message("____Running post_listings loop____", "POST_LISTINGS")
        logger.log_message(f"TEST_MODE={TEST_MODE}, STAGE={STAGE}", "POST_LISTINGS")

        try:
            # Always load actual listings (no more dummy data in TEST_MODE)
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
            
            # Calculate timestamp dynamically with Docker container offset correction
            # Docker container calculates ~20 hours ahead of SDK, so subtract 1 day
            today = datetime.utcnow()
            # Subtract 2 days instead of 1 to match SDK calculation
            previous_day = today - timedelta(days=2)
            nine_pm_previous_day = datetime(previous_day.year, previous_day.month, previous_day.day, 2, 0, 0)
            earliest_date = int(nine_pm_previous_day.timestamp())
            
            today = datetime.utcnow()
            
            logger.log_message("UNIX timestamp for earliest_date: " + str(earliest_date), "DATA_PROCESS")
            listings = self.filter_upcoming_terms(listings, earliest_date=earliest_date)

        except Exception as e:
            logger.log_message("Error during filtering/sorting: " + str(e), "ERROR")

        if not listings:
            logger.log_message("No listings to post.", "INFO")
            return

        logger.log_message(f"{len(listings)} listings to post", "SUCCESS")
        
        # Pre-fetch company logos for better performance
        logger.log_message("Starting logo prefetch process...", "LOGO")
        prefetch_start_time = time_module.time()
        
        # Track performance metrics for comparison
        performance_metrics = {
            'total_listings': len(listings),
            'prefetch_start_time': prefetch_start_time
        }
        
        try:
            performance_metrics = await self.prefetch_missing_logos(listings, performance_metrics)
            prefetch_duration = time_module.time() - prefetch_start_time
            performance_metrics['total_prefetch_duration'] = prefetch_duration
            
            # Log comprehensive performance summary
            self.log_performance_summary(performance_metrics)
            
        except Exception as e:
            prefetch_duration = time_module.time() - prefetch_start_time
            logger.log_message(f"Logo prefetch failed after {prefetch_duration:.2f} seconds: {e}", "ERROR")
        
        # Prepare embeds using the cached companies data to avoid additional S3 calls
        embeds = []
        
        # Get the companies cache once for all embed creation (cost optimization)
        companies_cache = None
        try:
            companies_cache = util.getDataFromJSON("companies.json")
            logger.log_message("Loaded companies cache for embed creation", "S3")
        except Exception as e:
            logger.log_message(f"Failed to load companies cache for embeds: {e}", "ERROR")
            companies_cache = []
        
        if companies_cache is None:
            companies_cache = []
        
        for listing in listings:
            embed = self.create_embed(listing, companies_cache)
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

            # Determine the thread title based on the season
            thread_title = self.generate_thread_title(today)

            try:
                # In STAGE mode or TEST_MODE, don't include role mentions (no notifications)
                if STAGE or TEST_MODE:
                    content = f"New internships posted for {thread_title}:"
                else:
                    content = f"{role_mention} New internships posted for {thread_title}:"
                
                thread_with_message = await forum_channel.create_thread(
                    name=thread_title,
                    content=content
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

            # Only set posted_today flag in TEST_MODE, not in STAGE mode
            if TEST_MODE and not STAGE:
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
    # Smart filter for upcoming terms - excludes current term, includes future ones
    # ──────────────────────────────────────────────────────────────────────────
    def filter_upcoming_terms(self, listings, earliest_date=0):
        """Filter listings for upcoming terms, excluding the current term."""
        # Use UTC time consistently to match SDK behavior
        current_month = datetime.utcnow().month
        current_year = datetime.utcnow().year
        
        # Determine current term
        if 1 <= current_month <= 5:  # January to May = Spring
            current_term = "Spring"
        elif 6 <= current_month <= 7:  # June to July = Summer  
            current_term = "Summer"
        elif 8 <= current_month <= 12:  # August to December = Fall
            current_term = "Fall"
        
        # Define upcoming terms to look for (proper year rollover)
        upcoming_terms = []
        if current_term == "Spring":
            upcoming_terms = [
                f"Summer {current_year}",
                f"Fall {current_year}", 
                f"Winter {current_year}",  # Winter of current year (Winter 2025 = Winter 2025-2026)
                f"Spring {current_year + 1}"
            ]
        elif current_term == "Summer":
            upcoming_terms = [
                f"Fall {current_year}",
                f"Winter {current_year}",  # Winter of current year (Winter 2025 = Winter 2025-2026)
                f"Spring {current_year + 1}",  # Spring is next year
                f"Summer {current_year + 1}"
            ]
        elif current_term == "Fall":
            upcoming_terms = [
                f"Winter {current_year}",  # Winter of current year (Winter 2025 = Winter 2025-2026)
                f"Spring {current_year + 1}",
                f"Summer {current_year + 1}",
                f"Fall {current_year + 1}"
            ]
        
        logger.log_message(f"Current term: {current_term} {current_year}", "DATA_PROCESS")
        logger.log_message(f"Looking for upcoming terms: {upcoming_terms}", "DATA_PROCESS")
        
        filtered = []
        date_passed = 0
        term_passed = 0
        
        for listing in listings:
            try:
                # First check date filter - only listings from past 24 hours
                listing_date = int(listing.get("date_posted", 0))
                if listing_date < earliest_date:
                    continue
                
                date_passed += 1
                
                # Then check terms
                terms = listing.get("terms", [])
                if not terms or not isinstance(terms, list):
                    continue
                
                # Check if any term matches our upcoming terms
                has_upcoming_term = False
                for term in terms:
                    if term is None:
                        continue
                    term_str = str(term).strip()
                    for upcoming_term in upcoming_terms:
                        if upcoming_term.lower() in term_str.lower():
                            has_upcoming_term = True
                            break
                    if has_upcoming_term:
                        break
                
                if has_upcoming_term:
                    term_passed += 1
                    filtered.append(listing)
                    
            except Exception as e:
                logger.log_message(f"Error filtering listing: {e}", "ERROR")
                continue
        
        logger.log_message(f"Date filter: {date_passed} listings passed", "DATA_PROCESS")
        logger.log_message(f"Term filter: {term_passed} listings passed", "DATA_PROCESS")
        
        logger.log_message(f"Filtered {len(filtered)} listings from {len(listings)} total", "DATA_PROCESS")
        return filtered

 # ──────────────────────────────────────────────────────────────────────────
    # Builds a Discord Embed object from a single listing dictionary.
    # ──────────────────────────────────────────────────────────────────────────
    def create_embed(self, listing, companies_cache=None):
        """Create a Discord Embed object for a job listing."""
        # Defensive checks for required fields
        if not listing or not isinstance(listing, dict):
            logger.log_message("Invalid listing object passed to create_embed", "ERROR")
            return None
        
        # Additional defensive checks for critical fields
        title = listing.get("title")
        if not title or not isinstance(title, str) or not title.strip():
            logger.log_message("Listing missing valid title, skipping embed creation", "ERROR")
            return None
            
        # Purple embed color with defensive timestamp handling
        try:
            date_updated = listing.get("date_updated", datetime.now().timestamp())
            if isinstance(date_updated, (int, float)) and date_updated > 0:
                timestamp = datetime.fromtimestamp(date_updated)
            else:
                timestamp = datetime.now()
        except (ValueError, OSError) as e:
            logger.log_message(f"Invalid timestamp in listing, using current time: {e}", "WARNING")
            timestamp = datetime.now()
            
        embed = discord.Embed(
            title=title.strip(),
            url=listing.get("url", ""),
            description=f"Posted by **{listing.get('company_name', 'Unknown Company')}**",
            color=0x5865f2,
            timestamp=timestamp
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

            # Set thumbnail with company logo - use cached data to avoid additional S3 calls
            company_logo = self.get_company_logo(listing, companies_cache)
            if company_logo is not None and company_logo.strip():
                embed.set_thumbnail(url=company_logo)
            else:
                # Log when logo is missing but continue embed creation gracefully
                company_name = listing.get("company_name", "Unknown Company")
                logger.log_message(f"No logo available for {company_name}, creating embed without thumbnail", "LOGO")

        # Set footer with logo and last updated timestamp - defensive handling
        acm_logo_path = "acm_logo.png"
        try:
            footer_date = listing.get('date_updated', datetime.now().timestamp())
            if isinstance(footer_date, (int, float)) and footer_date > 0:
                footer_timestamp = datetime.fromtimestamp(footer_date)
                footer_text = f"Last updated • {footer_timestamp.strftime('%m/%d/%Y %I:%M %p')}"
            else:
                footer_text = f"Last updated • {datetime.now().strftime('%m/%d/%Y %I:%M %p')}"
        except (ValueError, OSError) as e:
            logger.log_message(f"Invalid footer timestamp in listing, using current time: {e}", "WARNING")
            footer_text = f"Last updated • {datetime.now().strftime('%m/%d/%Y %I:%M %p')}"
            
        embed.set_footer(
            text=footer_text,
            icon_url=f"attachment://{acm_logo_path}"
        )
        return embed

    # ──────────────────────────────────────────────────────────────────────────
    # Helper method to get company logo from cache
    # ──────────────────────────────────────────────────────────────────────────
    def get_company_logo(self, listing, companies_cache=None):
        """Get company logo URL from cache based on company name."""
        if not companies_cache or not isinstance(companies_cache, list):
            return None
        
        company_name = listing.get("company_name")
        if not company_name:
            return None
        
        # Search for company in cache
        for company in companies_cache:
            if company.get("name") == company_name:
                return company.get("logo_url")
        
        return None

 # ──────────────────────────────────────────────────────────────────────────
    # Pre-fetches missing company logos for efficiency (only fetch each company once)
    # ──────────────────────────────────────────────────────────────────────────
    async def prefetch_missing_logos(self, listings, performance_metrics=None):
        """Pre-fetch missing company logos to avoid redundant requests."""
        # Initialize performance metrics if not provided
        if performance_metrics is None:
            performance_metrics = {
                'total_listings': len(listings),
                'prefetch_start_time': time_module.time()
            }
        
        # Track S3 operation metrics
        s3_load_start = time_module.time()
        
        # Get current cached companies with graceful fallback for S3 failures
        companies = None
        try:
            companies = util.getDataFromJSON("companies.json")
            logger.log_message("Successfully loaded companies cache from S3", "S3")
        except Exception as e:
            logger.log_message(f"Failed to load companies cache from S3: {e}", "ERROR")
            logger.log_message("Initializing empty companies cache as fallback", "S3")
        
        # Graceful fallback: initialize empty cache if S3 load fails
        if companies is None:
            companies = []
            logger.log_message("Using empty companies cache due to S3 load failure", "S3")
        
        s3_load_duration = time_module.time() - s3_load_start
        performance_metrics['s3_load_duration'] = s3_load_duration
        logger.log_message(f"S3 companies cache loaded in {s3_load_duration:.3f} seconds", "PERFORMANCE")
        
        # Create a set of already cached company names for fast lookup
        cached_companies = {company.get('name') for company in companies if company.get('name')}
        
        # Track cache efficiency metrics
        performance_metrics['initial_cache_size'] = len(companies)
        performance_metrics['cached_companies_count'] = len(cached_companies)
        
        # Find unique companies that need logos (only for today's active listings)
        companies_to_fetch = set()
        companies_needing_logos = set()  # Companies that actually need logo processing
        
        for listing in listings:
            company_name = listing.get('company_name')
            company_url = listing.get('company_url')
            
            # Only count companies that have valid URLs for logo fetching
            if company_name and company_url and company_url.startswith('https://simplify.jobs/c/'):
                companies_needing_logos.add(company_name)
                
                # Add to fetch list if not already cached
                if company_name not in cached_companies:
                    companies_to_fetch.add((company_name, company_url))
        
        # Calculate cache hit/miss statistics (only for companies that need logo processing)
        performance_metrics['companies_needing_logos'] = len(companies_needing_logos)
        performance_metrics['companies_to_fetch'] = len(companies_to_fetch)
        performance_metrics['cache_hits'] = len(companies_needing_logos) - len(companies_to_fetch)
        
        if len(companies_needing_logos) > 0:
            cache_hit_rate = (performance_metrics['cache_hits'] / len(companies_needing_logos)) * 100
            performance_metrics['cache_hit_rate'] = cache_hit_rate
            logger.log_message(f"Cache hit rate: {cache_hit_rate:.1f}% ({performance_metrics['cache_hits']}/{len(companies_needing_logos)} companies)", "PERFORMANCE")
        
        if not companies_to_fetch:
            logger.log_message("All company logos already cached, skipping logo fetch.", "LOGO")
            performance_metrics['fetch_duration'] = 0
            performance_metrics['successful_fetches'] = 0
            performance_metrics['failed_fetches'] = 0
            performance_metrics['s3_save_duration'] = 0
            return performance_metrics
        
        logger.log_message(f"Pre-fetching logos for {len(companies_to_fetch)} companies...", "LOGO")
        
        # Safety check to prevent excessive API calls
        if len(companies_to_fetch) > 50:
            logger.log_message(f"WARNING: Attempting to fetch {len(companies_to_fetch)} logos - this seems excessive!", "ERROR")
            logger.log_message(f"Total listings: {len(listings)}, Companies needing logos: {len(companies_needing_logos)}", "ERROR")
            logger.log_message("Limiting to first 20 companies to prevent IP ban", "ERROR")
            companies_to_fetch = list(companies_to_fetch)[:20]
        
        # Track success/failure statistics and timing
        successful_fetches = 0
        failed_fetches = 0
        fetch_start_time = time_module.time()
        
        # Fetch missing logos with enhanced error handling
        for company_name, company_url in companies_to_fetch:
            # Wrap each individual logo fetch operation in comprehensive try-catch
            try:
                logger.log_message(f"Fetching logo for {company_name}...", "LOGO")
                
                # Network request with configurable timeout and error handling
                response = None
                try:
                    # Use configurable timeout values with separate connect and read timeouts
                    timeout = (HTTP_CONNECT_TIMEOUT, HTTP_REQUEST_TIMEOUT)
                    response = requests.get(company_url, timeout=timeout)
                    response.raise_for_status()  # Raises HTTPError for bad HTTP status codes
                except requests.exceptions.Timeout:
                    logger.log_message(f"Timeout error fetching logo for {company_name}: Request timed out after {HTTP_REQUEST_TIMEOUT} seconds (connect timeout: {HTTP_CONNECT_TIMEOUT}s)", "ERROR")
                    failed_fetches += 1
                    continue  # Continue processing remaining companies
                except requests.exceptions.HTTPError as e:
                    status_code = response.status_code if response else "Unknown"
                    logger.log_message(f"HTTP error fetching logo for {company_name}: {e} (Status: {status_code})", "ERROR")
                    failed_fetches += 1
                    continue  # Continue processing remaining companies
                except requests.exceptions.ConnectionError as e:
                    logger.log_message(f"Connection error fetching logo for {company_name}: {e}", "ERROR")
                    failed_fetches += 1
                    continue  # Continue processing remaining companies
                except requests.exceptions.RequestException as e:
                    logger.log_message(f"Network error fetching logo for {company_name}: {e}", "ERROR")
                    failed_fetches += 1
                    continue  # Continue processing remaining companies
                
                # HTML parsing with specific error handling
                soup = None
                img = None
                try:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    img = soup.find(name='img', attrs={'alt': company_name})
                except Exception as e:
                    logger.log_message(f"HTML parsing error for {company_name}: {e}", "ERROR")
                    failed_fetches += 1
                    continue  # Continue processing remaining companies
                
                # Logo extraction and validation with error handling
                try:
                    if img and 'src' in img.attrs:
                        company_logo = img['src']
                        if company_logo and company_logo.strip():  # Ensure logo URL is not empty or whitespace
                            company = {
                                'name': company_name,
                                'logo_url': company_logo
                            }
                            companies.append(company)
                            logger.log_message(f"Logo found and saved for {company_name}", "LOGO")
                            successful_fetches += 1
                        else:
                            logger.log_message(f"Empty or invalid logo URL found for {company_name}", "ERROR")
                            failed_fetches += 1
                    else:
                        logger.log_message(f"No logo img tag found for {company_name}", "LOGO")
                        failed_fetches += 1
                except Exception as e:
                    logger.log_message(f"Logo extraction error for {company_name}: {e}", "ERROR")
                    failed_fetches += 1
                    continue  # Continue processing remaining companies
                    
            except Exception as e:
                # Catch-all for any unexpected errors to ensure processing continues
                logger.log_message(f"Unexpected error fetching logo for {company_name}: {e}", "ERROR")
                failed_fetches += 1
                continue  # Ensure we continue processing remaining companies
        
        # Calculate fetch timing
        fetch_duration = time_module.time() - fetch_start_time
        performance_metrics['fetch_duration'] = fetch_duration
        performance_metrics['successful_fetches'] = successful_fetches
        performance_metrics['failed_fetches'] = failed_fetches
        
        # Log summary statistics
        total_companies = len(companies_to_fetch)
        logger.log_message(f"Logo prefetch completed: {successful_fetches}/{total_companies} successful, {failed_fetches}/{total_companies} failed", "LOGO")
        logger.log_message(f"Logo fetching took {fetch_duration:.2f} seconds", "PERFORMANCE")
        
        # Save all new logos to S3 at once, with comprehensive error handling for S3 operations
        s3_save_start = time_module.time()
        if successful_fetches > 0:
            try:
                # Use retry mechanism for critical S3 save operation to handle concurrent operations safely
                util.saveDataToJSON("companies.json", companies, max_retries=3)
                s3_save_duration = time_module.time() - s3_save_start
                performance_metrics['s3_save_duration'] = s3_save_duration
                logger.log_message(f"Successfully saved {successful_fetches} company logos to S3 in {s3_save_duration:.3f} seconds", "PERFORMANCE")
                
                # Log S3 operation efficiency comparison
                estimated_individual_saves = successful_fetches * 0.1  # Estimate 100ms per individual save
                efficiency_improvement = ((estimated_individual_saves - s3_save_duration) / estimated_individual_saves) * 100 if estimated_individual_saves > 0 else 0
                logger.log_message(f"S3 batch save efficiency: {efficiency_improvement:.1f}% faster than {successful_fetches} individual saves", "PERFORMANCE")
                
            except Exception as e:
                s3_save_duration = time_module.time() - s3_save_start
                performance_metrics['s3_save_duration'] = s3_save_duration
                logger.log_message(f"S3 save operation failed after {s3_save_duration:.3f} seconds and all retries: {e}", "ERROR")
                logger.log_message(f"Continuing with posting process despite S3 save failure - {successful_fetches} logos will be lost but posting will proceed", "ERROR")
                # Don't re-raise the exception - allow posting process to continue
        else:
            performance_metrics['s3_save_duration'] = 0
            logger.log_message("No new logos to save to S3", "LOGO")
        
        return performance_metrics

    # ──────────────────────────────────────────────────────────────────────────
    # Logs comprehensive performance summary with before/after optimization metrics
    # ──────────────────────────────────────────────────────────────────────────
    def log_performance_summary(self, performance_metrics):
        """Log comprehensive performance summary and optimization metrics."""
        logger.log_message("=== LOGO PREFETCH PERFORMANCE SUMMARY ===", "PERFORMANCE")
        
        # Basic metrics
        total_listings = performance_metrics.get('total_listings', 0)
        total_duration = performance_metrics.get('total_prefetch_duration', 0)
        logger.log_message(f"Total listings processed: {total_listings}", "PERFORMANCE")
        logger.log_message(f"Total prefetch duration: {total_duration:.2f} seconds", "PERFORMANCE")
        
        # Cache efficiency metrics
        cache_hits = performance_metrics.get('cache_hits', 0)
        unique_companies = performance_metrics.get('unique_companies_in_listings', 0)
        cache_hit_rate = performance_metrics.get('cache_hit_rate', 0)
        logger.log_message(f"Cache efficiency: {cache_hits}/{unique_companies} companies cached ({cache_hit_rate:.1f}% hit rate)", "PERFORMANCE")
        
        # Fetch operation metrics
        successful_fetches = performance_metrics.get('successful_fetches', 0)
        failed_fetches = performance_metrics.get('failed_fetches', 0)
        fetch_duration = performance_metrics.get('fetch_duration', 0)
        companies_to_fetch = performance_metrics.get('companies_to_fetch', 0)
        
        if companies_to_fetch > 0:
            success_rate = (successful_fetches / companies_to_fetch) * 100
            avg_fetch_time = fetch_duration / companies_to_fetch if companies_to_fetch > 0 else 0
            logger.log_message(f"Logo fetching: {successful_fetches}/{companies_to_fetch} successful ({success_rate:.1f}% success rate)", "PERFORMANCE")
            logger.log_message(f"Average fetch time per company: {avg_fetch_time:.3f} seconds", "PERFORMANCE")
        
        # S3 operation metrics
        s3_load_duration = performance_metrics.get('s3_load_duration', 0)
        s3_save_duration = performance_metrics.get('s3_save_duration', 0)
        logger.log_message(f"S3 operations: Load {s3_load_duration:.3f}s, Save {s3_save_duration:.3f}s", "PERFORMANCE")
        
        # Before/after optimization comparison
        logger.log_message("=== OPTIMIZATION IMPACT ANALYSIS ===", "PERFORMANCE")
        
        # Calculate estimated time without optimization (individual fetches during embed creation)
        estimated_individual_fetch_time = unique_companies * 1.5  # Estimate 1.5s per company fetch
        estimated_individual_s3_saves = successful_fetches * 0.1  # Estimate 100ms per individual S3 save
        estimated_unoptimized_time = estimated_individual_fetch_time + estimated_individual_s3_saves
        
        if estimated_unoptimized_time > 0:
            time_savings = estimated_unoptimized_time - total_duration
            efficiency_improvement = (time_savings / estimated_unoptimized_time) * 100
            logger.log_message(f"Estimated time without optimization: {estimated_unoptimized_time:.2f} seconds", "PERFORMANCE")
            logger.log_message(f"Actual optimized time: {total_duration:.2f} seconds", "PERFORMANCE")
            logger.log_message(f"Time savings: {time_savings:.2f} seconds ({efficiency_improvement:.1f}% improvement)", "PERFORMANCE")
        
        # Deduplication efficiency
        total_company_references = total_listings  # Assume each listing has one company
        deduplication_savings = total_company_references - unique_companies
        if total_company_references > 0:
            deduplication_rate = (deduplication_savings / total_company_references) * 100
            logger.log_message(f"Deduplication efficiency: {deduplication_savings}/{total_company_references} duplicate company references eliminated ({deduplication_rate:.1f}%)", "PERFORMANCE")
        
        logger.log_message("=== END PERFORMANCE SUMMARY ===", "PERFORMANCE")

# ──────────────────────────────────────────────────────────────────────────
    # Retrieves (and caches) the company logo URL; scrapes Simplify if needed.
    # ──────────────────────────────────────────────────────────────────────────
    def get_company_logo(self, listing, companies_cache=None):
        """Gets the company logo for a listing"""
        # Defensive checks
        if not listing or not isinstance(listing, dict):
            return None
            
        company_name = listing.get('company_name')
        company_url = listing.get('company_url')
        
        if not company_name or not company_url:
            return None
        
        # Use provided cache or load from S3 (fallback for backward compatibility)
        companies = companies_cache
        if companies is None:
            try:
                companies = util.getDataFromJSON("companies.json")
                logger.log_message("Loading companies cache from S3 (fallback - consider using cached version)", "S3")
            except Exception as e:
                logger.log_message(f"Failed to load companies cache from S3 in get_company_logo: {e}", "ERROR")
                logger.log_message("Proceeding without cache lookup due to S3 failure", "ERROR")
                companies = []
        
        # Graceful fallback: initialize empty cache if S3 load fails
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
            
            # Use configurable timeout values with separate connect and read timeouts
            timeout = (HTTP_CONNECT_TIMEOUT, HTTP_REQUEST_TIMEOUT)
            response = requests.get(company_url, timeout=timeout)
            response.raise_for_status()  # Raises HTTPError for bad HTTP status codes
            
            soup = BeautifulSoup(response.text, 'html.parser')
            img = soup.find(name='img', attrs={'alt': company_name})
            
            if not img or 'src' not in img.attrs:
                logger.log_message(f"No logo found for {company_name}", "LOGO")
                return None
                
            company_logo = img['src']
            if not company_logo or not company_logo.strip():
                logger.log_message(f"Empty or invalid logo URL found for {company_name}", "ERROR")
                return None
                
            company = {
                'name': company_name,
                'logo_url': company_logo
            }
            companies.append(company)
            
            # Save to S3 with error handling and retry mechanism - don't crash if S3 save fails
            try:
                util.saveDataToJSON("companies.json", companies, max_retries=3)
                logger.log_message(f"Logo found and saved for {company_name}", "LOGO")
            except Exception as e:
                logger.log_message(f"Failed to save logo to S3 for {company_name} after all retries: {e}", "ERROR")
                logger.log_message(f"Logo will be used for current session but not persisted", "ERROR")

            return company_logo
            
        except requests.exceptions.Timeout:
            logger.log_message(f"Timeout error fetching logo for {company_name}: Request timed out after {HTTP_REQUEST_TIMEOUT} seconds (connect timeout: {HTTP_CONNECT_TIMEOUT}s)", "ERROR")
            return None
        except requests.exceptions.HTTPError as e:
            logger.log_message(f"HTTP error fetching logo for {company_name}: {e}", "ERROR")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.log_message(f"Connection error fetching logo for {company_name}: {e}", "ERROR")
            return None
        except requests.exceptions.RequestException as e:
            logger.log_message(f"Network error fetching logo for {company_name}: {e}", "ERROR")
            return None
        except Exception as e:
            logger.log_message(f"Unexpected error fetching logo for {company_name}: {e}", "ERROR")
            return None

  # ──────────────────────────────────────────────────────────────────────────
    # Generates the thread title like “SPRING 25: April 26”, based on today’s
    # date and a simple season heuristic.
    # ──────────────────────────────────────────────────────────────────────────
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
