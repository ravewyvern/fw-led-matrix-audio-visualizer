import os
import struct
import subprocess
import tempfile
import serial
import select
import fcntl
import argparse
import concurrent.futures


# send data to the LED matrix
def send_command(cmd_id: int, params: list, serialport):
    if params is None:
        params = []
    payload = bytes(MAGIC + [cmd_id] + params)
    serialport.write(payload)

def merge_data(data: list, data2: list):
    output = [0] * 9
    data2.reverse()
    for num, datapoint in enumerate(data):
        top2 = max(data[num], data2[num])
        output[num] = top2
    return output

# kill the program without problems
def shutdown():
    serLeft.close()
    serRight.close()
    print("Program stopped :3")

def log(message):
    if DEBUG_MODE:
        print(message)

def write_pixel_data(data: list, serialport):
    global SENSITIVITY
    if LOCATION == 0 or LOCATION == 2:
        max_height = 34
    else:
        max_height = 17
    # Create each column data
    for col in range(0, 9):
        col_data = [0] * 34

        # calculate range
        height = int(min(round(data[col] * SENSITIVITY, 0), max_height))
        if height == max_height and ENABLE_REDUCE:
            SENSITIVITY -= 1
        if LOCATION == 0:
            top = min(34-height, 34-ENABLE_BAR)
            bottom = 34
            middle = 33
            log(f"LOCATION={LOCATION}, top={top}, middle={middle}, bottom={bottom}")
        elif LOCATION == 1:
            top = 17 - ENABLE_BAR - min(height, 17-ENABLE_BAR)
            bottom = 17+height
            middle = 16
            log(f"LOCATION={LOCATION}, top={top}, middle={middle}, bottom={bottom}")
        elif LOCATION == 2:
            top = 0
            bottom = max(0+height, 0+ENABLE_BAR)
            middle = 0
            log(f"LOCATION={LOCATION}, top={top}, middle={middle}, bottom={bottom}")
        else:
            log("Error: Location unknown")

        if ENABLE_HOLLOW:
            for col2 in range(0, 34):
                if col2 == top-1 or col2 == bottom or (col2 == middle and ENABLE_BAR):
                    col_data[col2] = BRIGHTNESS
        else:
            for col2 in range(top, bottom):
                col_data[col2] = BRIGHTNESS
        send_command(0x07, [col] + col_data, serialport)
        # log(f"Writing data to serial {serialport}, coldata={col_data}")
    send_command(0x08, [], serialport)

def run():
    print(f"Running visualizer on LED matrices with senitivity at {SENSITIVITY}")
    log(f"Intialized serial ports: left={serLeft}, right={serRight}, BRIGHTNESS={BRIGHTNESS}")

    # Code I stole from github so idk what it does lol
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
                    log(f"Writing data for bars {BARS_NUMBER}")
                    if BARS_NUMBER == 36:
                        future_left = executor.submit(write_pixel_data, merge_data(sample[0:9], sample[27:36]), serLeft)
                        future_right = executor.submit(write_pixel_data, merge_data(sample[9:18], sample[18:27]), serRight)
                    else:
                        future_left = executor.submit(write_pixel_data, sample[0:9], serLeft)
                        future_right = executor.submit(write_pixel_data, sample[9:18], serRight)

                    # wait for both to finish
                    future_left.result()
                    future_right.result()
            else:
                future_left = executor.submit(write_pixel_data, zero_sample[0:9], serLeft)
                future_right = executor.submit(write_pixel_data, zero_sample[9:18], serRight)

                future_left.result()
                future_right.result()

    finally:
        # Clean up extra stuff
        executor.shutdown(wait=False)
        process.terminate()
        if os.path.exists(config_file_name):
            os.remove(config_file_name)

if __name__ == "__main__":

    # Phrase all arguments
    parser = argparse.ArgumentParser(description="Framework LED Matrix audio visualizer :3")
    parser.add_argument("--sensitivity", type=int, default=20,
                         help="Multiplier applied to bar heights")
    parser.add_argument("--bar", dest="bar", action="store_true",
                        help="Disable showing a bar in the center when no audio is playing")
    parser.add_argument("--reduce", action="store_true",
                        help="Reduce the sensitivity if it keeps peaking")
    parser.add_argument("--mono", action="store_true",
                        help="Show one visualizer for left and right instead")
    parser.add_argument("--smooth", action="store_true",
                        help="Use monstercat smoothing on bars")
    parser.add_argument("--debug", action="store_true",
                        help="enable debug logging")
    parser.add_argument("--hollow", action="store_true",
                        help="Make it hollow")
    parser.add_argument("--location", type=int, default=1,
                        help="Where it starts, 0 = bottom, 1 = middle, 2 = top")
    parser.add_argument("--brightness", type=int, default=255,
                        help="brightness of the leds 1-255")
    parser.add_argument("--right", type=str, default="/dev/ttyACM0",
                        help="Serial port for the right led matrix")
    parser.add_argument("--left", type=str, default="/dev/ttyACM1",
                        help="Serial port for the left led matrix")
    args = parser.parse_args()

    # Make args useable again (MAUA)
    SENSITIVITY = args.sensitivity
    if args.bar:
        ENABLE_BAR = 1
    else:
        ENABLE_BAR = 0
    ENABLE_REDUCE = args.reduce
    ENABLE_HOLLOW = args.hollow
    DEBUG_MODE = args.debug
    if args.mono:
        BARS_NUMBER = 36
    else:
        BARS_NUMBER = 18
    if args.smooth:
        ENABLE_SMOOTH = 1
    else:
        ENABLE_SMOOTH = 0
    LOCATION = min(max(args.location, 0), 2)
    BRIGHTNESS = min(max(args.brightness, 1), 255)
    LEFT_PORT = args.left
    RIGHT_PORT = args.right

    # random stuff you shouldnt touch
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
    monstercat = %s
    """

    config = conpat % (BARS_NUMBER, RAW_TARGET, OUTPUT_BIT_FORMAT, ENABLE_SMOOTH)
    bytetype, bytesize, bytenorm = ("H", 2, 65535) if OUTPUT_BIT_FORMAT == "16bit" else ("B", 1, 255)

    # run the main program
    try:
        run()
    except KeyboardInterrupt:
        pass
    finally:
        shutdown()
