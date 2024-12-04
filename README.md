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
- new format option: height in pixels
- automatic add sequence counter, if file already exists
- support for HEIF images
- support for video files
- if no EXIF data is found, fall back to file time stamps
- use different EXIF time stamps: DateTime, DateTimeDigitized, ...
- never rename thumbnail databases: Thumbs.db (win) and .DS_Store (Moc)
- pipx support
- bulk operations: always, never, ...
- modified default naming: incl. height

and many minor improvements, which I might not remember...
