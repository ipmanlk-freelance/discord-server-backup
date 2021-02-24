import discord
from backup import BackupCreator


class DiscordClient(discord.Client):
    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))

    async def on_message(self, message):
        handler = BackupCreator(bot=self.user, guild=message.guild)
        backup = await handler.create()


intents = discord.Intents.default()
intents.members = True
client = DiscordClient(intents=intents)
client.run("ODE0MTk0NTAyMjM0NjY5MDY5.YDaTuA.yyw-Or48vxZfprZgRyPsADV8K28")
