#!/usr/bin/python3
import os
import sys
import socket
import argparse
from struct import pack

DEFAULT_PORT = 69
BLOCK_SIZE = 512
DEFAULT_TRANSFER_MODE = 'octet'

OPCODE = {'RRQ': 1, 'WRQ': 2, 'DATA': 3, 'ACK': 4, 'ERROR': 5}
ERROR_CODE = {
    0: "Not defined, see error message (if any).",
    1: "File not found.",
    2: "Access violation.",
    3: "Disk full or allocation exceeded.",
    4: "Illegal TFTP operation.",
    5: "Unknown transfer ID.",
    6: "File already exists.",
    7: "No such user."
}


def send_rrq(sock, filename, mode, server_address):
    """Send a Read Request (RRQ) to the server."""
    format = f'>h{len(filename)}sB{len(mode)}sB'
    rrq_message = pack(format, OPCODE['RRQ'], bytes(filename, 'utf-8'), 0, bytes(mode, 'utf-8'), 0)
    sock.sendto(rrq_message, server_address)


def send_wrq(sock, filename, mode, server_address):
    """Send a Write Request (WRQ) to the server."""
    format = f'>h{len(filename)}sB{len(mode)}sB'
    wrq_message = pack(format, OPCODE['WRQ'], bytes(filename, 'utf-8'), 0, bytes(mode, 'utf-8'), 0)
    sock.sendto(wrq_message, server_address)

    try:
        with open(filename, 'rb') as file:
            block_number = 1
            while True:
                file_block = file.read(BLOCK_SIZE)
                block_message = pack(f'>hh{len(file_block)}s', OPCODE['DATA'], block_number, file_block)
                sock.sendto(block_message, server_address)

                # Wait for ACK
                try:
                    ack_data, _ = sock.recvfrom(4)
                    ack_opcode = int.from_bytes(ack_data[:2], 'big')
                    ack_block = int.from_bytes(ack_data[2:4], 'big')
                    if ack_opcode == OPCODE['ACK'] and ack_block == block_number:
                        block_number += 1
                    else:
                        raise ValueError("Invalid ACK received.")
                except socket.timeout:
                    print(f"Timeout: Resending block {block_number}")
                    continue

                if len(file_block) < BLOCK_SIZE:
                    print("File upload completed.")
                    break
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        sys.exit(1)


def send_ack(sock, seq_num, server):
    """Send an ACK message to the server."""
    format = '>hh'
    ack_message = pack(format, OPCODE['ACK'], seq_num)
    sock.sendto(ack_message, server)


# Parse command line arguments
parser = argparse.ArgumentParser(description='TFTP client program')
parser.add_argument(dest="host", help="Server IP address", type=str)
parser.add_argument(dest="operation", help="get or put a file", type=str)
parser.add_argument(dest="filename", help="name of file to transfer", type=str)
parser.add_argument("-p", "--port", dest="port", type=int)
args = parser.parse_args()

server_ip = args.host
server_port = args.port if args.port else DEFAULT_PORT
server_address = (server_ip, server_port)
operation = args.operation
filename = args.filename
mode = DEFAULT_TRANSFER_MODE

# Create a UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(5)  # 5-second timeout

if operation == "get":
    # Download file from the server
    send_rrq(sock, filename, mode, server_address)
    file = open(filename, 'wb')
    expected_block_number = 1

    while True:
        try:
            data, server_new_socket = sock.recvfrom(516)
        except socket.timeout:
            print("Timeout: No response from server.")
            file.close()
            os.remove(filename)
            sys.exit(1)

        opcode = int.from_bytes(data[:2], 'big')

        if opcode == OPCODE['DATA']:
            block_number = int.from_bytes(data[2:4], 'big')
            if block_number == expected_block_number:
                send_ack(sock, block_number, server_new_socket)
                file_block = data[4:]
                file.write(file_block)
                expected_block_number += 1
            else:
                send_ack(sock, block_number, server_new_socket)

            if len(file_block) < BLOCK_SIZE:
                print("File transfer completed.")
                file.close()
                break

        elif opcode == OPCODE['ERROR']:
            error_code = int.from_bytes(data[2:4], byteorder='big')
            print(ERROR_CODE[error_code])
            file.close()
            os.remove(filename)
            break

elif operation == "put":
    # Upload file to the server
    send_wrq(sock, filename, mode, server_address)

else:
    print("Invalid operation. Use 'get' or 'put'.")
    sys.exit(1)

sys.exit(0)
