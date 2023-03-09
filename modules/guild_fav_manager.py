from __future__ import annotations
from io import BytesIO
import json
import disnake
from disnake.ext import commands
from typing import TYPE_CHECKING, Union, Optional

from utils.music.converters import URL_REG
from utils.music.errors import GenericError
from utils.music.models import LavalinkPlayer
from utils.others import send_idle_embed, select_bot_pool, CustomContext
from utils.db import DBModel

if TYPE_CHECKING:
    from utils.client import BotCore


class GuildFavModal(disnake.ui.Modal):
    def __init__(self, bot: BotCore, name: Optional[str], description: Optional[str], url: Optional[str]):

        self.bot = bot
        self.name = name

        super().__init__(
            title="Dodaj/uredi plejlistu/favorite",
            custom_id="guild_fav_edit",
            timeout=180,
            components=[
                disnake.ui.TextInput(
                    label="Naziv favorita/plejliste:",
                    custom_id="guild_fav_name",
                    min_length=2,
                    max_length=25,
                    value=name or None
                ),
                disnake.ui.TextInput(
                    label="Opis:",
                    custom_id="guild_fav_description",
                    max_length=50,
                    value=description or None
                ),
                disnake.ui.TextInput(
                    label="Link/Url:",
                    custom_id="guild_fav_url",
                    min_length=10,
                    max_length=200,
                    value=url or None
                ),
            ]
        )

    async def callback(self, inter: disnake.ModalInteraction):

        url = inter.text_values["guild_fav_url"]

        try:
            valid_url = URL_REG.findall(url)[0]
        except IndexError:
            await inter.send(
                embed=disnake.Embed(
                    description=f"**Nije pronađena važeća veza:** {url}",
                    color=disnake.Color.red()
                ), ephemeral=True
            )
            return

        await inter.response.defer(ephemeral=True)

        guild_data = await self.bot.get_data(inter.guild_id, db_name=DBModel.guilds)

        if not guild_data["player_controller"]["channel"] or not self.bot.get_channel(int(guild_data["player_controller"]["channel"])):
            raise GenericError("**Nema konfigurisanog bota na serveru! Koristite naredbu /setup**")

        name = inter.text_values["guild_fav_name"]
        description = inter.text_values["guild_fav_description"]

        if not guild_data["player_controller"]["channel"] or not self.bot.get_channel(
                int(guild_data["player_controller"]["channel"])):
            raise GenericError("**Nema konfigurisanog bota na serveru! Koristite naredbu /setup**")

        try:
            if name != self.name:
                del guild_data["player_controller"]["fav_links"][self.name]
        except KeyError:
            pass

        guild_data["player_controller"]["fav_links"][name] = {'url': valid_url, "description": description}

        await self.bot.update_data(inter.guild_id, guild_data, db_name=DBModel.guilds)

        guild = inter.guild or self.bot.get_guild(inter.guild_id)

        await inter.edit_original_message(embed=disnake.Embed(description="**Link je uspješno dodat/ažuriran na pinovima igrača!\n"
                         "Članovi ga mogu koristiti direktno u player-kontroleru kada nije u upotrebi..**",
                                                              color=self.bot.get_color(guild.me)), view=None)

        await self.bot.get_cog("PinManager").process_idle_embed(guild)

