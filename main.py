print("Loading libraries...")
import discord
from discord.ext import commands
from discord.ext import tasks
import logging
import asyncio
import common
import helpcommand
import os
import time
import sys

class Version:
    def __init__(self):
        self.major = 0
        self.minor = 0
        self.patch = 0

def parse_version(versionstring):
    version = Version()
    version.major, version.minor, version.patch = [int(i) for i in versionstring.replace('a','').split('.')]
    return version

def validate_config(config):
    '''Ensures that the configuration data is complete and has the right data types.'''
    VALID_FLAGS = ['owner_id', 'custom_emoji', 'draobmmj_enabled', 'draobmmj_emoji', 'jmmboard_emoji', 'token', 'dbp', 'jmmboard_channel', 'draobmmj_channel']
    FLAG_TYPES = {'owner_id':int, 'custom_emoji':bool, 'draobmmj_enabled':bool, 'draobmmj_emoji':str, 'jmmboard_emoji':str, 'token':str, 'dbp':str, 'jmmboard_channel':str, 'draobmmj_channel':str}
    for flag in VALID_FLAGS:
        try:
            config[flag]
            #check that the element is the proper type (some stuff e.g ids need to be ints)
            #and convert if needed
            try:
                if not isinstance(config[flag], FLAG_TYPES[flag]):
                    config[flag] = FLAG_TYPES[flag](config[flag])
            except:
                print("It looks like something you entered when running setup.sh is in the wrong format. Try running setup.sh again.")
                print(f"If you believe you entered everything correctly, send the following line to tk421#2016.\n{flag}: expected '{FLAG_TYPES[flag].__name__}', got '{type(config[flag]).__name__}'. raw: '{config[flag]}'")
                os._exit(2)
        except:
            print("The configuration file is missing something. Try running setup.sh again.")
            os._exit(1)

def load_config():
    '''Loads configuration data from a file generated by setup.sh, then checks the validity of the data. Returns the loaded data if the check passes.'''
    config = {}
    #Uncomment the following line to suppress KeyErrors. This will break validate_config.
    #import collections; config = collections.defaultdict(lambda: None)
    with open('config', 'r') as configfile:
        for i in configfile.readlines():
            if not i.strip().startswith('#'):
                #split on only the first :, splitting on every one would break emojis
                i = i.strip().split(':',1)
                config[i[0]] = i[1]
    validate_config(config)
    return config

logging.basicConfig(level=logging.INFO)
print("starting...")
config = load_config()
intents = discord.Intents.default()
intents.reactions = True
intents.guilds = True
intents.members = True
bot = commands.Bot(help_command=helpcommand.HelpCommand(), command_prefix="+", owner_id=int(config['owner_id']), intents=intents, activity=discord.Activity(type=discord.ActivityType.playing, name="starting up..."))
bot.start_time = time.time()
bot.logger = logging.getLogger('jmmith')
bot.dbip = 'localhost'
bot.messages = []
bot.database = "maximilian"
bot.dbinst = common.db(bot, config['dbp'])
try:
    bot.dbinst.connect(bot.database)
except pymysql.err.OperationalError:
    bot.logger.critical(f"Couldn't connect to a local database. Trying 10.0.0.51")
    bot.dbip = '10.0.0.51'
    bot.dbinst = common.db(bot, config['dbp'])
    bot.dbinst.connect(bot.database)
bot.cache_lock = asyncio.Lock()
bot.itercount = 0
bot.messagecount = 1
bot.previousinfo = ""
bot.initial_caching = True
if parse_version(discord.__version__).major < 2:
    bot.IS_DPY_2 = False
    bot.logger.warning("It looks like you're running Jmmith using a discord.py version less than 2.0! Jmmith will not work in threads.")
else:
    bot.IS_DPY_2 = True
bot.USE_CUSTOM_EMOJI = config['custom_emoji']
bot.load_extension('jishaku')
bot.load_extension('jmmboardconfig')
bot.load_extension('info')
#maximilian extensions that provide some useful functionality
bot.load_extension('core')
bot.load_extension('errorhandling')

def progress_bar(current, total, barlength, extrainfo):
    percent = float(current) * 100 / total
    arrow   = '-' * int(percent/100 * barlength - 1) + '>'
    spaces  = ' ' * (barlength - len(arrow))
    print(f'Progress: [{arrow}{spaces}] {round(percent)}%   {extrainfo.ljust(len(bot.previousinfo))}', end='\r')
    bot.previousinfo = extrainfo

