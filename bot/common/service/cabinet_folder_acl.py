"""Доступ к папкам кабинетов карточек / пипсов / анализа матча."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from bot.common.service.cabinet_admin import is_cabinet_admin


def viewer_owns_folder(folder, user_id: int, is_admin: bool) -> bool:
    owner = getattr(folder, "owner_user_id", None)
    if owner is not None and int(owner) == int(user_id):
        return True
    if not is_admin:
        return False
    if owner is None:
        return True
    return is_cabinet_admin(int(owner))


async def folder_has_shared_grant(
    session,
    *,
    grant_model,
    folder_model,
    folder,
    user_id: int,
) -> bool:
    chain_ids = [int(folder.id)]
    current = folder
    visited: set[int] = set()
    while current.parent_id:
        parent_id = int(current.parent_id)
        if parent_id in visited:
            break
        visited.add(parent_id)
        parent = await session.get(folder_model, parent_id)
        if not parent:
            break
        chain_ids.append(int(parent.id))
        current = parent
    grant = await session.scalar(
        select(grant_model.id)
        .join(folder_model, folder_model.id == grant_model.folder_id)
        .where(
            grant_model.user_id == int(user_id),
            grant_model.folder_id.in_(chain_ids),
            folder_model.is_shared.is_(True),
        )
        .limit(1)
    )
    return grant is not None


async def collect_granted_subtree(
    session,
    *,
    folder_model,
    grant_model,
    user_id: int,
    extra_where=(),
) -> dict[int, Any]:
    granted_res = await session.execute(
        select(folder_model)
        .join(grant_model, grant_model.folder_id == folder_model.id)
        .where(
            grant_model.user_id == int(user_id),
            folder_model.is_shared.is_(True),
            *extra_where,
        )
    )
    granted_roots = list(granted_res.scalars().all())
    if not granted_roots:
        return {}

    owner_ids = {int(root.owner_user_id) for root in granted_roots if root.owner_user_id}
    trees: dict[int | None, list[Any]] = {}
    if owner_ids:
        owned_res = await session.execute(
            select(folder_model).where(
                folder_model.owner_user_id.in_(owner_ids),
                *extra_where,
            )
        )
        for item in owned_res.scalars().all():
            trees.setdefault(item.owner_user_id, []).append(item)
    catalog_needed = any(root.owner_user_id is None for root in granted_roots)
    if catalog_needed:
        catalog_res = await session.execute(
            select(folder_model).where(folder_model.owner_user_id.is_(None), *extra_where)
        )
        trees.setdefault(None, list(catalog_res.scalars().all()))

    by_id: dict[int, Any] = {}
    for root in granted_roots:
        children_map: dict[int | None, list[Any]] = {}
        for item in trees.get(root.owner_user_id, []):
            children_map.setdefault(item.parent_id, []).append(item)
        queue = [root]
        seen: set[int] = set()
        while queue:
            current = queue.pop(0)
            cid = int(current.id)
            if cid in seen:
                continue
            seen.add(cid)
            by_id[cid] = current
            queue.extend(children_map.get(cid, []))
    return by_id


async def grant_folder_access(
    session,
    *,
    grant_model,
    folder_id: int,
    target_user_id: int,
    granted_by: int,
) -> tuple[Any, bool]:
    existing = await session.scalar(
        select(grant_model).where(
            grant_model.folder_id == int(folder_id),
            grant_model.user_id == int(target_user_id),
        )
    )
    if existing:
        return existing, False
    grant = grant_model(
        folder_id=int(folder_id),
        user_id=int(target_user_id),
        granted_by=int(granted_by),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(grant)
    await session.flush()
    return grant, True
