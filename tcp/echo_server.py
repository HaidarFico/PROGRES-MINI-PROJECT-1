import socket
import select

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 9000
BUFFER_SIZE = 1024

def run_echo_server():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((SERVER_HOST, SERVER_PORT))
    server_sock.listen()
    server_sock.setblocking(False)

    print(f"[#] Server is listening on ({SERVER_HOST}, {SERVER_PORT})")

    inputs = [server_sock]
    client_map = {}

    try:
        while True:
            readable, _, exceptional = select.select(inputs, [], inputs)
            for sock in readable:
                if sock is server_sock:
                    client_sock, client_addr = server_sock.accept()
                    client_sock.setblocking(False)
                    inputs.append(client_sock)
                    client_map[client_sock] = client_addr
                    print(f"[#] Client connected: {client_addr}")
                else:
                    data = sock.recv(BUFFER_SIZE)
                    if data:
                        response = b"Echo: " + data
                        sock.sendall(response)
                        print(f"[#] Echoed to {client_map[sock]}: {data.decode().strip()}")
                    else:
                        print(f"[#] Client disconnected: {client_map[sock]}")
                        inputs.remove(sock)
                        del client_map[sock]
                        sock.close()

            for sock in exceptional:
                inputs.remove(sock)
                if sock in client_map:
                    del client_map[sock]
                sock.close()
    except KeyboardInterrupt:
        print("[#] Server is shutting down...")
    finally:
        for sock in inputs:
            sock.close()

if __name__ == "__main__":
    run_echo_server()