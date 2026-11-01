# Reference investigation

These references informed the minimal redesign. The new printable meshes are
original geometry; no third-party CAD was incorporated.

## Rii K06 Keyboard Case — U0064695548

Source: https://www.nexprint.com/en/models/G5141615

Downloaded and inspected the author's two build photographs:

- [Open assembly](rii-k06-open.jpg)
- [Phone installed](rii-k06-installed.jpg)

Photo credit: **U0064695548**, RiiK06 Keyboard Case, Nexprint. The listing declares
[Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
The reference photos are unmodified. They are not pictures of our design.

The photographs show a shallow keyboard surround, a thin magnetic phone plate,
and a small rear pivot. This supports using device-specific depths and small
round knuckles rather than the original tall flat-bottom hinge blocks. The
author notes that the keyboard cutouts are imperfect and recommends tree
supports. We adopted the compact hinge principle and local support requirement;
our phone mounting remains a rigid open frame with removable adhesive pads.
No dimensions were inferred from photo pixels.

The public listing identifies a 2.09 MB 3MF, but its downloadable file URL is
absent from the public page data. We did not download or measure that CAD file.

## TypingCat pocket cyberdeck

Creator's build discussion:
https://www.reddit.com/r/cyberDeck/comments/1hrmc41/

Universal version discussion:
https://www.reddit.com/r/cyberDeck/comments/1iggtca/

Models:
https://www.thingiverse.com/thing:6897933
https://www.thingiverse.com/thing:6897994

The creator describes a three-part chassis around a Pixel 6 Pro and a different
keyboard, with a flush closure. The universal version uses magnetic mounting and
discusses friction hinges. The useful principle is keeping the mounting structure
close to the device rather than adding a deep generic box. This is a different
keyboard and phone, so it is not a drop-in alternative for our hardware.

Thingiverse returned HTTP 403 when attempting to download the public model page;
the 3dgo mirror also returned 403. No mesh measurements or licence assumptions
are made for these models.

## Mobile C-deck — Sergiy

Primary project: https://hackaday.io/project/203116-mobile-c-deck

Download listing linked by the project:
https://www.printables.com/model/1355982-modular-c-deck-clamshell-palmtop

Reviewed the project description and component list. It uses replaceable phone
inserts, a different keyboard and additional hardware. Its modular insert is
useful for changing phones, but adds structure compared with a frame sized for
one bare iPhone. The linked Printables page could not be fetched, so its meshes
were not downloaded or measured.

## Changes resulting from the investigation

| Feature | First version | Minimal version |
| --- | --- | --- |
| Printed closed envelope | 157 × 101.4 × 29.8 mm | 155 × 82.3 × 22.8 mm |
| Hinge | Tall rectangular blocks | 6.4 mm diameter round barrels |
| Pin | 3 mm | 2 mm |
| Phone seat | Raised for camera clearance | 1.2 mm frame with camera opening |
| Back | Mostly solid | Perimeter rails and adhesive mounting ribs |
| Keyboard footprint | Padded to phone depth | Sized to keyboard, aligned at hinge |
| Support | Flat-bottom hinge | Local support beneath barrel undersides |
| Solid mesh volume, both parts | 156,811.5 mm³ | 21,907.0 mm³ |

The volume comparison uses the first committed version, before its camera
opening, and the current generated solids. It is not a measured filament saving
or slicer estimate. The thin frame exposes the camera bump, so the assembled
device can exceed the printed envelope. Reference access and inspection were
performed during this redesign; the third-party models were not print-tested.
