import logging
from dotenv import load_dotenv
import os
import datetime
import discord
from discord.ext import commands
from discord.ext.commands import cooldown, BucketType
from discord.ext.commands import CommandOnCooldown
from database import init_db, add_clock_in, update_clock_out, get_clock_times, get_ongoing_sessions, remove_session, get_last_message_timestamp, set_last_message_timestamp

# Load environment variables from .env file
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
ALLOWED_CHANNEL_ID = int(os.getenv('ALLOWED_CHANNEL_ID'))
ALLOWED_ADMIN_CHANNEL_ID = int(os.getenv('ALLOWED_ADMIN_CHANNEL_ID'))
REQUIRED_PD_ROLE_NAME = os.getenv('REQUIRED_PD_ROLE_NAME')
REQUIRED_HR_ROLE_NAME = os.getenv('REQUIRED_HR_ROLE_NAME')
REQUIRED_PD_SPECIFIC_ROLE_NAME = os.getenv('REQUIRED_PD_SPECIFIC_ROLE_NAME').split(',')
LOGS_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID'))
LOGS_TAG_ROLE_NAME = os.getenv('LOGS_TAG_ROLE_NAME')
RENEW_CHANNEL_ID = int(os.getenv('RENEW_CHANNEL_ID'))

# Initialize database
init_db()

logging.basicConfig(filename='bot.log', level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class DiscordHandler(logging.Handler):
    def __init__(self, bot, channel_id):
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id

    async def send_log(self, message):
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            await channel.send(message)

    def emit(self, record):
        log_entry = self.format(record)
        self.bot.loop.create_task(self.send_log(log_entry))

# Define bot and command prefix
intents = discord.Intents.default()
intents.members = True  # Enable member intents
intents.message_content = True  # Enable message content intent
bot = commands.Bot(command_prefix="/", intents=intents)

# Add the custom handler to the logger
discord_handler = DiscordHandler(bot, LOGS_CHANNEL_ID)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
discord_handler.setFormatter(formatter)

# Set a specific log level for the Discord handler
discord_handler.setLevel(logging.WARNING)  # Only send WARNING and above to Discord

# Add handlers to the logger
logger = logging.getLogger()
logger.addHandler(discord_handler)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, CommandOnCooldown):
        await ctx.message.delete()
        await ctx.send(f"{ctx.author.mention}, this command is on cooldown. Please wait {error.retry_after:.2f} seconds.", delete_after=3)
    else:
        raise error

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    schedule_next_message()

def schedule_next_message():
    """Schedule the next message based on the last message timestamp."""
    last_timestamp = get_last_message_timestamp()
    if last_timestamp:
        now = datetime.datetime.now()
        next_timestamp = last_timestamp + datetime.timedelta(days=7)
        delay = (next_timestamp - now).total_seconds()
        if delay > 0:
            bot.loop.call_later(delay, send_scheduled_message)
        else:
            send_scheduled_message()
    else:
        send_scheduled_message()

def send_scheduled_message():
    """Send the scheduled message and update the timestamp."""
    channel = bot.get_channel(RENEW_CHANNEL_ID)
    if channel:
        role = discord.utils.get(channel.guild.roles, name=REQUIRED_HR_ROLE_NAME)
        if role:
            bot.loop.create_task(channel.send(f"{role.mention} Please RENEW the BOT"))
        else:
            bot.loop.create_task(channel.send("Please RENEW the BOT"))
        set_last_message_timestamp(datetime.datetime.now())
        schedule_next_message()

def round_minutes(minutes):
    """Round minutes according to the specified rules"""
    return round(minutes / 5) * 5

def is_allowed_channel(ctx):
    """Check if the command is issued in the allowed channel"""
    return ctx.channel.id == ALLOWED_CHANNEL_ID

def is_allowed_admin_channel(ctx):
    """Check if the command is issued in the allowed admin channel"""
    return ctx.channel.id == ALLOWED_ADMIN_CHANNEL_ID