class GuildFavView(disnake.ui.View):

    def __init__(self, bot: BotCore, ctx: Union[disnake.AppCmdInter, CustomContext], data: dict):
        super().__init__(timeout=60)
        self.bot = bot
        self.ctx = ctx
        self.current = None
        self.data = data
        self.message = None

        if data["player_controller"]["fav_links"]:

            fav_select = disnake.ui.Select(options=[
                disnake.SelectOption(label=k, description=v.get("description")) for k, v in data["player_controller"]["fav_links"].items()
            ], min_values=1, max_values=1)
            fav_select.callback = self.select_callback
            self.add_item(fav_select)

        favadd_button = disnake.ui.Button(label="Dodati", emoji="⭐")
        favadd_button.callback = self.favadd_callback
        self.add_item(favadd_button)

        if data["player_controller"]["fav_links"]:

            edit_button = disnake.ui.Button(label="Uredi", emoji="✍️")
            edit_button.callback = self.edit_callback
            self.add_item(edit_button)

            remove_button = disnake.ui.Button(label="Izbrisi", emoji="♻️")
            remove_button.callback = self.remove_callback
            self.add_item(remove_button)

        cancel_button = disnake.ui.Button(label="Otkaži", emoji="❌")
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)

    async def on_timeout(self):

        if isinstance(self.ctx, CustomContext):
            try:
                await self.message.edit(
                    embed=disnake.Embed(description="**Vrijeme je isteklo...**", color=self.bot.get_color()), view=None
                )
            except:
                pass

        else:
            await self.ctx.edit_original_message(
                embed=disnake.Embed(description="**Vrijeme je isteklo...**", color=self.bot.get_color()), view=None
            )
        self.stop()

    async def favadd_callback(self, inter: disnake.MessageInteraction):
        await inter.response.send_modal(GuildFavModal(bot=self.bot, name=None, url=None, description=None))
        await inter.delete_original_message()
        self.stop()

    async def edit_callback(self, inter: disnake.MessageInteraction):

        if not self.current:
            await inter.send("Morate odabrati stavku!", ephemeral=True)
            return

        try:
            await inter.response.send_modal(
                GuildFavModal(
                    bot=self.bot, name=self.current,
                    url=self.data["player_controller"]["fav_links"][self.current]["url"],
                    description=self.data["player_controller"]["fav_links"][self.current]["description"]
                )
            )
        except KeyError:
            await inter.send(f"**Nema favorita sa imenom:** {self.current}", ephemeral=True)
            return

        if isinstance(self.ctx, disnake.AppCmdInter):
            await self.ctx.delete_original_message()
        else:
            await inter.message.delete()
        self.stop()

    async def remove_callback(self, inter: disnake.MessageInteraction):

        if not self.current:
            await inter.send("Morate odabrati stavku!", ephemeral=True)
            return

        await inter.response.defer(ephemeral=True)

        guild_data = await self.bot.get_data(inter.guild_id, db_name=DBModel.guilds)

        try:
            del guild_data["player_controller"]["fav_links"][self.current]
        except:
            raise GenericError(f"**Ne postoje linkovi na listu sa imenom:** {self.current}")

        await self.bot.update_data(inter.guild_id, guild_data, db_name=DBModel.guilds)

        guild = self.bot.get_guild(inter.guild_id) or inter.guild

        await inter.edit_original_message(
            embed=disnake.Embed(description="**Link je uspješno uklonjen!**", color=self.bot.get_color(guild.me)),
            view=None)

        await self.bot.get_cog("PinManager").process_idle_embed(guild)
        self.stop()

    async def cancel_callback(self, inter: disnake.MessageInteraction):
        await inter.response.edit_message(
            embed=disnake.Embed(
                description="**Operacija sa omiljenim serverima je otkazana...**",
                color=self.bot.get_color(),
            ), view=None
        )
        self.stop()

    async def select_callback(self, inter: disnake.MessageInteraction):
        self.current = inter.values[0]
        await inter.response.defer()


