#!/usr/bin/python3
'''
$ mytftp host_address [-p port_number] <get|put> filename
'''
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

def send_rrq(sock, server_address, filename, mode):
    format = f'>h{len(filename)}sB{len(mode)}sB'
    rrq_message = pack(format, OPCODE['RRQ'], bytes(filename, 'utf-8'), 0, bytes(mode, 'utf-8'), 0)
    sock.sendto(rrq_message, server_address)

def send_wrq(sock, server_address, filename, mode):
    format = f'>h{len(filename)}sB{len(mode)}sB'
    wrq_message = pack(format, OPCODE['WRQ'], bytes(filename, 'utf-8'), 0, bytes(mode, 'utf-8'), 0)
    sock.sendto(wrq_message, server_address)

def send_ack(sock, seq_num, server):
    format = f'>hh'
    ack_message = pack(format, OPCODE['ACK'], seq_num)
    sock.sendto(ack_message, server)

# Parse command line arguments
parser = argparse.ArgumentParser(description='TFTP client program')
parser.add_argument(dest="host", help="Server IP address", type=str)
parser.add_argument(dest="operation", help="get or put a file", type=str, choices=['get', 'put'])
parser.add_argument(dest="filename", help="name of file to transfer", type=str)
parser.add_argument("-p", "--port", dest="port", type=int, default=DEFAULT_PORT)
args = parser.parse_args()

server_ip = args.host
server_port = args.port
server_address = (server_ip, server_port)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(5)  # Set a timeout of 5 seconds

mode = DEFAULT_TRANSFER_MODE
operation = args.operation
filename = args.filename

if operation == 'get':
    send_rrq(sock, server_address, filename, mode)
    with open(filename, 'wb') as file:
        expected_block_number = 1

        while True:
            try:
                data, server_new_socket = sock.recvfrom(516)
                opcode = int.from_bytes(data[:2], 'big')

                if opcode == OPCODE['DATA']:
                    block_number = int.from_bytes(data[2:4], 'big')
                    if block_number == expected_block_number:
                        send_ack(sock, block_number, server_new_socket)
                        file_block = data[4:]
                        file.write(file_block)
                        expected_block_number += 1
                    else:
                        send_ack(sock, block_number, server_new_socket)  # Re-send ACK for duplicate blocks

                    if len(file_block) < BLOCK_SIZE:
                        print("File transfer completed.")
                        break

                elif opcode == OPCODE['ERROR']:
                    error_code = int.from_bytes(data[2:4], byteorder='big')
                    print(ERROR_CODE[error_code])
                    break

            except socket.timeout:
                print("Timeout occurred. Retrying...")
                send_rrq(sock, server_address, filename, mode)  # Re-send RRQ

elif operation == 'put':
    send_wrq(sock, server_address, filename, mode)
    try:
        with open(filename, 'rb') as file:
            block_number = 1

            while True:
                block = file.read(BLOCK_SIZE)
                if not block:
                    break
                data_packet = pack(f'>hh{len(block)}s', OPCODE['DATA'], block_number, block)
                sock.sendto(data_packet, server_address)

                try:
                    ack, server_new_socket = sock.recvfrom(516)
                    opcode = int.from_bytes(ack[:2], 'big')

                    if opcode == OPCODE['ACK'] and int.from_bytes(ack[2:4], 'big') == block_number:
                        block_number += 1
                    else:
                        print("Invalid ACK received. Retrying...")

                except socket.timeout:
                    print("Timeout occurred. Retrying block", block_number)
                    sock.sendto(data_packet, server_address)  # Re-send current block

        print("File upload completed.")

    except FileNotFoundError:
        print("File not found.")

sock.close()
sys.exit(0)