# this one is for the pd role check
def has_required_pd_role(ctx):
    """Check if the user has the required role"""
    role = discord.utils.get(ctx.guild.roles, name=REQUIRED_PD_ROLE_NAME)
    return role in ctx.author.roles

# check hr role
def has_required_hr_role(ctx):
    """Check if the user has the required role"""
    role = discord.utils.get(ctx.guild.roles, name=REQUIRED_HR_ROLE_NAME)
    return role in ctx.author.roles

# check asp+ role for ongoing
def has_required_specific_role(ctx):
    user_roles = [role.name for role in ctx.author.roles]
    return any(role in user_roles for role in REQUIRED_PD_SPECIFIC_ROLE_NAME)

@bot.command()
@cooldown(1,1.5,BucketType.default)
async def clockin(ctx):
    """Store the clock-in time for a user"""
    await ctx.message.delete()
    if not is_allowed_channel(ctx):
        allowed_channel = ctx.guild.get_channel(ALLOWED_CHANNEL_ID)
        await ctx.send(f"```--------------------------------------------------------```", delete_after=3)
        await ctx.send(f"{ctx.author.mention}, you can only use this command in {allowed_channel.mention}.", delete_after=3)
        return
    
    if not has_required_pd_role(ctx):
        await ctx.send(f"```--------------------------------------------------------```", delete_after=3)
        await ctx.send(f"{ctx.author.mention}, you do not have permission to use this command.", delete_after=3)
        return

    user_id = ctx.author.id
    current_time = datetime.datetime.now()
    date_str = current_time.strftime("%Y-%m-%d")

    sessions = get_clock_times(user_id, date_str)
    for session in sessions:
        if session[1] is None:
            await ctx.send(f"```--------------------------------------------------------```", delete_after=3)
            await ctx.send(f"{ctx.author.mention}, you already have an active clock-in. Please clock out first.", delete_after=3)
            role = discord.utils.get(ctx.guild.roles, name=LOGS_TAG_ROLE_NAME)
            hr = discord.utils.get(ctx.guild.roles, name=REQUIRED_HR_ROLE_NAME)
            logging.warning(f"{role.mention} {hr.mention}")
            logging.warning(f"User {ctx.author.mention} tried to clock in with an active session.")
            return

    add_clock_in(user_id, date_str, current_time.strftime("%H:%M:%S"))
    await ctx.send(f"```--------------------------------------------------------```")
    await ctx.send(f"{ctx.author.mention} clocked in at {current_time.strftime('%H:%M:%S')} on {date_str}")
    logging.info(f"User {ctx.author} clocked in at {current_time.strftime('%H:%M:%S')} on {date_str}.")

@bot.command()
@cooldown(1,1.5,BucketType.default)
async def clockout(ctx):
    """Calculate the time difference between clock-in and clock-out"""
    await ctx.message.delete()
    if not is_allowed_channel(ctx):
        allowed_channel = ctx.guild.get_channel(ALLOWED_CHANNEL_ID)
        await ctx.send(f"```--------------------------------------------------------```", delete_after=3)
        await ctx.send(f"{ctx.author.mention}, you can only use this command in {allowed_channel.mention}.", delete_after=3)
        return

    if not has_required_pd_role(ctx):
        await ctx.send(f"```--------------------------------------------------------```", delete_after=3)
        await ctx.send(f"{ctx.author.mention}, you do not have permission to use this command.", delete_after=3)
        return
    
    user_id = ctx.author.id
    current_time = datetime.datetime.now()
    date_str = current_time.strftime("%Y-%m-%d")

    sessions = get_clock_times(user_id, date_str)
    for session in sessions:
        if session[1] is None:
            update_clock_out(user_id, date_str, current_time.strftime("%H:%M:%S"))
            clock_in_time_str = f"{date_str} {session[0]}"
            clock_in_time = datetime.datetime.strptime(clock_in_time_str, "%Y-%m-%d %H:%M:%S")
            time_diff = current_time - clock_in_time
            minutes = time_diff.total_seconds() / 60
            rounded_minutes = round_minutes(minutes)
            await ctx.send(f"```--------------------------------------------------------```")
            await ctx.send(f"{ctx.author.mention} clocked out at {current_time.strftime('%H:%M:%S')} on {date_str}. Total time: {rounded_minutes:.2f} minutes")
            logging.info(f"User {ctx.author} clocked out at {current_time.strftime('%H:%M:%S')} on {date_str}. Total time: {rounded_minutes:.2f} minutes.")
            return

    await ctx.send(f"```--------------------------------------------------------```", delete_after=3)
    await ctx.send(f"{ctx.author.mention}, you need to clock in first using `/clockin`.", delete_after=3)

