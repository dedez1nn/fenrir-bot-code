import pytest
from unittest.mock import AsyncMock, Mock
import discord

from cogs.addrem import AddRole


@pytest.fixture
def cog():
    bot = Mock()
    return AddRole(bot)


@pytest.fixture
def interaction():
    interaction = AsyncMock()

    # response e followup
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    # usuário com permissão
    interaction.user = Mock()
    interaction.user.guild_permissions = Mock(manage_roles=True)
    interaction.user.mention = "@admin"

    # guild e bot role
    interaction.guild = Mock()
    interaction.guild.me = Mock()
    interaction.guild.me.top_role = Mock(position=10)

    return interaction


@pytest.fixture
def role():
    role = Mock()
    role.position = 1
    role.mention = "@cargo"
    return role


@pytest.fixture
def member():
    member = Mock()
    member.roles = []
    member.bot = False
    member.mention = "@user"
    member.id = 123
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()
    return member


# -----------------------
# ADD ROLE
# -----------------------

@pytest.mark.asyncio
async def test_addrole_success(cog, interaction, member, role):
    await cog.addrole.callback(cog, interaction, member, role)

    member.add_roles.assert_called_once_with(role)
    interaction.response.send_message.assert_called()


@pytest.mark.asyncio
async def test_addrole_sem_permissao(cog, interaction, member, role):
    interaction.user.guild_permissions.manage_roles = False

    await cog.addrole.callback(cog, interaction, member, role)

    interaction.response.send_message.assert_called_with(
        "❌ Você não tem permissão para gerenciar cargos.",
        ephemeral=True
    )


@pytest.mark.asyncio
async def test_addrole_cargo_alto(cog, interaction, member, role):
    role.position = 20

    await cog.addrole.callback(cog, interaction, member, role)

    interaction.response.send_message.assert_called_with(
        "❌ Não posso adicionar este cargo (posição muito alta).",
        ephemeral=True
    )


@pytest.mark.asyncio
async def test_addrole_usuario_ja_tem(cog, interaction, member, role):
    member.roles = [role]

    await cog.addrole.callback(cog, interaction, member, role)

    interaction.response.send_message.assert_called()


# -----------------------
# REMOVE ROLE
# -----------------------

@pytest.mark.asyncio
async def test_removerole_success(cog, interaction, member, role):
    member.roles = [role]

    await cog.removerole.callback(cog, interaction, member, role)

    member.remove_roles.assert_called_once_with(role)


@pytest.mark.asyncio
async def test_removerole_usuario_sem_cargo(cog, interaction, member, role):
    member.roles = []

    await cog.removerole.callback(cog, interaction, member, role)

    interaction.response.send_message.assert_called()


# -----------------------
# ADD ROLE ALL
# -----------------------

@pytest.mark.asyncio
async def test_addrole_all_success(cog, interaction, role):
    m1 = Mock(bot=False, roles=[])
    m1.add_roles = AsyncMock()

    m2 = Mock(bot=False, roles=[role])

    interaction.guild.members = [m1, m2]

    await cog.addrole_all.callback(cog, interaction, role)

    m1.add_roles.assert_called_once_with(role)
    interaction.followup.send.assert_called()


# -----------------------
# REMOVE ROLE ALL
# -----------------------

@pytest.mark.asyncio
async def test_removerole_all_success(cog, interaction, role):
    m1 = Mock(bot=False, roles=[role])
    m1.remove_roles = AsyncMock()

    m2 = Mock(bot=False, roles=[])

    interaction.guild.members = [m1, m2]

    await cog.removerole_all.callback(cog, interaction, role)

    m1.remove_roles.assert_called_once_with(role)
    interaction.followup.send.assert_called()