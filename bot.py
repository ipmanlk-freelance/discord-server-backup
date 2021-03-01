import discord
from util.backup import BackupCreator
from util.restore import BackupRestorer
from discord.ext import commands
from pathlib import Path
import json

# load config file
with open(Path("setup/config.json")) as f:
    config = json.load(f)

# setup required intents
intents = discord.Intents.default()
intents.members = True

# create new discord.ext bot object with given prefix and intents
bot = commands.Bot(command_prefix=config["PREFIX"], intents=intents)

# listen for events and commands


@bot.event
async def on_ready():
    print('Bot is ready. Logged on as {0}!'.format(bot.user))


@bot.command(name="backup")
async def backup(ctx):
    if ((ctx.guild.owner.id != ctx.author.id) and (str(ctx.author.id) not in config["ALLOWED_MEMBER_IDS"])):
        await ctx.message.reply("You don't have permission to perform this action!.")
        return
    bc = BackupCreator(bot=bot.user, guild=ctx.guild,
                       response_channel=ctx.channel)
    await bc.create()


@bot.command(name="restore")
async def backup(ctx):
    if ((ctx.guild.owner.id != ctx.author.id) and (str(ctx.author.id) not in config["ALLOWED_MEMBER_IDS"])):
        await ctx.message.reply("You don't have permission to perform this action!.")
        return
    br = BackupRestorer(bot=bot)
    await br.restore(guild=ctx.guild, loader=bot.user)

bot.run(config["TOKEN"])
