import discord
import traceback
import asyncio
import json
import time
import types
import base64
import requests
import datetime
from pathlib import Path


class BackupRestorer:
    def __init__(self, bot):
        data_folder = Path("data")
        backup_file = data_folder / "backup.json"

        with open(backup_file) as backup:
            self.data = json.load(backup)
        self.bot = bot
        self.id_translator = {}
        self.options = {
            "roles": True,
            "channels": True,
            "settings": True,
            "bans": True,
            "members": True,
            "roles": True,
            "messages": True
        }
        self.semaphore = asyncio.Semaphore(2)
        self.message_holder = []

    async def _overwrites_from_json(self, json):
        overwrites = {}
        for union_id, overwrite in json.items():
            try:
                union = await self.guild.fetch_member(int(union_id))
            except discord.NotFound:
                roles = list(
                    filter(lambda r: r.id == self.id_translator.get(union_id), self.guild.roles))
                if len(roles) == 0:
                    continue

                union = roles[0]

            overwrites[union] = discord.PermissionOverwrite(**overwrite)

        return overwrites

    def _translate_mentions(self, text):
        if not text:
            return text

        formats = ["<#%s>", "<@&%s>"]
        for key, value in self.id_translator.items():
            for _format in formats:
                text = text.replace(_format % str(key), _format % str(value))

        return text

    async def run_tasks(self, coros, wait=True):
        async def executor(_coro):
            try:
                await _coro

            except Exception:
                pass

            finally:
                self.semaphore.release()

        tasks = []
        for coro in coros:
            await self.semaphore.acquire()
            tasks.append(self.bot.loop.create_task(executor(coro)))

        if wait and tasks:
            await asyncio.wait(tasks)

    async def _prepare_guild(self):
        print(f"Deleting roles on {self.guild.id}")
        if self.options.get("roles"):
            existing_roles = list(filter(
                lambda r: not r.managed and self.guild.me.top_role.position > r.position,
                self.guild.roles
            ))
            difference = len(self.data["roles"]) - len(existing_roles)
            for role in existing_roles:
                if difference < 0:
                    try:
                        await role.delete(reason=self.reason)
                    except Exception:
                        pass

                    else:
                        difference += 1

                else:
                    break

        if self.options.get("channels"):
            print(f"Deleting channels on {self.guild.id}")
            for channel in self.guild.channels:
                try:
                    await channel.delete(reason=self.reason)
                except Exception:
                    pass

    async def _load_settings(self):
        print(f"Loading settings on {self.guild.id}")

        # grab server icon
        server_icon = requests.get(self.data["icon_url"]).content

        await self.guild.edit(
            name=self.data["name"],
            afk_channel=self.guild.get_channel(
                self.id_translator.get(self.data["afk_channel"])),
            afk_timeout=self.data["afk_timeout"],

            system_channel=self.guild.get_channel(
                self.id_translator.get(self.data["system_channel"])),
            reason=self.reason,
            icon=server_icon)

    async def _load_roles(self):
        print(f"Loading roles on {self.guild.id}")
        existing_roles = list(reversed(list(filter(
            lambda r: not r.managed and not r.is_default()
            and self.guild.me.top_role.position > r.position,
            self.guild.roles
        ))))
        for role in reversed(self.data["roles"]):
            try:
                if role["default"]:
                    await self.guild.default_role.edit(
                        permissions=discord.Permissions(role["permissions"])
                    )
                    new_role = self.guild.default_role
                else:
                    kwargs = {
                        "name": role["name"],
                        "hoist": role["hoist"],
                        "mentionable": role["mentionable"],
                        "color": discord.Color(role["color"]),
                        "permissions": discord.Permissions.none(),
                        "reason": self.reason
                    }

                    if len(existing_roles) == 0:
                        try:
                            new_role = await asyncio.wait_for(self.guild.create_role(**kwargs), 10)
                        except asyncio.TimeoutError:
                            # Probably hit the 24h rate limit. Just skip roles
                            break
                    else:
                        new_role = existing_roles.pop(0)
                        await new_role.edit(**kwargs)

                self.id_translator[role["id"]] = new_role.id
            except Exception:
                pass

    async def _load_role_permissions(self):
        tasks = []
        for role in self.data["roles"]:
            to_edit = self.guild.get_role(self.id_translator.get(role["id"]))
            if to_edit:
                tasks.append(to_edit.edit(
                    permissions=discord.Permissions(role["permissions"])))

        await self.run_tasks(tasks)

    async def _load_categories(self):
        print(f"Loading categories on {self.guild.id}")
        for category in self.data["categories"]:
            try:
                created = await self.guild.create_category_channel(
                    name=category["name"],
                    overwrites=await self._overwrites_from_json(category["overwrites"]),
                    reason=self.reason
                )
                self.id_translator[category["id"]] = created.id
            except Exception:
                pass

    async def _load_text_channels(self):
        print(f"Loading text channels on {self.guild.id}")
        for tchannel in self.data["text_channels"]:
            try:
                if tchannel["category"] != None:
                    created = await self.guild.create_text_channel(
                        name=tchannel["name"],
                        overwrites=await self._overwrites_from_json(tchannel["overwrites"]),
                        category=discord.Object(
                            self.id_translator.get(tchannel["category"])),
                        reason=self.reason
                    )
                else:
                    created = await self.guild.create_text_channel(
                        name=tchannel["name"],
                        overwrites=await self._overwrites_from_json(tchannel["overwrites"]),
                        reason=self.reason
                    )
                self.id_translator[tchannel["id"]] = created.id
                await created.edit(
                    topic=self._translate_mentions(tchannel["topic"]),
                    nsfw=tchannel["nsfw"],
                )

                await asyncio.sleep(1)
                # store to later post
                self.message_holder.append(
                    [created, reversed(tchannel["messages"])])
                # print(f"Sending messages to text channel {created.id}")
                # for message in reversed(tchannel["messages"]):
                #     if (message["author_id"] == self.bot.user.id):
                #         continue
                #     embed=discord.Embed()
                #     embed.timestamp=datetime.datetime.fromtimestamp(
                #         message["created_at"])
                #     embed.color=0x0000ff
                #     embed.add_field(
                #         name=message["username"], value=message["content"], inline=False)
                #     await created.send(embed=embed)
            except Exception:
                pass

    async def _load_voice_channels(self):
        print(f"Loading voice channels on {self.guild.id}")
        for vchannel in self.data["voice_channels"]:
            try:
                created = await self.guild.create_voice_channel(
                    name=vchannel["name"],
                    overwrites=await self._overwrites_from_json(vchannel["overwrites"]),
                    category=discord.Object(
                        self.id_translator.get(vchannel["category"])),
                    reason=self.reason
                )
                await created.edit(
                    bitrate=vchannel["bitrate"],
                    user_limit=vchannel["user_limit"]
                )
                self.id_translator[vchannel["id"]] = created.id
            except Exception:
                pass

    async def _load_channels(self):
        await self._load_categories()
        await self._load_text_channels()
        await self._load_voice_channels()

    async def _load_bans(self):
        print(f"Loading bans on {self.guild.id}")

        tasks = [
            await self.guild.ban(user=discord.Object(
                int(ban["user"])), reason=ban["reason"])
            for ban in self.data["bans"]
        ]
        await self.run_tasks(tasks)

    async def _load_members(self):
        print(f"Loading members on {self.guild.id}")

        async def edit_member(member, member_data):
            roles = [
                discord.Object(self.id_translator.get(role))
                for role in member_data["roles"]
                if role in self.id_translator.keys()
            ]

            if self.guild.me.top_role.position > member.top_role.position:
                try:
                    if member != self.guild.owner:
                        await member.edit(
                            nick=member_data.get("nick"),
                            roles=[r for r in member.roles if r.managed] + roles,
                            reason=self.reason
                        )

                except discord.Forbidden:
                    try:
                        await member.edit(
                            roles=[r for r in member.roles if r.managed] + roles,
                            reason=self.reason
                        )

                    except discord.Forbidden:
                        await member.add_roles(*roles)

            else:
                await member.add_roles(*roles)

        tasks = []
        default_data = {
            "nick": None,
            "roles": []
        }
        async for member in self.guild.fetch_members(limit=self.guild.member_count):
            fits = list(filter(lambda m: m["id"] == str(
                member.id), self.data["members"]))
            if fits:
                tasks.append(edit_member(member, fits[0]))

            else:
                tasks.append(edit_member(member, default_data))

        await self.run_tasks(tasks)

    async def _load_messages(self):
        for m in self.message_holder:
            channel = m[0]
            messages = m[1]

            print(f"Restoring messages on channel: {channel.id}. Be patient.")

            for message in messages:
                if (message["author_id"] == self.bot.user.id):
                    continue

                if message["type"] == "text":
                    if ((message["content"]).strip() == "") or (len(message["content"]) > 1024):
                        continue

                    embed = discord.Embed()
                    embed.timestamp = datetime.datetime.fromtimestamp(
                        message["created_at"])
                    embed.color = 0x0000ff
                    embed.add_field(
                        name=message["username"], value=message["content"], inline=False)
                    await channel.send(embed=embed)

                if message["type"] == "attachment":
                    await channel.send(message["url"])

                if message["type"] == "embed":
                    embed = discord.Embed()

                    if message["colour"] != None:
                        embed.color = message["colour"]

                    if message["title"] != None:
                        embed.title = message["title"]

                    if message["description"] != None:
                        embed.description = message["description"]

                    if message["image"] != None:
                        embed.set_image(url=message["image"])

                    if message["thumbnail"] != None:
                        embed.set_thumbnail(url=message["thumbnail"])

                    if message["author"] != None and message["author"]["name"] != None:

                        embed.set_author(
                            name=message["author"]["name"],
                            url=message["author"]["url"] if message["author"]["url"] != None else discord.Embed.Empty,
                            icon_url=message["author"]["icon_url"] if message["author"]["icon_url"] != None else discord.Embed.Empty
                        )

                    if message["footer"] != None and message["footer"]["text"] != None:
                        embed.set_footer(
                            text=message["footer"]["text"],
                            icon_url=message["footer"]["icon_url"] if message["footer"]["icon_url"] != None else discord.Embed.Empty,
                        )

                    for field in message["fields"]:
                        embed.add_field(
                            name=field["name"], value=field["value"], inline=field["inline"])

                    await channel.send(embed=embed)

    async def restore(self, guild, loader: discord.User):
        self.guild = guild
        self.loader = loader
        self.reason = "Backup restore"

        print(f"Loading backup on {self.guild.id}")

        try:
            await self._prepare_guild()
        except Exception:
            traceback.print_exc()

        steps = [
            ("roles", self._load_roles),
            ("channels", self._load_channels),
            ("settings", self._load_settings),
            ("bans", self._load_bans),
            ("members", self._load_members),
            ("roles", self._load_role_permissions),
            ("messages", self._load_messages),

        ]
        for option, coro in steps:
            if self.options.get(option):
                try:
                    await coro()
                except Exception:
                    traceback.print_exc()

        print("------------------------------------------------------------")

        print(
            f"Congratulations!. Backup restore on server {self.guild.id} has been completed!.")
