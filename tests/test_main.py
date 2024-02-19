"""Test cases for the __main__ module."""
import pytest
from click.testing import CliRunner

from epomakercontroller import __main__
from epomakercontroller.epomakercontroller import EpomakerController
from epomakercontroller.data.command_data import image_data_prefix
from epomakercontroller.commands import EpomakerImageCommand, IMAGE_DIMENSIONS
import random
import numpy as np
import matplotlib.pyplot as plt
import cv2
import math

@pytest.fixture
def runner() -> CliRunner:
    """Fixture for invoking command-line interfaces."""
    return CliRunner()


def test_main_succeeds(runner: CliRunner) -> None:
    """It exits with a status code of zero."""
    result = runner.invoke(__main__.main)
    assert result.exit_code == 0


def assert_colour_close(original: tuple[int, int, int], decoded: tuple[int, int, int], delta: int = 8,
                        debug_str: str = "") -> None:
    """Asserts that two colors are within an acceptable delta of each other.
    This is necessary because the RGB565 encoding and decoding process is lossy.
    """
    for o, d in zip(original, decoded):
        assert abs(o - d) <= delta, f"{debug_str} Original: {original}, Decoded: {decoded}, Delta: {delta}"


def test_encode_decode_rgb565() -> None:
    """Test the _encode_rgb565 and _decode_rgb565 functions."""
    # Test data
    rgb = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

    # Encode and decode
    encoded = EpomakerImageCommand._encode_rgb565(*rgb)
    decoded = EpomakerImageCommand._decode_rgb565(encoded)

    assert_colour_close(rgb, decoded)


def test_read_and_decode_bytes() -> None:
    """Test reading bytes from a text file and decoding them."""
    # Test data
    # file_path = "tests/data/upload-calibration-image-bytes.txt"
    file_path = "/home/sam/Documents/keyboard-usb-sniff/EpomakerController/EpomakerController/image_data.txt"

    # Read bytes from file
    with open(file_path, "r") as file:
        hex_data_full = file.readlines()

    # Parse the hex data assuming a 2-byte color encoding (16 bits per pixel)
    pixels = []
    for line in hex_data_full:
        # Each pair of values now represents one pixel
        if ":" in line:
            pixel_values = line.strip().split(':')
        else:
            pixel_values = [line[i:i+2] for i in range(0, len(line), 2)]
        for i in range(0, len(pixel_values), 2):
            try:
                # Convert every 2 values into a single integer representing a pixel
                pixel = int("".join(pixel_values[i:i+2]), 16)
                pixels.append(pixel)
            except ValueError:
                # In case of incomplete values, we break the loop
                break

    shape = IMAGE_DIMENSIONS
    num_pixels = shape[0] * shape[1]
    image_data = pixels[:num_pixels]  # Ensure we only take the number of pixels we need
    image_array_16bit = np.array(image_data, dtype=np.uint16).reshape(shape)

    rgb_array_decoded = np.array(
        [EpomakerImageCommand._decode_rgb565(pixel) for pixel in image_array_16bit.ravel()],
        dtype=np.uint8
        )
    rgb_image = rgb_array_decoded.reshape((shape[0], shape[1], 3))

    # Display the RGB image
    # plt.imshow(rgb_image)
    # plt.axis('off')  # Hide the axes
    # plt.show()
    # TODO: Assertions
    # assert isinstance(decoded_text, str)
    # assert len(decoded_text) > 0
    # assert decoded_text.startswith("Hello")
    # assert decoded_text.endswith("world!")


def test_encode_image() -> None:
    image_path = "tests/data/calibration.png"
    image = cv2.imread(image_path)
    image = cv2.resize(image, IMAGE_DIMENSIONS)
    image = cv2.flip(image, 0)
    image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)

    image_16bit = np.zeros((IMAGE_DIMENSIONS[0], IMAGE_DIMENSIONS[1]), dtype=np.uint16)
    try:
        for y in range(image.shape[0]):
            for x in range(image.shape[1]):
                r, g, b = image[y, x]
                image_16bit[y, x] = EpomakerImageCommand._encode_rgb565(r, g, b)
    except Exception as e:
        print(f"Exception while converting image: {e}")

    image_data = ""
    for row in image_16bit:
        image_data += ''.join([hex(val)[2:].zfill(4) for val in row])

    # 4 bytes per pixel (16 bits)
    assert len(image_data) == (IMAGE_DIMENSIONS[0] * IMAGE_DIMENSIONS[1]) * 4
    buffer_length = 128 - len(image_data_prefix[0])
    with open("image_data.txt", "w", encoding="utf-8") as file:
        chunks = math.floor(len(image_data) / buffer_length)
        i = 0
        while i < chunks:
            image_byte_segment = image_data[i*buffer_length:(i+1)*buffer_length]
            file.write(f"{image_byte_segment}\n")
            i += 1
        # Remainder of the data
        image_byte_segment = EpomakerController._pad_command(
            image_data[i*buffer_length:], buffer_length
            )
        file.write(f"{image_byte_segment}\n")
    # TODO: Assertions

