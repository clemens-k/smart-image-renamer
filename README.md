# Prerequisites

- python >=3.11
- poetry >=1.8

# Building

    poetry build

should create `sdist` and `wheel` in `dist` folder

# Pipx installation from local folder

    pipx install .

# Differences to forked repo

Added:
- support for HEIF images
- support for video files
- if no EXIF data is found, fall back to file time stamps
- never rename thumbnail databases: Thumbs.db (win) and .DS_Store (Moc)
- pipx support
- bulk operations: always, never, ...
- modified default naming

and many minor improvements, which I might not remember...
