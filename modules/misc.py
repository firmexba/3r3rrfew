import traceback
from itertools import cycle
from random import shuffle
from os import getpid
import platform
import asyncio

import disnake
import psutil
import humanize
from disnake.ext import commands
from aiohttp import ClientSession

from utils.client import BotCore
from utils.db import DBModel, db_models
from utils.music.checks import check_requester_channel
from utils.music.converters import time_format, URL_REG
from utils.others import select_bot_pool


class Misc(commands.Cog):

    def __init__(self, bot: BotCore):
        self.bot = bot
        self.activities = None
        self.task = self.bot.loop.create_task(self.presences())
        self.extra_user_bots = []
        self.extra_user_bots_ids = [int(i) for i in bot.config['ADDITIONAL_BOT_IDS'].split() if i.isdigit()]

    desc_prefix = "🔰 [Drugi] 🔰 | "


    def placeholders(self, text: str):

        if not text:
            return ""

        return text \
            .replace("{users}", f'{len([m for m in self.bot.users if not m.bot]):,}'.replace(",", ".")) \
            .replace("{playing}", f'{len(self.bot.music.players):,}'.replace(",", ".")) \
            .replace("{guilds}", f'{len(self.bot.guilds):,}'.replace(",", ".")) \
            .replace("{uptime}", time_format((disnake.utils.utcnow() - self.bot.uptime).total_seconds() * 1000,
                                             use_names=True))


    async def presences(self):

        if not self.activities:

            activities = []

            for i in self.bot.config["LISTENING_PRESENCES"].split("||"):
                if i:
                    activities.append({"name":i, "type": "listening"})

            for i in self.bot.config["WATCHING_PRESENCES"].split("||"):
                if i:
                    activities.append({"name": i, "type": "watching"})

            for i in self.bot.config["PLAYING_PRESENCES"].split("||"):
                if i:
                    activities.append({"name": i, "type": "playing"})

            for i in self.bot.config["STREAMING_PRESENCES"].split("|||"):
                if i:
                    try:
                        name, url = i.split("||")
                        activities.append({"name": name, "url": url.strip(" "), "type": "streaming"})
                    except Exception:
                        traceback.print_exc()

            shuffle(activities)

            self.activities = cycle(activities)

        while True:

            await self.bot.wait_until_ready()

            activity_data = next(self.activities)

            if activity_data["type"] == "listening":
                activity = disnake.Activity(
                    type=disnake.ActivityType.listening,
                    name=self.placeholders(activity_data["name"])
                )

            elif activity_data["type"] == "watching":
                activity = disnake.Activity(
                    type=disnake.ActivityType.watching,
                    name=self.placeholders(activity_data["name"])
                )

            elif activity_data["type"] == "streaming":
                activity = disnake.Activity(
                    type=disnake.ActivityType.streaming,
                    name=self.placeholders(activity_data["name"]),
                    url=activity_data["url"]
                )

            else:
                activity = disnake.Game(name=self.placeholders(activity_data["name"]))

            await self.bot.change_presence(activity=activity)

            await asyncio.sleep(self.bot.config["PRESENCE_INTERVAL"])


    @commands.Cog.listener("on_guild_join")
    async def guild_add(self, guild: disnake.Guild):

        if not guild.system_channel or not guild.system_channel.permissions_for(guild.me).send_messages:
            return

        if str(self.bot.user.id) in self.bot.config["INTERACTION_BOTS_CONTROLLER"]:
            await guild.leave()

        if self.bot.config["GLOBAL_PREFIX"]:
            components = [disnake.ui.Button(custom_id="bot_invite", label="Trebate još muzičkih botova? Kliknite ovdje.")] if [b for b in self.bot.pool.bots if b.appinfo and b.appinfo.bot_public] else None
        else:
            components = []

        embed = disnake.Embed(
            description="",
            color=self.bot.get_color(guild.me)
        )

        if not self.bot.command_sync_flags.sync_commands and self.bot.config["INTERACTION_BOTS"]:

            interaction_invites = []

            for b in self.bot.pool.bots:

                if str(b.user.id) not in self.bot.config["INTERACTION_BOTS"]:
                    continue

                interaction_invites.append(f"[`{disnake.utils.escape_markdown(str(b.user.name))}`]({disnake.utils.oauth_url(b.user.id, scopes=['applications.commands'])}) ")

            if interaction_invites:
                embed.description += f"Zdravo! Da vidite sve moje komande ukucajte kosu (**/**) i provjeri " \
                                     f"naredbe sljedećih aplikacija u nastavku:\n" \
                                     f"{' **|** '.join(interaction_invites)}\n\n" \
                                     f"Ako se gornje naredbe aplikacije ne prikazuju prilikom kucanja " \
                                     f"van (**/**) moraćete da kliknete na ime iznad da integrišete komande iz " \
                                     f"bar na vašem serveru.\n\n"

            else:
                embed.description += "Zdravo! Da vidite sve moje komande koristite kosu crtu (**/**)\n\n"

        if cmd:=self.bot.get_command("setup"):
            embed.description += f"Ako želite, koristite naredbu **/{cmd.name}** da kreirate namenski kanal za postavljanje pitanja " \
                                 "pesme bez komandi i ostavite muzički plejer fiksiran na namenskom kanalu.\n\n"

        if self.bot.config["SUPPORT_SERVER"]:
            embed.description += f"Ako imate bilo kakvih pitanja ili želite biti u toku sa najnovijim vijestima, možete unijeti moj [`server za podršku`]({self.bot.config['SUPPORT_SERVER']})\n\n"

        try:
            await guild.system_channel.send(embed=embed, components=components)
        except:
            traceback.print_exc()

        await self.bot.update_appinfo()


    about_cd = commands.CooldownMapping.from_cooldown(1, 5, commands.BucketType.member)

    @commands.command(name="about", aliases=["sobre", "info", "botinfo"], description="Pogledaj informacije o meni.",
                      cooldown=about_cd)
    async def about_legacy(self, ctx):
        await self.about.callback(self=self, inter=ctx)


    @commands.slash_command(
        description=f"{desc_prefix}Pogledaj informacije o meni.", cooldown=about_cd
    )
    async def about(
            self,
            inter: disnake.AppCmdInter
    ):

        await inter.response.defer(ephemeral=True)

        inter, bot = await select_bot_pool(inter, first=self.bot.config["GLOBAL_PREFIX"])

        if not bot:
            return

        ram_usage = humanize.naturalsize(psutil.Process(getpid()).memory_info().rss)

        guild = bot.get_guild(inter.guild_id) or inter.guild

        embed = disnake.Embed(
            description=f"**O meni:**\n\n",
            color=bot.get_color(inter.guild.me if inter.guild else guild.me)
        )

        active_players_other_bots = 0

        if self.bot.config["GLOBAL_PREFIX"]:

            for b in bot.pool.bots:
                active_players_other_bots += len(b.music.players)

            if active_players_other_bots:
                embed.description += f"> **Aktivni botovi (svi botovi):** `{active_players_other_bots}`\n"

        else:

            if bot.music.players:
                embed.description += f"> **Aktivni botovi (trenutni bot):** `{len(bot.music.players)}`\n"

            for b in self.bot.pool.bots:
                if b.user.id == bot.user.id:
                    continue
                active_players_other_bots += len(b.music.players)

            if active_players_other_bots:
                embed.description += f"> **Aktivni botovi (ostali botovi):** `{active_players_other_bots}`\n"

        if bot.pool.commit:
            embed.description += f"> **Trenutno:** [`{bot.pool.commit[:7]}`]({bot.pool.remote_git_url}/commit/{bot.pool.commit})\n"

        embed.description += f"> **Python:** `{platform.python_version()}`\n" \
                             f"> **Disnake:** `{disnake.__version__}`\n" \
                             f"> **Latencija:** `{round(bot.latency * 1000)}ms`\n" \
                             f"> **RAM:** `{ram_usage}`\n" \
                             f"> **Uptime:** <t:{int(bot.uptime.timestamp())}:R>\n"

        if bot.config["GLOBAL_PREFIX"]:
            guild_data = await bot.get_global_data(inter.guild_id, db_name=DBModel.guilds)
        else:
            embed.set_thumbnail(url=bot.user.display_avatar.replace(size=256, static_format="png").url)
            guild_data = await bot.get_data(inter.guild_id, db_name=DBModel.guilds)

        prefix = guild_data["prefix"] or bot.default_prefix

        if bot.default_prefix and not bot.config["INTERACTION_COMMAND_ONLY"]:
            embed.description += f"> **Prefix:** `{disnake.utils.escape_markdown(prefix, as_needed=True)}`\n"

        links = "[`[Hvala na koristenju]`](#)"

        if bot.config["SUPPORT_SERVER"]:
            links += f" **|** [`[podrška]`]({bot.config['SUPPORT_SERVER']})"

        embed.description += f">  {links}\n"

        try:
            avatar = bot.owner.avatar.with_static_format("png").url
        except AttributeError:
            avatar = bot.owner.default_avatar.with_static_format("png").url

        embed.set_footer(
            icon_url=avatar,
            text=f"Koji: {bot.owner}"
        )

        components = [disnake.ui.Button(custom_id="bot_invite", label="dodaj me na svoj server")] if [b for b in bot.pool.bots if b.appinfo and b.appinfo.bot_public] else None

        try:
            await inter.edit_original_message(embed=embed, components=components)
        except (AttributeError, disnake.InteractionNotEditable):
            try:
                await inter.response.edit_message(embed=embed, components=components)
            except:
                await inter.send(embed=embed, ephemeral=True, components=components)


    @commands.Cog.listener("on_button_click")
    async def invite_button(self, inter: disnake.MessageInteraction, is_command=False):

        if not is_command and inter.data.custom_id != "bot_invite":
            return

        bots_invites = []
        bots_in_guild = []

        guild = inter.guild

        if not guild:
            for bot in self.bot.pool.bots:
                if (guild:=bot.get_guild(inter.guild_id)):
                    break

        for bot in sorted(self.bot.pool.bots, key=lambda b: len(b.guilds)):

            if bot.appinfo and not bot.appinfo.bot_public or str(bot.user.id) in bot.config['INTERACTION_BOTS_CONTROLLER']:
                continue

            invite = f"[`{disnake.utils.escape_markdown(str(bot.user.name))}`]({disnake.utils.oauth_url(bot.user.id, permissions=disnake.Permissions(bot.config['INVITE_PERMISSIONS']), scopes=('bot', 'applications.commands'))})"

            if not str(bot.user.id) not in self.bot.config["INTERACTION_BOTS_CONTROLLER"] and bot.appinfo.flags.gateway_message_content_limited:
                invite += f" ({len(bot.guilds)}/100)"
            else:
                invite += f" ({len(bot.guilds)})"

            if guild and bot.user in guild.members:
                bots_in_guild.append(invite)
            else:
                bots_invites.append(invite)

        txt = ""

        if bots_invites:
            txt += "**Dostupni muzički botovi:**\n"
            for i in disnake.utils.as_chunks(bots_invites, 2):
                txt += " | ".join(i) + "\n"
            txt += "\n"

        if bots_in_guild:
            txt += "**Muzički botovi koji su već na trenutnom serveru:**\n"
            for i in disnake.utils.as_chunks(bots_in_guild, 2):
                txt += " | ".join(i) + "\n"

        if not txt:
            await inter.send(
                embed=disnake.Embed(
                    colour=self.bot.get_color(
                        inter.guild.me if inter.guild else guild.me if guild else None
                    ),
                    title="**Nema dostupnih javnih botova...**",
                ), ephemeral=True
            )
            return

        interaction_bots = ""

        for bot_id in inter.bot.config["INTERACTION_BOTS"].split(" "):

            if not bot_id.isdigit():
                continue

            if bot_id in txt and len(bots_invites + bots_in_guild) < 2:
                continue

            try:
                if int(bot_id) == inter.bot.user.id:
                    userbot = inter.bot.user
                else:
                    userbot = await inter.bot.get_or_fetch_user(int(bot_id))
                    if not userbot:
                        continue

                interaction_bots += f"[`{disnake.utils.escape_markdown(str(userbot.name))}`]({disnake.utils.oauth_url(userbot.id, scopes=['applications.commands'])}) "
            except Exception:
                traceback.print_exc()

        if interaction_bots:
            txt = f"**Registrujte komande kose crte na serveru:**\n{interaction_bots}\n\n" + txt

        await inter.send(
            embed=disnake.Embed(
                colour=self.bot.get_color(
                    inter.guild.me if inter.guild else guild.me if guild else None
                ),
                description=txt
            ), ephemeral=True
        )


    @commands.command(name="invite", aliases=["convidar"], description="Prikaži moj link za pozivnicu da me dodate na svoj server.")
    async def invite_legacy(self, ctx):
        await self.invite.callback(self=self, inter=ctx)


    @commands.slash_command(
        description=f"{desc_prefix}Prikaži moj link za pozivnicu da me dodate na svoj server."
    )
    async def invite(self, inter: disnake.AppCmdInter):

        await inter.response.defer(ephemeral=True)

        await self.invite_button(inter, is_command=True)

    @commands.user_command(name="avatar")
    async def avatar(self, inter: disnake.UserCommandInteraction):

        embeds = []

        assets = {}

        if self.bot.intents.members:
            user = (await self.bot.fetch_user(inter.target.id) if not inter.target.bot else self.bot.get_user(inter.target.id))
        else:
            user = inter.target

        if inter.target.guild_avatar:
            assets["Avatar (Server)"] = inter.target.guild_avatar.with_static_format("png")
        assets["Avatar (User)"] = user.display_avatar.with_static_format("png")
        if user.banner:
            assets["Banner"] = user.banner.with_static_format("png")

        for name, asset in assets.items():
            embed = disnake.Embed(description=f"{inter.target.mention} **[{name}]({asset.with_size(2048).url})**",
                                  color=self.bot.get_color(inter.guild.me if inter.guild else None))
            embed.set_image(asset.with_size(256).url)
            embeds.append(embed)

        await inter.send(embeds=embeds, ephemeral=True)

    async def cog_check(self, ctx):
        return await check_requester_channel(ctx)

    def cog_unload(self):

        try:
            self.task.cancel()
        except:
            pass


