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
python3 .agents/skills/google-drive-objects/scripts/add_to_google_drive.py PATH_TO_IMAGE
```

It moves the file, refuses to overwrite an existing filename, waits for Drive for desktop to assign its cloud file ID, then prints only the direct thumbnail URL. To find or inspect images, list/search the folder and use the available image viewer on the local path. If sync does not provide an ID before timeout, report that the file was moved but its URL is pending.

## Direct Google Drive URLs

The uploader gets the cloud file ID from Drive for desktop's local metadata index; never infer an ID from a filename. The same URL formats used by `../../../data/images/images.json` are:

```text
source: https://drive.google.com/file/d/FILE_ID/view
url:    https://drive.google.com/thumbnail?id=FILE_ID&sz=w1600
```

`url` is the viewer thumbnail; `source` is the Drive file page. When editing `../../../data/images/images.json`, read `../../../rules/json-formats.md`, preserve its structure, and add only metadata supported by the user or source. Keep the image in Drive unless a repository copy is requested.