class PinManager(commands.Cog):

    def __init__(self, bot: BotCore):
        self.bot = bot

    desc_prefix = "📌 [Server Playlist] 📌 | "

    async def process_idle_embed(self, guild: disnake.Guild):
        guild_data = await self.bot.get_data(guild.id, db_name=DBModel.guilds)

        try:
            player: LavalinkPlayer = self.bot.music.players[guild.id]
            if not player.current:
                await player.process_idle_message()
            return
        except KeyError:
            pass

        try:
            channel = self.bot.get_channel(int(guild_data["player_controller"]["channel"]))
            message = await channel.fetch_message(int(guild_data["player_controller"]["message_id"]))

        except:
            return

        await send_idle_embed(message or channel, bot=self.bot, guild_data=guild_data)

    server_playlist_cd = commands.CooldownMapping.from_cooldown(3, 30, commands.BucketType.guild)

    @commands.max_concurrency(1, commands.BucketType.guild, wait=False)
    @commands.slash_command(
        default_member_permissions=disnake.Permissions(manage_guild=True),
        cooldown=server_playlist_cd
    )
    async def server_playlist(self, inter: disnake.AppCmdInter):
        pass

    @commands.has_guild_permissions(manage_guild=True)
    @commands.command(name="serverplaylist", aliases=["spl", "svp", "svpl"],
                      description="Upravljajte serverskim playlistama/favoritima.",
                      cooldown=server_playlist_cd)
    async def serverplaylist_legacy(self, ctx: CustomContext):
        await self.manager.callback(self=self, inter=ctx)

    @server_playlist.sub_command(
        description=f"{desc_prefix}Upravljajte serverskim playlistama/favoritima."
    )
    async def manager(self, inter: disnake.AppCmdInter):

        inter, bot = await select_bot_pool(inter)

        if not bot:
            return

        await inter.response.defer(ephemeral=True)

        guild_data = await bot.get_data(inter.guild_id, db_name=DBModel.guilds)

        view = GuildFavView(bot=bot, ctx=inter, data=guild_data)

        embed = disnake.Embed(
            description="**Server Bookmark Manager.**",
            colour=self.bot.get_color(),
        )

        if isinstance(inter, CustomContext):
            try:
                view.message = inter.store_message
                await inter.store_message.edit(embed=embed, view=view)
            except:
                view.message = await inter.send(embed=embed, view=view)
        else:
            try:
                await inter.edit_original_message(embed=embed, view=view)
            except:
                await inter.response.edit_message(embed=embed, view=view)

        await view.wait()

    @commands.cooldown(1, 20, commands.BucketType.guild)
    @server_playlist.sub_command(
        name="import", description=f"{desc_prefix}Uvezite linkove iz arh. json za listu linkova servera."
    )
    async def import_(
            self,
            inter: disnake.ApplicationCommandInteraction,
            file: disnake.Attachment = commands.Param(name="fajl", description="datoteka u .json formatu")
    ):

        if file.size > 2097152:
            raise GenericError("**Veličina fajla ne može biti veća od 2Mb!**")

        if not file.filename.endswith(".json"):
            raise GenericError("**Nevažeći tip datoteke!**")

        inter, bot = await select_bot_pool(inter)

        if not bot:
            return

        await inter.response.defer(ephemeral=True)

        try:
            data = (await file.read()).decode('utf-8')
            json_data = json.loads(data)
        except Exception as e:
            raise GenericError("**Došlo je do greške pri čitanju datoteke, pregledajte je i ponovo koristite naredbu.**\n"
                               f"```py\n{repr(e)}```")

        for name, data in json_data.items():

            if "> fav:" in name.lower():
                continue

            if len(data['url']) > (max_url_chars := bot.config["USER_FAV_MAX_URL_LENGTH"]):
                raise GenericError(f"**Stavka u vašoj datoteci premašuje dozvoljeni broj znakova:{max_url_chars}\nURL:** {data['url']}")

            if len(data['description']) > 50:
                raise GenericError(f"**Stavka u vašoj datoteci premašuje dozvoljeni broj znakova:{max_url_chars}\nDescrição:** {data['description']}")

            if not isinstance(data['url'], str) or not URL_REG.match(data['url']):
                raise GenericError(f"Vaš fajl sadrži nevažeći link: ```ldif\n{data['url']}```")

        guild_data = await self.bot.get_data(inter.guild_id, db_name=DBModel.guilds)

        if not guild_data["player_controller"]["channel"] or not bot.get_channel(int(guild_data["player_controller"]["channel"])):
            raise GenericError("**Nema konfigurisanog bota na serveru! Koristite naredbu /setup**")

        for name in json_data.keys():
            if len(name) > (max_name_chars := 25):
                raise GenericError(f"**Stavka iz vašeg fajla ({name}) premašuje dozvoljeni broj znakova:{max_name_chars}**")
            try:
                del guild_data["player_controller"]["fav_links"][name]
            except KeyError:
                continue

        if (json_size:=len(json_data)) > 25:
            raise GenericError(f"Broj stavki u arhivi premašuje maksimalno dozvoljeni broj (25).")

        if (json_size + (user_favs:=len(guild_data["player_controller"]["fav_links"]))) > 25:
            raise GenericError("Playlist/playlist servera nema dovoljno prostora za dodavanje svih stavki iz vašeg fajla...\n"
                                f"Granica: 25\n"
                                f"Broj sačuvanih linkova: {user_favs}\n"
                                f"Trebaš da: {(json_size + user_favs)-25}")

        guild_data["player_controller"]["fav_links"].update(json_data)

        await self.bot.update_data(inter.guild_id, guild_data, db_name=DBModel.guilds)

        guild = bot.get_guild(inter.guild_id) or inter.guild

        await inter.edit_original_message(
            embed = disnake.Embed(
                color=self.bot.get_color(guild.me),
                description = "**Linkovi su uspješno uvezeni!**\n"
                              "**Oni će se pojaviti kada plejer nije u upotrebi ili u stanju pripravnosti..**",
            ), view=None
        )

        await self.process_idle_embed(guild)

    @commands.cooldown(1, 20, commands.BucketType.guild)
    @server_playlist.sub_command(
        description=f"{desc_prefix}Izvezite fiksne linkove pjesama/liste za reprodukciju na serveru u json datoteku."
    )
    async def export(self, inter: disnake.ApplicationCommandInteraction):

        inter, bot = await select_bot_pool(inter)

        if not bot:
            return

        await inter.response.defer(ephemeral=True)

        guild_data = await bot.get_data(inter.guild_id, db_name=DBModel.guilds)

        if not guild_data["player_controller"]["fav_links"]:
            raise GenericError(f"**Na serveru nema zakačenih pesama/lista za reprodukciju..\n"
                               f"Možete dodati pomoću naredbe: /{self.server_playlist.name} {self.export.name}**")

        fp = BytesIO(bytes(json.dumps(guild_data["player_controller"]["fav_links"], indent=4), 'utf-8'))

        guild = bot.get_guild(inter.guild_id) or inter.guild

        embed = disnake.Embed(
            description=f"**Ovdje se nalaze fiksni podaci o pjesmi/listama za reprodukciju na serveru.\n"
                        f"Možete uvesti pomoću naredbe:** `/{self.server_playlist.name} {self.import_.name}`",
            color=self.bot.get_color(guild.me))

        await inter.edit_original_message(embed=embed, file=disnake.File(fp=fp, filename="guild_favs.json"), view=None)


def setup(bot: BotCore):
    bot.add_cog(PinManager(bot))