# def test_send_imagfe() -> None:
#     controller = EpomakerController()
#     controller.send_image("/home/sam/Documents/keyboard-usb-sniff/EpomakerController/EpomakerController/tests/data/calibration.png")
#     pass

def byte_wise_difference(bytes1: bytes, bytes2: bytes) -> list[int]:
    # Ensure the bytes objects are of the same length
    if len(bytes1) != len(bytes2):
        raise ValueError("Bytes objects must be of the same length")

    # Calculate the byte-wise difference
    differences = [abs(b1 - b2) for b1, b2 in zip(bytes1, bytes2)]

    return differences

def test_encode_image_command() -> None:
    command = EpomakerImageCommand()
    command.encode_image("/home/sam/Documents/keyboard-usb-sniff/EpomakerController/EpomakerController/tests/data/calibration.png")
    with open("/home/sam/Documents/keyboard-usb-sniff/EpomakerController/EpomakerController/tests/data/calibration-image-command.txt", "r") as file:
        for i, p in enumerate(command):
            test_bytes = bytes.fromhex(file.readline().strip())
            difference = byte_wise_difference(p, test_bytes)

            # Headers should always be equal
            test_bytes[:command.packet_header_length] == p[:command.packet_header_length]

            # Colours should be within an acceptable difference
            byte_pairs = [p[i:i+2] for i in range(0, len(p), 2)]
            byte_pairs_test = [test_bytes[i:i+2] for i in range(0, len(test_bytes), 2)]

            # Iterate over byte pairs and assert the color difference
            j = 0
            for pair, test_pair in zip(byte_pairs, byte_pairs_test):
                # Convert byte pair to integer
                colour = int.from_bytes(pair)
                colour_test = int.from_bytes(test_pair)

                # Assert the colour difference
                assert_colour_close(
                    EpomakerImageCommand._decode_rgb565(colour),
                    EpomakerImageCommand._decode_rgb565(colour_test),
                    debug_str=f"Packet {i}, Pair {j} "
                    )

                j += 1

            assert np.all(np.array(difference) <= 8)


def calculate_checksum(buffer: bytes, checkbit: int) -> bytes:
    sum_bits = 0
    for byte in buffer:
        sum_bits += byte
    if sum_bits == 0:
        return bytes(0)
    # Only use the lower 8 bits
    checksum = 0xff - sum_bits.to_bytes(2)[1]
    return checksum.to_bytes()


def test_checksum() -> None:
    checkbit = 8
    commands = []
    test_file = "/home/sam/Documents/keyboard-usb-sniff/EpomakerController/EpomakerController/tests/data/cycle-light-modes-command.txt"
    with open(test_file, "r", encoding="utf-8") as file:
        commands = file.readlines()
    for i, command in enumerate(commands):
        buffer = bytes.fromhex(command.strip())
        checksum = calculate_checksum(buffer[:checkbit], checkbit)
        assert checksum == buffer[checkbit].to_bytes(), f"{i} > Checksum: {checksum!r}, Buffer: {hex(buffer[checkbit])}"

    checkbit = 7
    commands = []
    test_files = [
        "/home/sam/Documents/keyboard-usb-sniff/EpomakerController/EpomakerController/tests/data/calibration-image-command.txt",
        "/home/sam/Documents/keyboard-usb-sniff/EpomakerController/EpomakerController/tests/data/all-keys-to-100-5-69-command.txt",
        "/home/sam/Documents/keyboard-usb-sniff/EpomakerController/EpomakerController/tests/data/change-A-blue-x4-red-x4-command.txt",
        "/home/sam/Documents/keyboard-usb-sniff/EpomakerController/EpomakerController/tests/data/change-all-key-unique-rgb-command.txt"
    ]
    for test_file in test_files:
        with open(test_file, "r", encoding="utf-8") as file:
            commands = file.readlines()
        for i, command in enumerate(commands):
            buffer = bytes.fromhex(command.strip())
            checksum = calculate_checksum(buffer[:checkbit], checkbit)
            assert checksum == buffer[checkbit].to_bytes(), f"{i} > Checksum: {checksum!r}, Buffer: {hex(buffer[checkbit])}"