@bot.command()
async def worked(ctx, date: str = None, user: discord.Member = None):
    """Show total worked time for all users or a specific user on a specific date (default: today)"""
    await ctx.message.delete()
    if not is_allowed_admin_channel(ctx):
        allowed_channel = ctx.guild.get_channel(ALLOWED_CHANNEL_ID)
        await ctx.send(f"```--------------------------------------------------------```", delete_after=3)
        await ctx.send(f"{ctx.author.mention}, you can only use this command in {allowed_channel.mention}.", delete_after=3)
        return

    if not has_required_hr_role(ctx):
        await ctx.send(f"```--------------------------------------------------------```", delete_after=3)
        await ctx.send(f"{ctx.author.mention}, you do not have permission to use this command.", delete_after=3)
        return

    if date is None:
        # date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")  
        date = datetime.datetime.now().strftime("%Y-%m-%d")  
        
    report = []

    if user:
        user_id = user.id
        sessions = get_clock_times(user_id, date)
        total_minutes = 0
        details = []
        for idx, session in enumerate(sessions, start=1):
            if session[0] and session[1]:
                clock_in_time = datetime.datetime.strptime(session[0], "%H:%M:%S")
                clock_out_time = datetime.datetime.strptime(session[1], "%H:%M:%S")
                minutes = (clock_out_time - clock_in_time).total_seconds() / 60
                rounded_minutes = round_minutes(minutes)
                total_minutes += rounded_minutes
                if(rounded_minutes > 0):
                    details.append(f"{idx}. {session[0]} - {session[1]} ({rounded_minutes:.2f} min)")

        if total_minutes > 0:
            details_text = "\n".join(details)
            report.append(f"**{user.mention}** - Total: {total_minutes:.2f} minutes\n{details_text}")
        else:
            report.append(f"No work sessions found for {user.mention} on {date}.")
    else:
        async for member in ctx.guild.fetch_members(limit=None):
            user_id = member.id
            sessions = get_clock_times(user_id, date)
            total_minutes = 0
            details = []
            for idx, session in enumerate(sessions, start=1):
                if session[0] and session[1]:
                    clock_in_time = datetime.datetime.strptime(session[0], "%H:%M:%S")
                    clock_out_time = datetime.datetime.strptime(session[1], "%H:%M:%S")
                    minutes = (clock_out_time - clock_in_time).total_seconds() / 60
                    rounded_minutes = round_minutes(minutes)
                    total_minutes += rounded_minutes

            if total_minutes > 0:
                details_text = "\n".join(details)
                report.append(f"**{member.mention}** - Total: {total_minutes:.2f} minutes\n{details_text}")

    if report:
        report_text = "\n\n".join(report)
        await ctx.send(f"```--------------------------------------------------------```")
        await ctx.send(f"**Worked time report for {date}:**\n\n{report_text}")
        logging.info(f"User {ctx.author} requested worked time report for {date}.")
    else:
        await ctx.send(f"```--------------------------------------------------------```", delete_after=3)
        await ctx.send(f"No records found for {date}.", delete_after=3)
        logging.info(f"User {ctx.author} requested worked time report for {date}, but no records were found.")

