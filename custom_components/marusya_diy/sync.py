"""Keep an account linked to the DIY configuration built from its device description."""

# @tag:diy-sync
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .api import DiyDevice, MarusyaClient, MarusyaError, MarusyaSessionGone
from .cabinet import Cabinet, CabinetError, CabinetSessionGone
from .diy_yaml import fingerprint

_LOGGER = logging.getLogger(__name__)

STATE_LINKED = "linked"
STATE_UNCHANGED = "unchanged"
STATE_NO_DEVICES = "no_devices"


class SyncError(Exception):
    """Sync stopped at `step`; `rolled_back` tells whether the previous configuration is linked again."""

    def __init__(self, step: str, detail: str, rolled_back: bool) -> None:
        super().__init__(f"{step}: {detail}")
        self.step = step
        self.detail = detail
        self.rolled_back = rolled_back


@dataclass(frozen=True)
class Linked:
    config_id: str
    config_name: str
    fingerprint: str


@dataclass(frozen=True)
class SyncOutcome:
    state: str
    linked: Linked | None
    devices: list[DiyDevice] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


async def async_sync(
    client: MarusyaClient,
    cabinet: Cabinet,
    config_name: str,
    text: str,
    device_ids: list[str],
    previous: Linked | None,
    force: bool = False,
) -> SyncOutcome:
    """Upload `text` as `config_name`, relink the account to it, drop older copies.

    Session loss (`MarusyaSessionGone`, `CabinetSessionGone`) propagates as is: it needs a new login,
    not a retry. Other refusals become `SyncError`.
    """
    cabinet_ids = {c.id for c in await cabinet.configs()}
    if not device_ids:
        if previous is None:
            return SyncOutcome(STATE_NO_DEVICES, None)
        return await _clear(client, cabinet, config_name)
    new_fingerprint = fingerprint(text)
    if (
        not force
        and previous is not None
        and previous.fingerprint == new_fingerprint
        and previous.config_id in cabinet_ids
        and await client.diy_is_linked()
    ):
        return SyncOutcome(STATE_UNCHANGED, previous)

    try:
        new = await cabinet.upload(config_name, text)
    except CabinetSessionGone:
        raise
    except CabinetError as err:
        raise SyncError(err.step, err.detail, rolled_back=True) from err

    try:
        await _relink(client, cabinet, new.id)
    except (MarusyaSessionGone, CabinetSessionGone):
        await _remove_quietly(cabinet, new.id)
        raise
    except (MarusyaError, CabinetError) as err:
        rolled_back = False
        if previous is not None and previous.config_id in cabinet_ids:
            try:
                await _relink(client, cabinet, previous.config_id)
                rolled_back = True
            except (MarusyaError, CabinetError) as rollback_err:
                _LOGGER.warning("Relinking the previous DIY configuration failed: %s", rollback_err)
        await _remove_quietly(cabinet, new.id)
        raise SyncError(err.step, err.detail, rolled_back) from err

    for stale in await cabinet.configs():
        if stale.name == config_name and stale.id != new.id:
            await _remove_quietly(cabinet, stale.id)
    devices = await client.diy_devices()
    visible = {d.uid for d in devices}
    missing = [i for i in device_ids if f"diy|{i}" not in visible]
    return SyncOutcome(STATE_LINKED, Linked(new.id, config_name, new_fingerprint), devices, missing)


async def _relink(client: MarusyaClient, cabinet: Cabinet, config_id: str) -> None:
    if await client.diy_is_linked():
        await client.unlink_diy()
    await cabinet.choose(client.diy_link_url(), config_id)


async def _clear(client: MarusyaClient, cabinet: Cabinet, config_name: str) -> SyncOutcome:
    """Undo our own link only: an account never synced keeps whatever DIY it had."""
    try:
        if await client.diy_is_linked():
            await client.unlink_diy()
    except MarusyaSessionGone:
        raise
    except MarusyaError as err:
        raise SyncError(err.step, err.detail, rolled_back=False) from err
    for stale in await cabinet.configs():
        if stale.name == config_name:
            await _remove_quietly(cabinet, stale.id)
    return SyncOutcome(STATE_NO_DEVICES, None)


async def _remove_quietly(cabinet: Cabinet, config_id: str) -> None:
    """A leftover configuration costs nothing but clutter; the next sync removes it by name."""
    try:
        await cabinet.remove(config_id)
    except CabinetError as err:
        _LOGGER.warning("Removing DIY configuration %s from the cabinet failed: %s", config_id, err)
