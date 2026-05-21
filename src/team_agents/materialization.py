from __future__ import annotations

import os
import shutil
from pathlib import Path

from team_agents.errors import ValidationError


MATERIALIZATION_STRATEGIES = {"auto", "symlink", "junction", "hardlink", "copy", "render-only"}


def validate_materialization_strategy(strategy: str) -> None:
    if strategy not in MATERIALIZATION_STRATEGIES:
        expected = ", ".join(sorted(MATERIALIZATION_STRATEGIES))
        raise ValidationError(f"Unsupported materialization strategy {strategy!r}; expected one of {expected}")


def effective_materialization_strategy(strategy: str) -> str:
    validate_materialization_strategy(strategy)
    if strategy != "auto":
        return strategy
    return "copy"


def materialization_warnings(strategy: str) -> list[str]:
    validate_materialization_strategy(strategy)
    if strategy == "junction" and os.name != "nt":
        return ["junction materialization is only supported on Windows"]
    if strategy == "hardlink":
        return ["hardlink materialization is file-oriented and may not preserve directory semantics across filesystems"]
    return []


def materialize_path(source: Path, target: Path, *, strategy: str, target_is_directory: bool) -> None:
    effective = effective_materialization_strategy(strategy)
    if effective == "render-only":
        remove_path(target)
        return
    if effective == "copy":
        copy_path(source, target, target_is_directory=target_is_directory)
        return
    if effective == "symlink":
        symlink_path(source, target, target_is_directory=target_is_directory)
        return
    if effective == "junction":
        if os.name != "nt":
            raise ValidationError("junction materialization is only supported on Windows")
        symlink_path(source, target, target_is_directory=target_is_directory)
        return
    if effective == "hardlink":
        hardlink_path(source, target, target_is_directory=target_is_directory)
        return
    raise ValidationError(f"Unsupported effective materialization strategy {effective!r}")


def copy_path(source: Path, target: Path, *, target_is_directory: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    source = source.resolve()
    if target.exists() or target.is_symlink():
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
    if target_is_directory:
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)


def symlink_path(source: Path, target: Path, *, target_is_directory: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        if target.resolve() == source.resolve():
            return
        target.unlink()
    elif target.exists():
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    target.symlink_to(source, target_is_directory=target_is_directory)


def hardlink_path(source: Path, target: Path, *, target_is_directory: bool) -> None:
    if target_is_directory:
        hardlink_tree(source, target)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
    os.link(source, target)


def hardlink_tree(source: Path, target: Path) -> None:
    source = source.resolve()
    if target.exists() or target.is_symlink():
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        dest = target / relative
        if path.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.link(path, dest)


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