@bot.command()
@cooldown(1,1.5,BucketType.default)
async def rmv(ctx, user: discord.Member, date: str, index: int):
    """Remove a specific clock-in/out session for a user on a specific date by index"""
    await ctx.message.delete()
    if not is_allowed_admin_channel(ctx):
        allowed_channel = ctx.guild.get_channel(ALLOWED_ADMIN_CHANNEL_ID)
        await ctx.send(f"{ctx.author.mention}, you can only use this command in {allowed_channel.mention}.", delete_after=3)
        return

    if not has_required_hr_role(ctx):
        await ctx.send(f"{ctx.author.mention}, you do not have permission to use this command.", delete_after=3)
        return

    user_id = user.id
    sessions = get_clock_times(user_id, date)
    
    if index < 1 or index > len(sessions):
        await ctx.send(f"{ctx.author.mention}, invalid index. Please provide a valid session index.", delete_after=3)
        return

    # Get the session based on the provided index (1-based index)
    session_to_remove = sessions[index - 1]
    clock_in_time = session_to_remove[0]

    remove_session(user_id, date, clock_in_time)
    await ctx.send(f"{ctx.author.mention}, removed session for {user.mention} on {date} at index {index}. Session: {session_to_remove}")
    await user.send(f"Your session {session_to_remove} on {date} was removed by {ctx.author.mention}.")
    logging.warning(f"Command: /rmv, User: {ctx.author.mention}, Target: {user.mention}, Date: {date}, Index: {index}, Session: {session_to_remove}")
    logging.info(f"User {ctx.author.mention} removed session for {user.mention} on {date} at index {index}. Session: {session_to_remove}")


@bot.command()
async def ongoing(ctx, user: discord.Member = None, action: str = None):
    """Show ongoing work sessions for all users or stop a specific user's ongoing session"""
    await ctx.message.delete()
    if not is_allowed_channel(ctx):
        allowed_channel = ctx.guild.get_channel(ALLOWED_CHANNEL_ID)
        await ctx.send(f"```--------------------------------------------------------```", delete_after=3)
        await ctx.send(f"{ctx.author.display_name}, you can only use this command in {allowed_channel.mention}.", delete_after=3)
        return

    if not (has_required_hr_role(ctx) or has_required_specific_role(ctx)):
        await ctx.send(f"```--------------------------------------------------------```", delete_after=3)
        await ctx.send(f"{ctx.author.display_name}, you do not have permission to use this command.", delete_after=3)
        return

    report = []
    current_time = datetime.datetime.now()

    if user:
        user_id = user.id
        sessions = get_clock_times(user_id, current_time.strftime("%Y-%m-%d"))
        for session in sessions:
            if session[1] is None:
                if action == "stop":
                    if has_required_hr_role(ctx):
                        remove_session(user_id, current_time.strftime("%Y-%m-%d"), session[0])
                        await ctx.send(f"```--------------------------------------------------------```")
                        await ctx.send(f"{ctx.author.mention}, stopped and removed clock-in for {user.mention} at {session[0]}.")
                        await user.send(f"Your clock-in on {session[0]} was stopped by {ctx.author.mention}.")
                        logging.info(f"Command: /ongoing stop, User: {ctx.author}, Target: {user}, Session started at: {session[0]}")
                        logging.warning(f"User {ctx.author.mention} stopped and removed clock-in for {user.mention} at {session[0]}.")
                        return
                    else:
                        await ctx.send(f"```--------------------------------------------------------```", delete_after=3)
                        await ctx.send(f"{ctx.author.mention}, you do not have permission to stop ongoing sessions.", delete_after=3)
                        return
                else:
                    report.append(f"**{user.mention}** - Clocked in at {session[0]}")
    else:
        ongoing_sessions = get_ongoing_sessions()
        for user_id, date, clock_in in ongoing_sessions:
            member = ctx.guild.get_member(user_id)
            if member is None:
                member = await bot.fetch_user(user_id)
                if member:
                    report.append(f"**{member.mention}** - Clocked in at {clock_in}")
            else:
                report.append(f"**{member.mention}** - Clocked in at {clock_in}")

    if report:
        await ctx.send(f"```--------------------------------------------------------```")
        await ctx.send("Ongoing work sessions:\n\n" + "\n".join(report))
    else:
        await ctx.send("No ongoing work sessions found.", delete_after=3)

# Run the bot with your token
bot.run(TOKEN)