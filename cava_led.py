import os
import struct
import subprocess
import tempfile
import serial
import select
import fcntl
import argparse
import concurrent.futures

# things you might want to change
LEFT_PORT = "/dev/ttyACM1"
RIGHT_PORT = "/dev/ttyACM0"
SENITIVITY = 20

# Things you probably dont want to change
BARS_NUMBER = 18
OUTPUT_BIT_FORMAT = "16bit"
RAW_TARGET = "/dev/stdout"
MAGIC = [0x32, 0xAC]
serLeft = serial.Serial(LEFT_PORT, 115200, timeout=1)
serRight = serial.Serial(RIGHT_PORT, 115200, timeout=1)

# Config for CAVA
conpat = """
[general]
bars = %d
framerate = 60

[output]
method = raw
raw_target = %s
bit_format = %s

[smoothing]
monstercat = 1
"""

config = conpat % (BARS_NUMBER, RAW_TARGET, OUTPUT_BIT_FORMAT)
bytetype, bytesize, bytenorm = ("H", 2, 65535) if OUTPUT_BIT_FORMAT == "16bit" else ("B", 1, 255)

# send data to the LED matrix
def send_command(cmd_id: int, params: list = None, serialport = serLeft):
    if params is None:
        params = []
    payload = bytes(MAGIC + [cmd_id] + params)
    serialport.write(payload)

# create data from CAVA to send to LED matrix
def write_pixel_data(data: list, serialport, auto_reduce: bool = False, bar_thingy: int = 16):
    global SENITIVITY
    for col in range(0, 9):
        col_data = [0] * 34
        height = int(min(round(data[col] * SENITIVITY, 0), 17))
        if height == 17 and auto_reduce:
           SENITIVITY -= 1
        for col2 in range(bar_thingy-min(height, bar_thingy), 17+height):
            col_data[col2] = 255
        send_command(0x07, [col] + col_data, serialport)
    send_command(0x08, [], serialport)

# code run when program is closed with ctrl + c
def shutdown():
    serLeft.close()
    serRight.close()
    print("Program stopped :3")

def run():
    # get global variables (apparently this is bad practice but im lazy)
    global SENITIVITY
    # phrase arguments
    parser = argparse.ArgumentParser(description="Framework LED Matrix audio visualizer :3")
    parser.add_argument("--sensitivity", type=int, default=SENITIVITY,
                         help="Multiplier applied to bar heights")
    parser.add_argument("--no-bar", dest="bar", action="store_false",
                        help="Disable showing a bar in the center when no audio is playing")
    parser.add_argument("--reduce", action="store_true",
                        help="Reduce the sensitivity if it keeps peaking")
    args = parser.parse_args()
    # Apply arguments
    SENITIVITY = args.sensitivity
    bar_thingy = 16
    if not args.bar:
        bar_thingy = 17
    auto_reduce = args.reduce

    print(f"Running visualizer on LED matrices with senitivity at {SENITIVITY}")

    with tempfile.NamedTemporaryFile(mode='w', delete=False) as config_file:
        config_file.write(config)
        config_file_name = config_file.name

    process = subprocess.Popen(["cava", "-p", config_file_name], stdout=subprocess.PIPE)

    if RAW_TARGET != "/dev/stdout":
        if not os.path.exists(RAW_TARGET):
            os.mkfifo(RAW_TARGET)
        source_fd = os.open(RAW_TARGET, os.O_RDONLY | os.O_NONBLOCK)
    else:
        source_fd = process.stdout.fileno()
        fl = fcntl.fcntl(source_fd, fcntl.F_GETFL)
        fcntl.fcntl(source_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    chunk_size = bytesize * BARS_NUMBER
    fmt = bytetype * BARS_NUMBER
    buffer = b""
    zero_sample = [0.0] * BARS_NUMBER

    # run control of each LED matrix as a seperated thread for better performance
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

    # main loop for displaying audio
    try:
        while True:
            ready, _, _ = select.select([source_fd], [], [], 0.1)

            if ready:
                while True:
                    try:
                        data = os.read(source_fd, 4096)
                        if not data:
                            print("Cava stream ended.")
                            return
                        buffer += data
                    except BlockingIOError:
                        break
                # get latestest to avoid any issues
                if len(buffer) >= chunk_size:
                    num_frames = len(buffer) // chunk_size
                    latest_frame_start = (num_frames - 1) * chunk_size
                    latest_frame_end = num_frames * chunk_size
                    latest_frame = buffer[latest_frame_start:latest_frame_end]

                    buffer = buffer[latest_frame_end:]

                    sample = [i / bytenorm for i in struct.unpack(fmt, latest_frame)]

                    # start both processes?????
                    future_left = executor.submit(write_pixel_data, sample[0:10], serLeft, auto_reduce, bar_thingy)
                    future_right = executor.submit(write_pixel_data, sample[9:18], serRight, auto_reduce, bar_thingy)

                    # wait for both to finish
                    future_left.result()
                    future_right.result()
            else:
                future_left = executor.submit(write_pixel_data, zero_sample[0:10], serLeft, auto_reduce, bar_thingy)
                future_right = executor.submit(write_pixel_data, zero_sample[9:18], serRight, auto_reduce, bar_thingy)

                future_left.result()
                future_right.result()

    finally:
        # Clean up extra stuff
        executor.shutdown(wait=False)
        process.terminate()
        if os.path.exists(config_file_name):
            os.remove(config_file_name)

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        pass
    finally:
        shutdown()
