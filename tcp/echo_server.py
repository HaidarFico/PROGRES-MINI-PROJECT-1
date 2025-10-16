import socket
import sys


SERVER_HOST = '127.0.0.1'
SERVER_PORT = 9000

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((SERVER_HOST, SERVER_PORT))
    s.listen()
    print(f"[#] The server is listenning on ({SERVER_HOST}, {SERVER_PORT})")
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    conn, addr = s.accept()
    with conn as c:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            conn.sendall(b'Echo: ' + data)
            print(f"[#] Echoed data {data.decode().strip()}")

