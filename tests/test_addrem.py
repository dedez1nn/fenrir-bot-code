import pytest
from unittest.mock import AsyncMock, Mock

from cogs.moderacao.addrem import AddRole


@pytest.fixture
def cog():
    bot = Mock()
    return AddRole(bot)


@pytest.fixture
def ctx():
    ctx = AsyncMock()
    ctx.send = AsyncMock()

    ctx.author = Mock()
    ctx.author.mention = "@admin"

    ctx.guild = Mock()
    ctx.guild.me = Mock()
    ctx.guild.me.top_role = Mock(position=10)

    return ctx


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
async def test_addrole_success(cog, ctx, member, role):
    await cog.addrole.callback(cog, ctx, member, role)

    member.add_roles.assert_called_once_with(role)
    ctx.send.assert_called()


@pytest.mark.asyncio
async def test_addrole_cargo_alto(cog, ctx, member, role):
    role.position = 20

    await cog.addrole.callback(cog, ctx, member, role)

    ctx.send.assert_called_with("❌ Não posso adicionar este cargo (posição muito alta).")


@pytest.mark.asyncio
async def test_addrole_usuario_ja_tem(cog, ctx, member, role):
    member.roles = [role]

    await cog.addrole.callback(cog, ctx, member, role)

    ctx.send.assert_called()


# -----------------------
# REMOVE ROLE
# -----------------------

@pytest.mark.asyncio
async def test_removerole_success(cog, ctx, member, role):
    member.roles = [role]

    await cog.removerole.callback(cog, ctx, member, role)

    member.remove_roles.assert_called_once_with(role)


@pytest.mark.asyncio
async def test_removerole_usuario_sem_cargo(cog, ctx, member, role):
    member.roles = []

    await cog.removerole.callback(cog, ctx, member, role)

    ctx.send.assert_called()


# -----------------------
# ADD ROLE ALL
# -----------------------

@pytest.mark.asyncio
async def test_addrole_all_success(cog, ctx, role):
    m1 = Mock(bot=False, roles=[])
    m1.add_roles = AsyncMock()

    m2 = Mock(bot=False, roles=[role])

    ctx.guild.members = [m1, m2]

    await cog.addrole_all.callback(cog, ctx, role)

    m1.add_roles.assert_called_once_with(role)
    ctx.send.assert_called()


# -----------------------
# REMOVE ROLE ALL
# -----------------------

@pytest.mark.asyncio
async def test_removerole_all_success(cog, ctx, role):
    m1 = Mock(bot=False, roles=[role])
    m1.remove_roles = AsyncMock()

    m2 = Mock(bot=False, roles=[])

    ctx.guild.members = [m1, m2]

    await cog.removerole_all.callback(cog, ctx, role)

    m1.remove_roles.assert_called_once_with(role)
    ctx.send.assert_called()
