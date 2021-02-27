import discord
import traceback
import asyncio
import json
import time
import os
from pathlib import Path


class BackupCreator:
    def __init__(self, bot, guild, response_channel=None):
        self.bot = bot
        self.guild = guild
        self.data = {}
        self.response_channel = response_channel

    @staticmethod
    def _overwrites_to_json(overwrites):
        try:
            return {str(target.id): overwrite._values for target, overwrite in overwrites.items()}
        except Exception:
            return {}

    async def _save_channels(self):
        for category in self.guild.categories:
            try:
                self.data["categories"].append({
                    "name": category.name,
                    "position": category.position,
                    "category": None if category.category is None else str(category.category.id),
                    "id": str(category.id),
                    "overwrites": self._overwrites_to_json(category.overwrites)
                })
            except Exception:
                pass

            await asyncio.sleep(0)

        for tchannel in self.guild.text_channels:
            try:
                messages = []

                for message in await tchannel.history(limit=200).flatten():
                    messages.append({
                        "author_id": message.author.id,
                        "username": message.author.name,
                        "content": message.content,
                        "created_at": message.created_at.timestamp(),
                        "type": "text"
                    })

                    if (len(message.embeds) > 0):
                        for embed in message.embeds:
                            fields = []
                            if (len(embed.fields) > 0):
                                for field in embed.fields:
                                    fields.append({
                                        "name": field.name,
                                        "value": field.value,
                                        "inline": field.inline
                                    })

                            embed_data = {
                                "author_id": message.author.id,
                                "username": message.author.name,
                                "colour": embed.colour.value if embed.colour != discord.Embed.Empty else None,
                                "title": embed.title if embed.title != discord.Embed.Empty else None,
                                "description": embed.description if embed.description != discord.Embed.Empty else None,
                                "image": embed.image.url if embed.image.url != discord.Embed.Empty else None,
                                "thumbnail": embed.thumbnail.url if embed.thumbnail.url != discord.Embed.Empty else None,
                                "created_at": message.created_at.timestamp(),
                                "fields": fields,
                                "footer": None,
                                "type": "embed",
                                "author": {
                                    "name": embed.author.name if embed.author.name != discord.Embed.Empty else None,
                                    "url": embed.author.url if embed.author.url != discord.Embed.Empty else None,
                                    "icon_url": embed.author.icon_url if embed.author.icon_url != discord.Embed.Empty else None,
                                }
                            }

                            if (embed.footer != discord.Embed.Empty):
                                embed_data["footer"] = {
                                    "text": embed.footer.text if embed.footer.text != discord.Embed.Empty else None,
                                    "icon_url": embed.footer.icon_url if embed.footer.icon_url != discord.Embed.Empty else None,
                                }
                            messages.append(embed_data)

                self.data["text_channels"].append({
                    "name": tchannel.name,
                    "position": tchannel.position,
                    "category": None if tchannel.category is None else str(tchannel.category.id),
                    "id": str(tchannel.id),
                    "overwrites": self._overwrites_to_json(tchannel.overwrites),
                    "topic": tchannel.topic,
                    "slowmode_delay": tchannel.slowmode_delay,
                    "nsfw": tchannel.is_nsfw(),
                    "messages": messages,
                    "webhooks": [{
                        "channel": str(webhook.channel.id),
                        "name": webhook.name,
                        "avatar": str(webhook.avatar_url),
                        "url": webhook.url

                    } for webhook in await tchannel.webhooks()]
                })
            except Exception:
                pass

            await asyncio.sleep(0)

        for vchannel in self.guild.voice_channels:
            try:
                self.data["voice_channels"].append({
                    "name": vchannel.name,
                    "position": vchannel.position,
                    "category": None if vchannel.category is None else str(vchannel.category.id),
                    "id": str(vchannel.id),
                    "overwrites": self._overwrites_to_json(vchannel.overwrites),
                    "bitrate": vchannel.bitrate,
                    "user_limit": vchannel.user_limit,
                })
            except Exception:
                pass

            await asyncio.sleep(0)

    async def _save_roles(self):
        for role in self.guild.roles:
            try:
                if role.managed:
                    continue

                self.data["roles"].append({
                    "id": str(role.id),
                    "default": role.is_default(),
                    "name": role.name,
                    "permissions": role.permissions.value,
                    "color": role.color.value,
                    "hoist": role.hoist,
                    "position": role.position,
                    "mentionable": role.mentionable
                })
            except Exception:
                pass

            await asyncio.sleep(0)

    async def _save_members(self):
        if self.guild.large:
            await self.bot.request_offline_members(self.guild)

        async for member in self.guild.fetch_members(limit=1000):
            try:
                self.data["members"].append({
                    "id": str(member.id),
                    "name": member.name,
                    "discriminator": member.discriminator,
                    "nick": member.nick,
                    "roles": [str(role.id) for role in member.roles[1:] if not role.managed]
                })
            except Exception:
                pass

            await asyncio.sleep(0)

    async def _save_bans(self):
        for reason, user in await self.guild.bans():
            try:
                self.data["bans"].append({
                    "user": str(user.id),
                    "reason": reason
                })
            except Exception:
                pass

            await asyncio.sleep(0)

    async def create(self):
        self.data = {
            "id": str(self.guild.id),
            "name": self.guild.name,
            "icon_url": str(self.guild.icon_url),
            "owner": str(self.guild.owner_id),
            "member_count": self.guild.member_count,
            "region": str(self.guild.region),
            "system_channel": str(self.guild.system_channel),
            "afk_timeout": self.guild.afk_timeout,
            "afk_channel": None if self.guild.afk_channel is None else str(self.guild.afk_channel.id),
            "mfa_level": self.guild.mfa_level,
            "verification_level": str(self.guild.verification_level),
            "explicit_content_filter": str(self.guild.explicit_content_filter),
            "large": self.guild.large,
            "text_channels": [],
            "voice_channels": [],
            "categories": [],
            "roles": [],
            "members": [],
            "bans": [],
        }

        execution_order = [self._save_roles, self._save_channels,
                           self._save_members, self._save_bans]

        for method in execution_order:
            try:
                await method()
            except Exception:
                traceback.print_exc()

        with open(Path("data/backup.json"), "w") as fp:
            json.dump(self.data, fp)

        if (self.response_channel != None):
            await self.response_channel.send(
                "✅ **Backup of this server has been created.** ✅")

    def __dict__(self):
        return self.data
