# cake

cake scans a source tree and prints what to charge. **Time and materials** is the hourly-contract number: shorter AI hours, a warranty, and your AI subscriptions. The per-hour figure under that column is the all-in rate. The rate in the header is labor only. The **recommended bid** is the fixed price. A comparison table puts that bid next to a traditional staffed project and a solo developer with no AI tools.

Scans stay on your machine. Cake keeps no database and sends nothing out. Details are in [PRIVACY.md](PRIVACY.md). The license is [MIT](LICENSE), copyright ralvanos.

## Install

Python 3.11 or newer. The same program runs on Windows, Linux, and macOS.

Windows, from this folder:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\python -m cake examples/sample
```

Linux and macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m cake examples/sample
```

`python -m cake` is the command to use in the examples below. On Windows that is `.\.venv\Scripts\python`. On Linux and macOS it is `.venv/bin/python`. After install, the `cake` command itself is `.venv\Scripts\cake` or `.venv/bin/cake`.

## Use

Quote the sample, then another tree. A path is required. With no path, cake prints an error and the help. Pass `.` when you mean the current directory. Forward slashes work on Windows too. A Linux path looks like `/home/me/app`. A Windows path looks like `E:\Projects\app`.

```text
python -m cake examples/sample
python -m cake examples/sample --preset vibe --rate 175
python -m cake examples/sample --hours 80 --weeks 4
python -m cake /home/me/app
```

You can run a scan with no settings file. The built-in rate is $150 an hour.

To use your own rate on every scan, write one personal file. This does not edit source:

```text
python -m cake init --user
```

That file lives in your user settings, not in the cake program folder:

| System | File |
| --- | --- |
| Windows | `%APPDATA%\cake\cake.toml` |
| Linux and macOS | `~/.config/cake/cake.toml` |

A project that needs its own rate gets a file beside that project:

```text
python -m cake init
```

Help and version:

```text
python -m cake help
python -m cake --help
python -m cake --version
```

## How to read the result

Send the **recommended bid** when the price is fixed. Use the **time-and-materials total** when the contract is hourly. Those hours already use the AI speed preset, so the time is the shorter figure. The per-hour cell is labor plus warranty plus subscriptions. It is not a second, lower labor rate.

The comparison table has four columns:

| Column | What it is |
| --- | --- |
| Traditional | Staffed lifecycle. Basic COCOMO, the same shape as sloccount. Hours × your rate, plus a toolchain. No extra warranty. |
| Solo, no AI | One person at 15 finished lines an hour. Same toolchain. Warranty included. |
| AI pair | Daily agent pairing, 2.5×. AI subscriptions instead of the toolchain. This is the default quote. |
| AI vibe | Agents draft most of the code, 4×. |

Below 1,000 billable lines the traditional column is marked rough. Below 10,000 billable lines it says this is a large-project formula and runs high. The model was fit to larger systems.

`pair` keeps half the labor gap between solo and AI. The client gets the other half. Change that with `--keep`.

## Options

`cake help` prints the same list.

| Option | Meaning | Default |
| --- | --- | --- |
| `path` | File or directory to scan. Required. `.` scans the current directory. `help` prints help. `init` writes a project `cake.toml`. | |
| `--init` | Write `cake.toml` and exit. With `--user`, write the personal file. | |
| `--user` | With `init`, write the personal settings file. | |
| `--rate` | Hourly rate you charge. | `150` |
| `--hours-per-week` | Focused hours in a week. | `30` |
| `--preset` | `classic` (1×), `review` (1.6×), `pair` (2.5×), `vibe` (4×). | `pair` |
| `--keep` | Share of the AI labor savings kept on the fixed bid, from 0 to 1. | `0.5` |
| `--warranty` | Fraction added on bid labor for leftover fixes. | `0.15` |
| `--sloc-per-hour` | Finished lines per unassisted focused hour. | `15` |
| `--hours` | Use these hours on the invoice instead of the line estimate. | |
| `--weeks` | Calendar weeks for subscriptions and the weekly rate. | |
| `--currency` | `USD`, `EUR`, `GBP`, `CAD`, or `AUD`. | `USD` |
| `--sub NAME=MONTHLY` | Add or replace a monthly AI subscription. Repeatable. | |
| `--no-subs` | Drop AI subscriptions from the quote. | |
| `--salary` | Annual salary for the employer loaded cost in the comparison. | `140000` |
| `--overhead` | Multiplier on that salary. | `2.4` |
| `--toolchain` | Traditional toolchain, per person per month, comparison only. | `24` |
| `--config PATH` | Use this file and skip the project file and the personal file. | |
| `--no-config` | Ignore the project file and the personal file. | |
| `--max-bytes` | Skip files larger than this. | `1000000` |
| `--json` | Print JSON. | |
| `--explain` | Print why the numbers came out this way. | |
| `--plain` | Print without color. | |
| `--version` | Print the version. | |

## Settings

A scan needs no settings file. With none present, cake uses the built-in numbers: $150 an hour, the `pair` preset, and the two $20 subscriptions.

When files are present, later steps replace earlier ones:

1. Built-in numbers.
2. Your personal file, if you created it with `cake init --user`.
3. The nearest `cake.toml`, walking up from the folder you scan.
4. Flags such as `--rate`.

A project file overrides one setting at a time. If that file includes `[subscriptions]` or `[weights]`, that whole table replaces the personal one. `--config` reads only the file you name. `--no-config` stays on the built-in numbers.

`cake.toml.example` is the same text `init` writes, with the built-in numbers, and it is meant to be published. A filled-in `cake.toml` can hold your rate and salary. This repository ignores that file, along with virtual environments and common credential files, so a manual GitHub upload made with git does not include them. Putting a `cake.toml` in the cake program folder does not change scans of other projects.

```toml
[rates]
hourly = 150
hours_per_week = 30

[model]
sloc_per_hour = 15
preset = "pair"
keep_savings = 0.5
warranty = 0.15

[subscriptions]
"Cursor Pro" = 20
"Claude Pro" = 20
# "API usage" = 40

[traditional]
toolchain_monthly = 24

# [weights]
# Markdown = 0
# ".properties" = 0.05
```

A name such as `Markdown` changes that language. A suffix such as `".properties"` prices files cake does not already know. `#` lines in those files count as comments. The source table lists unrecognized suffixes, such as `.properties (3)`. Signing files such as `.keystore` are skipped with other binaries.

The subscription prices and the `$24` toolchain are planning defaults, not live vendor prices. Edit them to the bills you pay. Meetings, design, hosting, and hardware are outside the quote. Add them with `--hours` or `--rate` when the engagement includes them.

## Tests

Windows:

```powershell
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\pytest
```

Linux and macOS:

```bash
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/pytest
```

## Feedback & Support

Written by [ralvanos](https://github.com/ralvanos). Questions, ideas, or bug reports are welcome.

- **Email**: [ralvanos@protonmail.com](mailto:ralvanos@protonmail.com)
- **Contribute**: [github.com/ralvanos/cake](https://github.com/ralvanos/cake)

### Support the project

cake is free. Donations are voluntary.

#### Voluntary donations

- **Bitcoin**: `bc1qm0pwaxjyd809v7d606duklmcujn9sygnkgyunx`
- **Monero**: `82sVJnuXRSRGv8RnZGPhpQYssmSAQXT8aXu81CB9iifMB73HKmuMcGNWxmV5s8ELUoaHtJeY13akB7m5f6DMjCDW1mFjtKV`
