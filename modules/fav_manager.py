from __future__ import annotations
from typing import TYPE_CHECKING, Union, Optional
from io import BytesIO
import json

import disnake
from disnake.ext import commands

from utils.db import DBModel
from utils.music.converters import URL_REG
from utils.others import CustomContext
from utils.music.errors import GenericError

if TYPE_CHECKING:
    from utils.client import BotCore


class UserFavModal(disnake.ui.Modal):
    def __init__(self, bot: BotCore, name: Optional[str], url: Optional[str]):

        self.bot = bot
        self.name = name

        super().__init__(
            title="Dodaj/uredi plejlistu/favorite",
            custom_id="user_fav_edit",
            timeout=180,
            components=[
                disnake.ui.TextInput(
                    label="Ime plejliste/favoriti:",
                    custom_id="user_fav_name",
                    min_length=2,
                    max_length=25,
                    value=name or None
                ),
                disnake.ui.TextInput(
                    label="Link/Url:",
                    custom_id="user_fav_url",
                    min_length=10,
                    max_length=200,
                    value=url or None
                ),
            ]
        )

    async def callback(self, inter: disnake.ModalInteraction):

        url = inter.text_values["user_fav_url"]

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

        user_data = await self.bot.get_global_data(inter.author.id, db_name=DBModel.users)

        name = inter.text_values["user_fav_name"]

        try:
            if name != self.name:
                del user_data["fav_links"][self.name]
        except KeyError:
            pass

        user_data["fav_links"][name] = valid_url

        await self.bot.update_global_data(inter.author.id, user_data, db_name=DBModel.users)

        guild = inter.guild or self.bot.get_guild(inter.guild_id)

        await inter.edit_original_message(
            embed=disnake.Embed(
                description="**Link je uspješno sačuvan/ažuriran u vaše favorite!\n"
                            "On će se pojaviti u sljedećim prilikama:** ```\n"
                            "- Kada koristite naredbu /play (pri automatskom dovršavanju pretrage)\n"
                            "- Klikom na dugme Zatraži muzički plejer.\n"
                            "- Kada koristite naredbu play (sa prefiksom) bez imena ili veze.```",
                color=self.bot.get_color(guild.me)
            )
        )

class UserFavView(disnake.ui.View):

    def __init__(self, bot: BotCore, ctx: Union[disnake.AppCmdInter, CustomContext], data: dict):
        super().__init__(timeout=60)
        self.bot = bot
        self.ctx = ctx
        self.current = None
        self.data = data
        self.message = None

        if data["fav_links"]:

            fav_select = disnake.ui.Select(options=[
                disnake.SelectOption(label=k) for k, v in data["fav_links"].items()
            ], min_values=1, max_values=1)
            fav_select.callback = self.select_callback
            self.add_item(fav_select)

        favadd_button = disnake.ui.Button(label="Dodati", emoji="⭐")
        favadd_button.callback = self.favadd_callback
        self.add_item(favadd_button)

        if data["fav_links"]:

            edit_button = disnake.ui.Button(label="Uredi", emoji="✍️")
            edit_button.callback = self.edit_callback
            self.add_item(edit_button)

            remove_button = disnake.ui.Button(label="Izbrisi", emoji="♻️")
            remove_button.callback = self.remove_callback
            self.add_item(remove_button)

            clear_button = disnake.ui.Button(label="Favoriti", emoji="🚮")
            clear_button.callback = self.clear_callback
            self.add_item(clear_button)

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
        await inter.response.send_modal(UserFavModal(bot=self.bot, name=None, url=None))
        await inter.delete_original_message()
        self.stop()

    async def edit_callback(self, inter: disnake.MessageInteraction):

        if not self.current:
            await inter.send("Morate odabrati stavku!", ephemeral=True)
            return

        try:
            await inter.response.send_modal(
                UserFavModal(
                    bot=self.bot, name=self.current,
                    url=self.data["fav_links"][self.current],
                )
            )
        except KeyError:
            await inter.send(f"**Ne postoji favorit sa imenom:** {self.current}", ephemeral=True)
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

        user_data = await self.bot.get_global_data(inter.author.id, db_name=DBModel.users)

        try:
            del user_data["fav_links"][self.current]
        except:
            raise GenericError(f"**Na listi nema favorita sa imenom:** {self.current}")

        await self.bot.update_global_data(inter.author.id, user_data, db_name=DBModel.users)

        guild = self.bot.get_guild(inter.guild_id) or inter.guild

        await inter.edit_original_message(
            embed=disnake.Embed(
                description="**Link/Favorite je uspješno uklonjen!**",
                color=self.bot.get_color(guild.me)),
            view=None
        )
        self.stop()

    async def clear_callback(self, inter: disnake.MessageInteraction):

        await inter.response.defer(ephemeral=True)

        data = await self.bot.get_global_data(inter.author.id, db_name=DBModel.users)

        if not data["fav_links"]:
            raise GenericError("**Nemate omiljenih linkova!**")

        data["fav_links"].clear()

        await self.bot.update_global_data(inter.author.id, data, db_name=DBModel.users)

        embed = disnake.Embed(
            description="Vaša lista favorita je uspješno obrisana!",
            color=self.bot.get_color()
        )

        await inter.edit_original_message(embed=embed)
        self.stop()

    async def cancel_callback(self, inter: disnake.MessageInteraction):
        await inter.response.edit_message(
            embed=disnake.Embed(
                description="**Operacija sa favoritima je otkazana...**",
                color=self.bot.get_color(),
            ), view=None
        )
        self.stop()

    async def select_callback(self, inter: disnake.MessageInteraction):
        self.current = inter.values[0]
        await inter.response.defer()


