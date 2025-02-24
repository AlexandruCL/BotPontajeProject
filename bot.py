import logging
import asyncio
from dotenv import load_dotenv
import os
import datetime
import discord
from discord.ext import commands
from discord.ext.commands import cooldown, BucketType
from discord.ext.commands import CommandOnCooldown
from database import init_db, add_clock_in, update_clock_out, get_clock_times, get_ongoing_sessions, remove_session, get_last_message_timestamp, set_last_message_timestamp, increment_punish_count, get_punish_count, reset_punish_count

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
ALLOWED_PUNISH_CHANNEL_ID = int(os.getenv('ALLOWED_PUNISH_CHANNEL_ID'))
ATRIBUTII_ROLE_NAME=os.getenv('ATRIBUTII_ROLE_NAME')

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
        await ctx.send(f"{ctx.author.mention}, this command is on cooldown. Try again in {error.retry_after:.2f} seconds.", delete_after=3)
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send(f"{ctx.author.mention}, this command does not exist.", delete_after=3)
    else:
        await ctx.send(f"{ctx.author.mention}, an error occurred: {str(error)}", delete_after=3)
        logging.error(f"An error occurred: {str(error)}")

@bot.event
async def on_member_update(before, after):
    hr_role = discord.utils.get(after.guild.roles, name=REQUIRED_HR_ROLE_NAME)
    pd_role = discord.utils.get(after.guild.roles, name=REQUIRED_PD_ROLE_NAME)
    atributii_role=discord.utils.get(after.guild.roles, name=ATRIBUTII_ROLE_NAME)
    if hr_role and hr_role not in before.roles and hr_role in after.roles:
        logging.info(f"User {after.mention} received the {hr_role.mention} role.")
        channel = bot.get_channel(LOGS_CHANNEL_ID)
        role = discord.utils.get(after.guild.roles, name=LOGS_TAG_ROLE_NAME)
        if channel:
            await channel.send(f"|| {role.mention} || User {after.mention} received the {hr_role.mention} role.")
        channel = bot.get_channel(LOGS_CHANNEL_ID)
        role = discord.utils.get(after.guild.roles, name=LOGS_TAG_ROLE_NAME)
        if channel:
            await channel.send(f"|| {role.mention} || User {after.mention} received the {pd_role.mention} role.")
    
    if pd_role and pd_role not in before.roles and pd_role in after.roles:
        if atributii_role and atributii_role not in after.roles:
            await after.add_roles(atributii_role)
            logging.info(f"User {after.mention} received the {pd_role.mention} and {atributii_role.mention} role.")
            channel = bot.get_channel(LOGS_CHANNEL_ID)
            role = discord.utils.get(after.guild.roles, name=LOGS_TAG_ROLE_NAME)
            if channel:
                await channel.send(f"|| {role.mention} || User {after.mention} received the {pd_role.mention} and {atributii_role.mention} role.")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    schedule_next_message()

sending_message = False

def schedule_next_message(next_timestamp=None):
    """Schedule the next message based on the last message timestamp."""
    global sending_message
    if sending_message:
        return  # If a message is being sent, do not schedule another one

    if next_timestamp:
        last_timestamp = next_timestamp
    else:
        last_timestamp = get_last_message_timestamp()
    
    now = datetime.datetime.now()
    if last_timestamp:
        next_timestamp = last_timestamp + datetime.timedelta(days=7)
        logging.info(f"Timestamp: {last_timestamp}, Next timestamp: {next_timestamp}")
        delay = (next_timestamp - now).total_seconds()
        logging.info(f"The delay is {delay}")
        if delay > 0:
            bot.loop.call_later(delay, lambda: asyncio.create_task(send_scheduled_message()))
        else:
            asyncio.create_task(send_scheduled_message())
    else:
        send_scheduled_message()

async def send_scheduled_message():
    """Send the scheduled message and update the timestamp."""
    global sending_message
    sending_message = True  # Set the flag to indicate a message is being sent

    channel = bot.get_channel(RENEW_CHANNEL_ID)
    if channel:
        role = discord.utils.get(channel.guild.roles, name=REQUIRED_HR_ROLE_NAME)
        conducere = discord.utils.get(channel.guild.roles, name=LOGS_TAG_ROLE_NAME)
        if role:
            await channel.send(f"""||{role.mention}{conducere.mention}|| 
                                **Please RENEW the BOT**
                               > Also set the timestamp using ***`/settimestamp 0`*** command.
                               ` This message was sent on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}. The next message will be sent in 7 days.`
                               """)
        else:
            await channel.send("Please RENEW the BOT")
        new_timestamp = datetime.datetime.now()
        set_last_message_timestamp(new_timestamp)
        schedule_next_message(new_timestamp)
        sending_message = False  # Reset the flag after the message is sent

