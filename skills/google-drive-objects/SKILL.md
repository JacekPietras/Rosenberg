---
name: google-drive-objects
description: Upload, find, inspect, or create viewer URLs for images in this project's Google Drive objects folder.
metadata:
  short-description: Manage project Google Drive objects
---

# Google Drive objects

The local synced folder is `/Users/jpietras/GoogleDrivePrivate/[Rycerskie]/Boxberg/objects`.

## Upload or read

Upload from the project root with:

```text
python3 scripts/add_to_google_drive.py PATH_TO_IMAGE
```

It moves the file and refuses to overwrite an existing filename. To find or inspect images, list/search the folder and use the available image viewer on the local path. If the folder is unavailable or a move fails, report that; a successful local move alone does not confirm cloud sync.

## Direct Google Drive URLs

For `data/images/images.json`, get the Drive ID from its share link (`Copy link`). A local path does not reveal the ID; never guess it. For `FILE_ID`, use:

```text
source: https://drive.google.com/file/d/FILE_ID/view
url:    https://drive.google.com/thumbnail?id=FILE_ID&sz=w1600
```

`url` is the viewer thumbnail; `source` is the Drive file page. If the ID is unavailable, ask for the share link. Confirm the image's sharing permissions permit the intended viewer access. When editing `data/images/images.json`, read `rules/json-formats.md`, preserve its structure, and add only metadata supported by the user or source. Keep the image in Drive unless a repository copy is requested.