class FavManager(commands.Cog):

    def __init__(self, bot: BotCore):
        self.bot = bot

    desc_prefix = "⭐ [Favoritos] ⭐ | "

    fav_cd = commands.CooldownMapping.from_cooldown(3, 15, commands.BucketType.member)

    @commands.max_concurrency(1, commands.BucketType.member, wait=False)
    @commands.slash_command()
    async def fav(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @commands.command(name="favmanager", aliases=["favs", "favoritos", "fvmgr"],
                      description="Upravljajte svojim listama za reprodukciju/favoritima.", cooldown=fav_cd)
    async def favmanager_legacy(self, ctx: CustomContext):
        await self.manager.callback(self=self, inter=ctx)

    @fav.sub_command(
        description=f"{desc_prefix}Upravljajte svojim listama za reprodukciju/favoritima.", cooldown=fav_cd
    )
    async def manager(self, inter: disnake.AppCmdInter):

        await inter.response.defer(ephemeral=True)

        user_data = await self.bot.get_global_data(inter.author.id, db_name=DBModel.users)

        view = UserFavView(bot=self.bot, ctx=inter, data=user_data)

        embed = disnake.Embed(
            description="**Upravitelj omiljenih korisnika.**",
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

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.command(name="favlist", description="Pogledajte svoju listu favorita.")
    async def favlist_legacy(self, ctx: CustomContext):
        await self.list_.callback(self=self, inter=ctx, hidden=False)

    @commands.cooldown(1, 5, commands.BucketType.user)
    @fav.sub_command(
        name="list", description=f"{desc_prefix}Pogledajte svoju listu favorita."
    )
    async def list_(
            self, inter: disnake.ApplicationCommandInteraction,
            hidden: bool = commands.Param(
                name="maskiranje",
                description="Samo vi možete vidjeti listu favorita.",
                default=False)
    ):

        if hidden is False and not self.bot.check_bot_forum_post(inter.channel):
            hidden = True

        await inter.response.defer(ephemeral=hidden)

        user_data = await self.bot.get_global_data(inter.author.id, db_name=DBModel.users)

        if not user_data["fav_links"]:
            raise GenericError(f"**Nemate omiljenih linkova..\n"
                               f"Možete dodati pomoću naredbe: /{self.fav.name} {self.manager.name}**")

        embed = disnake.Embed(
            color=self.bot.get_color(),
            title="Vaši omiljeni linkovi:",
            description="\n".join(f"{n+1}) [`{f[0]}`]({f[1]})" for n, f in enumerate(user_data["fav_links"].items()))
        )

        embed.set_footer(text="Možete ih koristiti u komandi /play")

        if isinstance(inter, CustomContext):
            await inter.send(embed=embed)
        else:
            await inter.edit_original_message(embed=embed)

    fav_import_export_cd = commands.CooldownMapping.from_cooldown(1, 15, commands.BucketType.member)

    @fav.sub_command(
        name="import", description=f"{desc_prefix}Uvezite svoje oznake iz datoteke.",
        cooldown=fav_import_export_cd
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

        await inter.response.defer(ephemeral=True)

        try:
            data = (await file.read()).decode('utf-8')
            json_data = json.loads(data)
        except Exception as e:
            raise GenericError("**Došlo je do greške pri čitanju datoteke, pregledajte je i ponovo koristite naredbu.**\n"
                               f"```py\n{repr(e)}```")

        for name, url in json_data.items():

            if "> fav:" in name.lower():
                continue

            if len(url) > (max_url_chars := self.bot.config["USER_FAV_MAX_URL_LENGTH"]):
                raise GenericError(f"**Stavka iz vašeg fajla {url} premašuje dozvoljeni broj znakova:{max_url_chars}**")

            if not isinstance(url, str) or not URL_REG.match(url):
                raise GenericError(f"Vaš fajl sadrži nevažeći link: ```ldif\n{url}```")

        user_data = await self.bot.get_global_data(inter.author.id, db_name=DBModel.users)

        for name in json_data.keys():
            if len(name) > (max_name_chars := self.bot.config["USER_FAV_MAX_NAME_LENGTH"]):
                raise GenericError(f"**Stavka iz vašeg fajla ({name}) premašuje dozvoljeni broj znakova:{max_name_chars}**")
            try:
                del user_data["fav_links"][name.lower()]
            except KeyError:
                continue

        if self.bot.config["MAX_USER_FAVS"] > 0 and not (await self.bot.is_owner(inter.author)):

            if (json_size:=len(json_data)) > self.bot.config["MAX_USER_FAVS"]:
                raise GenericError(f"Broj stavki u vašoj datoteci oznaka premašuje "
                                   f"maksimalno dozvoljeni iznos ({self.bot.config['MAX_USER_FAVS']}).")

            if (json_size + (user_favs:=len(user_data["fav_links"]))) > self.bot.config["MAX_USER_FAVS"]:
                raise GenericError("Nemate dovoljno prostora da dodate sve oznake u svoj fajl...\n"
                                   f"Limit: {self.bot.config['MAX_USER_FAVS']}\n"
                                   f"Broj sačuvanih favorita: {user_favs}\n"
                                   f"Trebaš da: {(json_size + user_favs)-self.bot.config['MAX_USER_FAVS']}")

        user_data["fav_links"].update(json_data)

        await self.bot.update_global_data(inter.author.id, user_data, db_name=DBModel.users)

        await inter.edit_original_message(
            embed = disnake.Embed(
                color=self.bot.get_color(),
                description = "**Linkovi su uspješno uvezeni!**\n"
                              "**Oni će se pojaviti kada koristite naredbu /play (pri automatskom dovršavanju pretraživanja).**",
            )
        )

    @fav.sub_command(
        description=f"{desc_prefix}Izvezite svoje oznake u json datoteku.",
        cooldown=fav_import_export_cd
    )
    async def export(self, inter: disnake.ApplicationCommandInteraction):

        await inter.response.defer(ephemeral=True)

        user_data = await self.bot.get_global_data(inter.author.id, db_name=DBModel.users)

        if not user_data["fav_links"]:
            raise GenericError(f"**Nemate omiljenih linkova..\n"
                               f"Možete dodati pomoću naredbe: /{self.fav.name} {self.manager.name}**")

        fp = BytesIO(bytes(json.dumps(user_data["fav_links"], indent=4), 'utf-8'))

        embed = disnake.Embed(
            description=f"Vaše oznake su ovdje.\Možete uvesti pomoću naredbe: `/{self.import_.name}`",
            color=self.bot.get_color())

        await inter.edit_original_message(embed=embed, file=disnake.File(fp=fp, filename="favoritos.json"))


def setup(bot: BotCore):
    bot.add_cog(FavManager(bot))