def round_minutes(minutes):
    """Round minutes according to the specified rules"""
    return round(minutes / 5) * 5

def is_allowed_channel(ctx):
    """Check if the command is issued in the allowed channel"""
    return ctx.channel.id == ALLOWED_CHANNEL_ID

def is_allowed_admin_channel(ctx):
    """Check if the command is issued in the allowed admin channel"""
    return ctx.channel.id == ALLOWED_ADMIN_CHANNEL_ID

def is_allowed_punish_channel(ctx):
    """Check if the command is issued in the allowed admin channel"""
    return ctx.channel.id == ALLOWED_PUNISH_CHANNEL_ID

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

def has_required_conducere_role(ctx):
    """Check if the user has the required role"""
    role = discord.utils.get(ctx.guild.roles, name=LOGS_TAG_ROLE_NAME)
    return role in ctx.author.roles

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
            logging.warning(f"User {ctx.author.mention} tried to clock in with an active session. Session started at: {session[0]}")
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
        allowed_channel = ctx.guild.get_channel(ALLOWED_ADMIN_CHANNEL_ID)
        await ctx.send(f"```--------------------------------------------------------```", delete_after=3)
        await ctx.send(f"{ctx.author.mention}, you can only use this command in {allowed_channel.mention}.", delete_after=3)
        return

    if not (has_required_hr_role(ctx) or has_required_conducere_role(ctx)):
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
            report.append(f"**{user.mention}** - Total: ({total_minutes:.2f}) minutes\n{details_text}")
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
                report.append(f"**{member.mention}** - Total: ({total_minutes:.2f}) minutes\n{details_text}")

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
        await ctx.send(f"{ctx.author.mention}, you do not have permission to use this command.", delete_after=3)
        return

    report = []
    current_time = datetime.datetime.now()

    if user:
        user_id = user.id
        sessions = get_clock_times(user_id, current_time.strftime("%Y-%m-%d"))
        for session in sessions:
            if session[1] is None:
                if action == "stop":
                    if (has_required_hr_role(ctx) or has_required_conducere_role(ctx)):
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

@bot.command()
async def addminutes(ctx, user: discord.Member, date: str, minutes: float):
    """Add minutes to the last clock-in session for a user on a specific date or create a new session if none exists"""
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
    
    if sessions:
        last_session = sessions[-1]
        if last_session[1] is None:
            clock_in_time_str = f"{date} {last_session[0]}"
            clock_in_time = datetime.datetime.strptime(clock_in_time_str, "%Y-%m-%d %H:%M:%S")
            new_clock_out_time = clock_in_time + datetime.timedelta(minutes=minutes)
            update_clock_out(user_id, date, new_clock_out_time.strftime("%H:%M:%S"))
            await ctx.send(f"{ctx.author.mention}, added {minutes:.2f} minutes to {user.mention}'s last session. New clock-out time: {new_clock_out_time.strftime('%H:%M:%S')}")
            await user.send(f"Your last session on {date} was extended by {minutes:.2f} minutes by {ctx.author.mention}. New clock-out time: {new_clock_out_time.strftime('%H:%M:%S')}. Next time, please use `/clockin` and `/clockout` to avoid this.")
            logging.warning(f"User {ctx.author.mention} added {minutes:.2f} minutes to {user.mention}'s last session. New clock-out time: {new_clock_out_time.strftime('%H:%M:%S')}.")
            logging.info(f"User {ctx.author.mention} added {minutes:.2f} minutes to {user.mention}'s last session. New clock-out time: {new_clock_out_time.strftime('%H:%M:%S')}.")
        else:
            clock_in_time = datetime.datetime.strptime(f"{date} 00:00:00", "%Y-%m-%d %H:%M:%S")
            new_clock_out_time = clock_in_time + datetime.timedelta(minutes=minutes)
            add_clock_in(user_id, date, clock_in_time.strftime("%H:%M:%S"))
            update_clock_out(user_id, date, new_clock_out_time.strftime("%H:%M:%S"))
            await ctx.send(f"{ctx.author.mention}, created a new session for {user.mention} with {minutes:.2f} minutes. Clock-in time: {clock_in_time.strftime('%H:%M:%S')}, Clock-out time: {new_clock_out_time.strftime('%H:%M:%S')}")
            await user.send(f"Your new session on {date} was created with {minutes:.2f} minutes by {ctx.author.mention}. Clock-in time: {clock_in_time.strftime('%H:%M:%S')}, Clock-out time: {new_clock_out_time.strftime('%H:%M:%S')}. Next time, please use `/clockin` and  `/clockout` to avoid this.")
            logging.warning(f"User {ctx.author.mention} created a new session for {user.mention} with {minutes:.2f} minutes. Clock-in time: {clock_in_time.strftime('%H:%M:%S')}, Clock-out time: {new_clock_out_time.strftime('%H:%M:%S')}.")
            logging.info(f"User {ctx.author.mention} created a new session for {user.mention} with {minutes:.2f} minutes. Clock-in time: {clock_in_time.strftime('%H:%M:%S')}, Clock-out time: {new_clock_out_time.strftime('%H:%M:%S')}.")
    else:
        clock_in_time = datetime.datetime.strptime(f"{date} 00:00:00", "%Y-%m-%d %H:%M:%S")
        new_clock_out_time = clock_in_time + datetime.timedelta(minutes=minutes)
        add_clock_in(user_id, date, clock_in_time.strftime("%H:%M:%S"))
        update_clock_out(user_id, date, new_clock_out_time.strftime("%H:%M:%S"))
        await ctx.send(f"{ctx.author.mention}, created a new session for {user.mention} with {minutes:.2f} minutes. Clock-in time: {clock_in_time.strftime('%H:%M:%S')}, Clock-out time: {new_clock_out_time.strftime('%H:%M:%S')}")
        await user.send(f"Your new session on {date} was created with {minutes:.2f} minutes by {ctx.author.mention}. Clock-in time: {clock_in_time.strftime('%H:%M:%S')}, Clock-out time: {new_clock_out_time.strftime('%H:%M:%S')}. Next time, please use `/clockin` and  `/clockout` to avoid this.")
        logging.warning(f"User {ctx.author.mention} created a new session for {user.mention} with {minutes:.2f} minutes. Clock-in time: {clock_in_time.strftime('%H:%M:%S')}, Clock-out time: {new_clock_out_time.strftime('%H:%M:%S')}.")
        logging.info(f"User {ctx.author.mention} created a new session for {user.mention} with {minutes:.2f} minutes. Clock-in time: {clock_in_time.strftime('%H:%M:%S')}, Clock-out time: {new_clock_out_time.strftime('%H:%M:%S')}.")

