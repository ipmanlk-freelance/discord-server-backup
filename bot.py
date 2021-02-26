import discord
from backup import BackupCreator
from restore import BackupRestorer
from datetime import datetime


class DiscordClient(discord.Client):
    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))

    async def on_message(self, message):
        if (message.author.bot):
            return

        handler = BackupRestorer(bot=self)
        backup = await handler.restore(guild=message.guild, loader=self.user)

        # handler = BackupCreator(bot=self.user, guild=message.guild)
        # backup = await handler.create()

        # embedVar = discord.Embed(
        #     color=0x00ff00)
        # embedVar.timestamp = datetime.utcnow()
        # embedVar.add_field(
        #     name="David", value="Hello, how are you doing?", inline=False)
        # await message.channel.send(embed=embedVar)

        # embedVar = discord.Embed(color=0x00ff00)
        # embedVar.timestamp = datetime.utcnow()
        # embedVar.add_field(
        #     name="Ann", value="I'm good", inline=False)

        # await message.channel.send(embed=embedVar)


intents = discord.Intents.default()
intents.members = True
client = DiscordClient(intents=intents)
client.run("ODE0MTk0NTAyMjM0NjY5MDY5.YDaTuA.yyw-Or48vxZfprZgRyPsADV8K28")
