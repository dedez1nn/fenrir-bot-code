import discord
from discord.ext import commands, tasks

class RenameModal(discord.ui.Modal, title="✏️ Renomear Sala"):
    new_name = discord.ui.TextInput(label="Novo nome da sala", max_length=30)

    def __init__(self, voice_channel):
        super().__init__()
        self.voice_channel = voice_channel

    async def on_submit(self, interaction: discord.Interaction):
        await self.voice_channel.edit(name=self.new_name.value)
        await interaction.response.send_message(
            f"✅ Sala renomeada para **{self.new_name.value}**.", ephemeral=True
        )


class LimitModal(discord.ui.Modal, title="👥 Limitar Pessoas"):
    limit_value = discord.ui.TextInput(
        label="Número máximo de pessoas (0 = ilimitado)", max_length=2
    )

    def __init__(self, voice_channel):
        super().__init__()
        self.voice_channel = voice_channel

    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit = int(self.limit_value.value)
        except ValueError:
            return await interaction.response.send_message("❌ Valor inválido.", ephemeral=True)

        await self.voice_channel.edit(user_limit=limit)
        msg = f"✅ Limite definido para {limit} pessoas." if limit > 0 else "✅ Limite removido."
        await interaction.response.send_message(msg, ephemeral=True)


class PrivacySelectView(discord.ui.View):
    def __init__(self, voice_channel):
        super().__init__(timeout=None)
        self.voice_channel = voice_channel

    @discord.ui.select(
        placeholder="Escolha a visibilidade da sala...",
        options=[
            discord.SelectOption(label="Pública 🌍", description="Todos podem ver e entrar."),
            discord.SelectOption(label="Privada 🔒", description="Somente convidados."),
        ],
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        guild = interaction.guild
        if select.values[0].startswith("Pública"):
            await self.voice_channel.set_permissions(guild.default_role, view_channel=True, connect=True)
            await interaction.response.send_message("✅ Sala agora é **pública**.", ephemeral=True)
        else:
            await self.voice_channel.set_permissions(guild.default_role, view_channel=False, connect=False)
            await interaction.response.send_message("🔒 Sala agora é **privada**.", ephemeral=True)


class TransferSelectView(discord.ui.View):
    def __init__(self, bot, voice_channel, owner_ref):
        super().__init__(timeout=None)
        self.bot = bot
        self.voice_channel = voice_channel
        self.owner_ref = owner_ref

        options = [
            discord.SelectOption(label=m.display_name, value=str(m.id))
            for m in voice_channel.members if not m.bot
        ]
        if not options:
            options = [discord.SelectOption(label="Ninguém disponível", value="none", default=True)]

        select = discord.ui.Select(placeholder="Selecione o novo dono...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if self.owner_ref not in self.voice_channel.members:
            return await interaction.response.send_message(
                "❌ O dono original não está mais na sala.", ephemeral=True
            )
        if self.values[0] == "none":
            return await interaction.response.send_message("⚠️ Nenhum membro selecionado.", ephemeral=True)

        new_owner = interaction.guild.get_member(int(self.children[0].values[0]))
        old_owner = self.owner_ref
        await self.voice_channel.set_permissions(new_owner, manage_channels=True, connect=True)
        await self.voice_channel.set_permissions(old_owner, manage_channels=False)
        await interaction.response.send_message(
            f"✅ Propriedade transferida para {new_owner.mention}.", ephemeral=True
        )
        self.owner_ref = new_owner


class KickSelectView(discord.ui.View):
    def __init__(self, voice_channel):
        super().__init__(timeout=None)
        self.voice_channel = voice_channel

        options = [
            discord.SelectOption(label=m.display_name, value=str(m.id))
            for m in voice_channel.members if not m.bot
        ]
        if not options:
            options = [discord.SelectOption(label="Nenhum usuário disponível", value="none", default=True)]

        select = discord.ui.Select(placeholder="Selecione quem expulsar...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if self.children[0].values[0] == "none":
            return await interaction.response.send_message("⚠️ Nenhum membro selecionado.", ephemeral=True)

        member = interaction.guild.get_member(int(self.children[0].values[0]))
        await member.move_to(None)
        await interaction.response.send_message(f"🚫 {member.mention} foi expulso da sala.", ephemeral=True)


class VoiceControlView(discord.ui.View):
    def __init__(self, bot, owner, voice_channel):
        super().__init__(timeout=None)
        self.bot = bot
        self.owner = owner
        self.voice_channel = voice_channel

    async def _check_owner(self, interaction: discord.Interaction):
        if interaction.user != self.owner:
            await interaction.response.send_message("❌ Apenas o dono pode usar isso.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✏️ Renomear", style=discord.ButtonStyle.primary)
    async def rename_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._check_owner(interaction):
            await interaction.response.send_modal(RenameModal(self.voice_channel))

    @discord.ui.button(label="👥 Limitar", style=discord.ButtonStyle.primary)
    async def limit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._check_owner(interaction):
            await interaction.response.send_modal(LimitModal(self.voice_channel))

    @discord.ui.button(label="🔒 Privacidade", style=discord.ButtonStyle.secondary)
    async def privacy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._check_owner(interaction):
            await interaction.response.send_message(
                "Selecione o modo de privacidade:",
                view=PrivacySelectView(self.voice_channel),
                ephemeral=True,
            )

    @discord.ui.button(label="🔁 Transferir", style=discord.ButtonStyle.secondary)
    async def transfer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._check_owner(interaction):
            await interaction.response.send_message(
                "Selecione o novo dono:",
                view=TransferSelectView(self.bot, self.voice_channel, self.owner),
                ephemeral=True,
            )

    @discord.ui.button(label="🚫 Expulsar", style=discord.ButtonStyle.danger)
    async def kick_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._check_owner(interaction):
            await interaction.response.send_message(
                "Selecione quem expulsar:", view=KickSelectView(self.voice_channel), ephemeral=True
            )

    @discord.ui.button(label="🗑️ Excluir", style=discord.ButtonStyle.danger)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._check_owner(interaction):
            await self.voice_channel.delete()
            await interaction.response.send_message("✅ Sala excluída.", ephemeral=True)


_DEFAULT_VOICE_CREATOR_CH = 1429479982014660712


class VoiceCreator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.main_channel_id = _DEFAULT_VOICE_CREATOR_CH
        self.cleanup_loop.start()

    async def cog_load(self) -> None:
        cfg = getattr(self.bot, "config", None)
        self.main_channel_id = (cfg.get("voice_creator_channel_id") if cfg else None) or _DEFAULT_VOICE_CREATOR_CH

    def cog_unload(self):
        self.cleanup_loop.cancel()

    async def _cleanup_logic(self):
        for guild in self.bot.guilds:
            for channel in guild.voice_channels:
                if channel.name.startswith("🔊 Sala de") and len(channel.members) == 0:
                    try:
                        await channel.delete()
                    except (discord.Forbidden, discord.HTTPException):
                        pass

    @tasks.loop(minutes=2)
    async def cleanup_loop(self):
        await self._cleanup_logic()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if after.channel and after.channel.id == self.main_channel_id:
            guild = member.guild
            category = after.channel.category


            new_channel = await guild.create_voice_channel(
                name=f"🔊 Sala de {member.display_name}",
                category=category,
            )

            await member.move_to(new_channel)

            embed = discord.Embed(
                title="🎛️ Painel da sua Call",
                description=(
                    "Aqui você pode **gerenciar sua call**:\n\n"
                    "📝 Renomear\n"
                    "👥 Limitar pessoas\n"
                    "🔒 Privacidade\n"
                    "🔄 Transferir\n"
                    "🚫 Expulsar\n"
                    "🗑️ Excluir"
                ),
                color=discord.Color.blurple()
            )

            view = VoiceControlView(self.bot, member, new_channel)
            await new_channel.send(embed=embed, view=view)

    @tasks.loop(minutes=2)
    async def cleanup_loop(self):
        for guild in self.bot.guilds:
            for channel in guild.voice_channels:
                if channel.name.startswith("🔊 Sala de") and len(channel.members) == 0:
                    try:
                        await channel.delete()
                    except discord.Forbidden:
                        pass
                    except discord.HTTPException:
                        pass

async def setup(bot):
    await bot.add_cog(VoiceCreator(bot))