class GuildLog(commands.Cog):

    def __init__(self, bot: BotCore):
        self.bot = bot
        self.hook_url: str = ""

        if bot.config["BOT_ADD_REMOVE_LOG"]:

            if URL_REG.match(bot.config["BOT_ADD_REMOVE_LOG"]):
                self.hook_url = bot.config["BOT_ADD_REMOVE_LOG"]
            else:
                print("Nevažeći webhook URL (za isporuku dnevnika prilikom dodavanja/uklanjanja bota).")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: disnake.Guild):

        print(f"uklonjen sa servera: {guild.name} - [{guild.id}]")

        try:
            await self.bot.music.players[guild.id].destroy()
        except:
            pass

        if not self.hook_url:
            return

        embed = disnake.Embed(
            description=f"**Uklonjen sam sa servera:**\n"
                        f"```{guild.name}```\n"
                        f"**ID:** `{guild.id}`",
            color=disnake.Colour.red()
        )

        try:
            guild_data = await self.bot.get_data(guild.id, db_name=DBModel.guilds)
            guild_data["player_Controller"] = db_models[DBModel.guilds]["player_controller"]
            await self.bot.update_data(guild.id, guild_data, db_name=DBModel.guilds)
        except:
            traceback.print_exc()

        try:
            embed.set_thumbnail(url=guild.icon.replace(static_format="png").url)
        except AttributeError:
            pass

        try:
            owner_mention = self.bot.owner.mention
        except AttributeError:
            owner_mention = ""

        try:
            await self.send_hook(owner_mention, embed=embed)
        except:
            traceback.print_exc()

        await self.bot.update_appinfo()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: disnake.Guild):

        print(f"novi server: {guild.name} - [{guild.id}]")

        try:
            guild_data = await self.bot.get_data(guild.id, db_name=DBModel.guilds)
            guild_data["player_Controller"] = db_models[DBModel.guilds]["player_controller"]
            await self.bot.update_data(guild.id, guild_data, db_name=DBModel.guilds)
        except:
            traceback.print_exc()

        if not self.hook_url:
            return

        created_at = int(guild.created_at.timestamp())

        embed =disnake.Embed(
            description="__**Dodao me na novi server:**__\n"
                        f"```{guild.name}```\n"
                        f"**ID:** `{guild.id}`\n"
		                f"**Vlasnik:** `{guild.owner}`\n"
                        f"**Kreirano u:** <t:{created_at}:f> - <t:{created_at}:R>\n"
		                f"**Nivo verifikacije:** `{guild.verification_level or 'nenhuma'}`\n"
		                f"**Clanovi:** `{len([m for m in guild.members if not m.bot])}`\n"
		                f"**Bots:** `{len([m for m in guild.members if m.bot])}`\n",
            color=disnake.Colour.green()
        )

        try:
            embed.set_thumbnail(url=guild.icon.replace(static_format="png").url)
        except AttributeError:
            pass

        try:
            owner_mention = self.bot.owner.mention
        except AttributeError:
            owner_mention = ""

        await self.send_hook(owner_mention, embed=embed)

    async def send_hook(self, content="", *, embed: disnake.Embed=None):

        async with ClientSession() as session:
            webhook = disnake.Webhook.from_url(self.hook_url, session=session)
            await webhook.send(
                content=content,
                username=self.bot.user.name,
                avatar_url=self.bot.user.display_avatar.replace(size=256, static_format="png").url,
                embed=embed
            )


def setup(bot: BotCore):
    bot.add_cog(Misc(bot))
    bot.add_cog(GuildLog(bot))
