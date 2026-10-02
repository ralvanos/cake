# Privacy

cake runs on your machine. A scan does not upload source code, send telemetry, or call an AI model.

## What a scan reads

`cake` walks the directory you name and reads source files so it can count lines. It also reads file size and skips files it will not count.

It does not print file contents. The report shows totals by language, hours, and money.

Directories such as `.git`, `node_modules`, virtualenvs, and build outputs are not entered. Lockfiles and minified bundles are skipped. Hidden files that cake does not recognize as source are skipped. Signing files such as `.keystore` and `.jks` are skipped and their contents are not read.

An unrecognized file is counted by its suffix only. Cake does not open it and does not print its name beyond that suffix, such as `.properties (3)`.

## What a scan writes

A scan does not create, edit, rename, or delete files in the tree. It does not set timestamps.

Reading a file can update its last-access time when the operating system records access. cake does not ask for that update, and it never sets created, accessed, or modified times. A read does not change the modified time, which is the last time the file was written.

Windows often has last-access updates disabled. Linux often mounts disks with `relatime` or `noatime`, which limits those updates. If access times are turned on, a scan can change the access time only.

`cake init` writes a new `cake.toml` in the directory you name. `cake init --user` writes one personal settings file: `%APPDATA%\cake\cake.toml` on Windows, and `~/.config/cake/cake.toml` on Linux and macOS. Both refuse to overwrite an existing file. Those files hold rates and subscription amounts you type in. They are not sent anywhere.

## What leaves the machine

Nothing from a scan. There is no account, no network API, and no analytics in this program. The email address and GitHub link in the help text are printed for you to read. Cake does not contact them.

Installing cake with pip downloads Python packages from the Python package index. That is the installer, not a scan. After that, `cake` itself does not open a network connection.

## What cake does not store

Cake has no database and does not save a quote, a file list, or a scan history. Because nothing is stored and nothing is sent, there is no encrypted store and no encrypted upload.

## Settings

A project `cake.toml`, and the personal settings file from `cake init --user`, can contain your hourly rate, salary figure, and subscription prices. They are plain text so you can edit them. Cake reads them on your machine and does not copy them anywhere.

This repository's `.gitignore` excludes `cake.toml`, virtual environments, and common credential files. `cake.toml.example` is a template with the built-in numbers, and it is safe to publish. Keep a filled-in `cake.toml` out of a public upload when those numbers are private.

`--json` prints the same quote to your terminal. It is still local.
