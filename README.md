# framework led matrix audio visualizer

shows cool stuff on your LED matrices 
I tested it on linux but it likely doesnt work on windows

## Installation 
Both cava and pyserial are required for it to work

Install pyserial
```bash
pip install pyserial
```
Note: you might have to create a virtual environment

Install cava via your package manager (eg pacman, apt, dnf, etc)

and everything should work once you run it

## arguments

- --no-bar: removes the bar in the center when no music is playing
- --sensitivity: adjusts the sensitivity (how big the bars are)
- --reduce: automatically reduce the sensitivity if it peaks