async def add_to_cache(channel):
    print("Adding channel to cache... \n")
    bot.tempmessages = bot.messages
    #purge anything from this channel that's already in cache
    if bot.initial_caching:
        progress_bar(bot.messagecount, 1000, 50, f"#{channel.name}  Fetching history...")
    print("\n")
    history = await channel.history(limit=None, oldest_first=True).flatten()
    messages = []
    for message in history:
        messages.append(message)
        if bot.initial_caching:
            progress_bar(bot.messagecount, len(history), 50, f'#{channel.name}  {bot.messagecount}/{len(history)} messages')
        bot.messagecount += 1
    for message in bot.tempmessages:
        if message.channel == channel:
            try:
                #for some reason this blocked???????
                await asyncio.sleep(0.001)
                await bot.loop.run_in_executor(None, bot.messages.remove, message)
            except ValueError:
                pass
    for message in messages:
        bot.tempmessages.append(message)
    print("\n Done adding channel to cache.")
    bot.messagecount = 1
    bot.itercount += 1
    total = len(bot.guilds[0].text_channels)
    if bot.IS_DPY_2:
        total += len(bot.guilds[0].threads)
    print(f'{bot.itercount}/{total} channels cached')
    #be polite and wait for a bit before releasing the lock
    await asyncio.sleep(15)

@tasks.loop(minutes=60)
async def update_cache():
    if bot.initial_caching:
        return
    bot.itercount = 0
    async with bot.cache_lock:
        bot.tempmessages = bot.messages
        for i in bot.guilds[0].text_channels:
            await add_to_cache(i)
        if bot.IS_DPY_2:
            for i in bot.guilds[0].threads:
                await add_to_cache(i)

@bot.event
async def on_ready():
    print("ready")
    if not bot.initial_caching:
        return
    print("adding stuff to cache...")
    async with bot.cache_lock:
        for i in bot.guilds[0].text_channels:
            await add_to_cache(i)
        if bot.IS_DPY_2:
            for i in bot.guilds[0].threads:
                await add_to_cache(i)
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=" for 4 or more golden jmms!"))
    print("Done adding stuff to cache.")
    bot.initial_caching = False

@bot.event
async def on_message(message):
    await bot.process_commands(message)
    async with bot.cache_lock:
        bot.messages.append(message)

async def add_to_jmmboard(payload, message, channel, starboardchannel, guild, draobmmj):
    if draobmmj:
        table = "draobmmj"
        starboardchannel = guild.get_channel(900520099302219836)
        embedtext = f".smmjnedlogon erom ro 3 htiw \"dedrawa\" neeb sah {channel.name[::-1]}# ni egassem ruoy ,{message.author.name[::-1]}"
        color = discord.Color.dark_red()
    else:
        table = "jmmboard"
        embedtext = f"Congratulations, {message.author.name}! Your message in #{channel.name} has been awarded with 4 or more golden jmms!"
        color = 0xFDFE00

    if bot.dbinst.insert("maximilian", table, {"message_id":payload.message_id}, "message_id", False, "", False, "", False) == "success":
        embed = discord.Embed(title=embedtext, color=color)
        if message.content:
            if len(message.content) > 1024:
                embed.add_field(name="Content:", value=f"{message.content[:1021]}...", inline=False)
            else:
                embed.add_field(name="Content:", value=message.content, inline=False)
        if len(message.attachments) != 0:
            embed.set_image(url=message.attachments[0].url)
        if not message.content and message.embeds:
            embed.description = "<:blobpaiN:839543891518685225> I can't display embeds."
        embed.add_field(name="???", value="[Go to message](https://discord.com/channels/631316422328451082/" + str(payload.channel_id) + "/" + str(payload.message_id) + ")", inline=False)
        if not bot.IS_DPY_2:
            icon_url = message.author.avatar_url
        else:
            icon_url = str(message.author.avatar.url)
        embed.set_footer(text=f"Original message sent by {message.author.name}#{message.author.discriminator}.", icon_url=icon_url)
        starboardmessage = await starboardchannel.send(embed=embed)
        bot.messages.append(message)
    else:
        print("A message already has 4 or more golden jmms, or there was an error.")

@bot.event
async def on_raw_reaction_add(payload):
    guild = bot.get_guild(631316422328451082)    
    starboardchannel = guild.get_channel(775168255585026049)
    if not bot.IS_DPY_2:
        channel = guild.get_channel(payload.channel_id) 
        if not channel:
            return
    else:
        channel = guild.get_channel_or_thread(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    for each in message.reactions:
        if hasattr(each.emoji, 'id'):
            if each.emoji.id == 774445538409054218 and each.count >= 4:
                await add_to_jmmboard(payload, message, channel, starboardchannel, guild, False)
                break
            elif each.emoji.id == 776612785647910933 and each.count >= 3:
                await add_to_jmmboard(payload, message, channel, starboardchannel, guild, True)
                break

bot.run(config['token'])