@bot.command()
async def renewmessage(ctx):
    """Show the last message timestamp"""
    await ctx.message.delete()
    if ctx.author.id != 286492096242909185:  # Replace YOUR_USER_ID with the actual user ID
        await ctx.send(f"{ctx.author.mention}, you do not have permission to use this command.", delete_after=3)
        return

    last_timestamp = get_last_message_timestamp()
    if last_timestamp:
        await ctx.send(f"Last renew message: {last_timestamp}")
    else:
        await ctx.send("No last message timestamp found.")

@bot.command()
async def settimestamp(ctx, timestamp: str):
    """Set the timestamp of the last message"""
    await ctx.message.delete()
    if not has_required_conducere_role(ctx): # Replace YOUR_USER_ID with the actual user ID
        await ctx.send(f"{ctx.author.mention}, you do not have permission to use this command.", delete_after=3)
        return

    try:
        if(timestamp[0] == '0'):
            new_timestamp = datetime.datetime.now()
        else:
            new_timestamp = datetime.datetime.fromisoformat(timestamp)
        set_last_message_timestamp(new_timestamp)
        await ctx.send(f"> Timestamp set to: ***{new_timestamp}***")
        schedule_next_message(new_timestamp)
    except ValueError:
        await ctx.send(f"Invalid timestamp format. Please use ISO format (YYYY-MM-DDTHH:MM:SS).", delete_after=3)
       

