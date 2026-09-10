# framework led matrix audio visualizer

Uses CAVA to visualize audio onto the LED matrices on your framework laptop.

This works on linux with 2 LED matrices but it wont work on windows and I havent testing it with using only one LED matrix.

## Installation 
Both cava and pyserial are required for it to work

Install pyserial via pip or your package manager (eg pacman, apt, dnf, etc)

Install cava via your package manager

After that running it should just work. If the matrices are wrong, try using the --left and --right flags.


## arguments
-  -h, --help                 show the help message
-  --sensitivity SENSITIVITY  Multiplier applied to bar heights
-  --bar                      enable showing a bar in the center when no audio is playing
-  --reduce                   Reduce the sensitivity if it keeps peaking
-  --mono                     Show one visualizer for left and right instead
-  --smooth                   Use monstercat smoothing on bars
-  --debug                    enable debug logging
-  --hollow                   Make it hollow
-  --location LOCATION        Where it starts, 0 = bottom, 1 = middle, 2 = top
-  --brightness BRIGHTNESS    brightness of the leds 1-255         
-  --right RIGHT              Serial port for the right led matrix
-  --left LEFT                Serial port for the left led matrix
