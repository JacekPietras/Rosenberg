"""Enumerate source JSON without walking the soft-deleted document collection."""

from os import walk
from pathlib import Path


def json_paths(directory, deleted_directory):
    if directory.is_relative_to(deleted_directory):
        return
    for folder, subdirectories, filenames in walk(directory):
        folder = Path(folder)
        if folder == deleted_directory.parent and deleted_directory.name in subdirectories:
            subdirectories.remove(deleted_directory.name)
        for name in filenames:
            if name.endswith('.json'):
                yield folder / name