@bot.command()
async def helpme(ctx, action: str = None):
    """Show the list of available commands"""
    await ctx.message.delete()
    if ctx.author.id != 286492096242909185:  # Replace YOUR_USER_ID with the actual user ID
        await ctx.send(f"{ctx.author.mention}, you do not have permission to use this command.", delete_after=3)
        return

    if action == "pontaje":
        help_text = """
        **Available commands:**
        > `/clockin`: Starts the work session
        > `/clockout`: Calculate the time difference between clock-in and clock-out
        """
    elif action == "hr":
        help_text = """
        **Available commands:**
        > `/worked [date] [user]`: Show total worked time for all users or a specific user on a specific date (default: today)
        > `/rmv [user] [date] [index]`: Remove a specific clock-in/out session for a user on a specific date by index (ONLY USE THIS IF YOU NOTICE SOMEONE THAT LEFT HIS CLOCK IN OPENED AND CLOSED IT EVEN THO THEY WERE NOT ONLINE)
        > `/ongoing [user] [action]`: Show ongoing work sessions for all users or stop a specific user's ongoing session
        > `/addminutes [user] [date] [minutes]`: Add minutes to the last clock-in session for a user on a specific date or create a new session if none exists (IF YOU ABUSE THIS COMMAND YOU WILL BE DEMITTED)
        > `/warn [user] [message]`: Warns a user with a warning message ( Gives a warning to the user. ALWAYS PUNISH AFTER REMOVING THE SESSION OR STOPPING THE SESSION)
        > *For the last command, if the message is `reset`, the command will reset the warns count for the user and if the message is `?` the command will show the current warns count for the user*
        > Only CONDUCERE has access to reset. Please use `reset [message]` to reset the warns count for a user and also provide the message.
        > ***When typing the date parameter, use the format YYYY-MM-DD***
        """
    elif action == "admin":
        help_text = """
        **Available commands:**
        > `/renewmessage`: Show the last message timestamp
        > `/settimestamp [timestamp]`: Set the timestamp of the last message
        > `/helpme [action]`: Show the list of available commands for a specific action
        """
    elif action == "warn":
        help_text = """
        **Available commands:**
        > `/warn [user] [message]`: Warns a user with a warning message ( Gives a warning to the user. ALWAYS PUNISH AFTER REMOVING THE SESSION OR STOPPING THE SESSION)
        
         *For the last command, if the message is `reset`, the command will reset the warns count for the user and if the message is `?` the command will show the current warns count for the user*
        > Only CONDUCERE has access to reset. Please use `reset [message]` to reset the warns count for a user and also provide the message.
        """
    await ctx.send(help_text)

@bot.command()
async def say(ctx, *, message: str = None):
    await ctx.message.delete()
    if ctx.author.id != 286492096242909185:  # Replace YOUR_USER_ID with the actual user ID
        await ctx.send(f"{ctx.author.mention}, you do not have permission to use this command.", delete_after=3)
        return
    await ctx.send(message)

@bot.command()
async def warn(ctx, user: discord.Member,*, message: str = None):
    await ctx.message.delete()

    if not message:
        await ctx.send(f"{ctx.author.mention}, please provide a message for the warning.", delete_after=3)
        return

    if not (has_required_hr_role(ctx) or has_required_conducere_role(ctx)):
        await ctx.send(f"{ctx.author.mention}, you do not have permission to use this command.", delete_after=3)
        return

    if not is_allowed_punish_channel(ctx):
        allowed_channel = ctx.guild.get_channel(ALLOWED_PUNISH_CHANNEL_ID)
        await ctx.send(f"{ctx.author.mention}, you can only use this command in {allowed_channel.mention}.", delete_after=3)
        return

    user_id = user.id

    if message.startswith("reset"):
        if not has_required_conducere_role(ctx):
            await ctx.send(f"{ctx.author.mention}, you do not have permission to use this command.", delete_after=3)
            return
        reset_punish_count(user_id)
        reset_message = message[5:]
        afterreset = get_punish_count(user_id)
        await ctx.send(f"""{ctx.author.mention} has reset the warns count for {user.mention}.
                       > {user.mention} now has ***{afterreset} / 5 warnings***.
                       ```{reset_message if reset_message else ''}```""")
        await user.send(f"""Your warns count has been reset by {ctx.author.mention}. 
                        > You now have ***{afterreset} / 5 warnings***.
                        ```{reset_message if reset_message else ''}```""")
        logging.info(f"User {ctx.author.mention} reset the warns count for {user.mention}. ")
        logging.warning(f"User {ctx.author.mention} reset the warns count for {user.mention}.")
        return
    elif message.startswith("?"):
        current_count = get_punish_count(user_id)
        await ctx.send(f"> {user.mention} has ***{current_count} warnings***.")
        return

    current_count = get_punish_count(user_id)

    if current_count >= 5:
        await ctx.send(f"{ctx.author.mention}, {user.mention} has already reached the maximum number of warns.", delete_after=3)
        return

    new_count = increment_punish_count(user_id)
    conducere = discord.utils.get(ctx.guild.roles, name=LOGS_TAG_ROLE_NAME)
    hr = discord.utils.get(ctx.guild.roles, name=REQUIRED_HR_ROLE_NAME)
    if(new_count == 5):
        punish_text=f"""
        ### {user.mention} got a warning from {ctx.author.mention}.
        > This is warning number ***{new_count} / 5***.
        ||{conducere.mention}{hr.mention}||
        ```{message if message else ''}```
        """
    else:
        punish_text=f"""
        ### {user.mention} got a warning from {ctx.author.mention}.
        > This is warning number ***{new_count} / 5***.
        ```{message if message else ''}```
        """
    await ctx.send(punish_text)
    await user.send("You have been given a warning by the HR team. Check the discord server for more information.")

    logging.info(punish_text)
    logging.warning(punish_text)
    
# Run the bot with your token
bot.run(TOKEN)
