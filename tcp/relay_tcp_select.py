import socket
import select
import argparse

BUFFER_SIZE = 4096

socket_map = {}

def close_relay(sock):
    peer = socket_map.pop(sock, None)
    if peer:
        socket_map.pop(peer, None)
        peer.close()
    sock.close()

def accept_client(listen_sock, remote_host, remote_port, inputs):
    try:
        client_sock, client_addr = listen_sock.accept()
        client_sock.setblocking(False)

        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.connect((remote_host, remote_port))
        server_sock.setblocking(False)

        inputs.extend([client_sock, server_sock])
        socket_map[client_sock] = server_sock
        socket_map[server_sock] = client_sock

        print(f"[#] Relay: {client_addr} <-> {remote_host}:{remote_port}")
    except Exception as e:
        print(f"[ERROR] Failed to accept client: {e}")

def data_transfer(sock, inputs):
    try:
        data = sock.recv(BUFFER_SIZE)
        if data:
            peer = socket_map.get(sock)
            if peer:
                peer.sendall(data)
        else:
            inputs.remove(sock)
            peer = socket_map.get(sock)
            if peer and peer in inputs:
                inputs.remove(peer)
            close_relay(sock)
    except Exception as e:
        print(e)
        if sock in inputs:
            inputs.remove(sock)
        peer = socket_map.get(sock)
        if peer and peer in inputs:
            inputs.remove(peer)
        close_relay(sock)

def run(listen_port, remote_host, remote_port):
    inputs = []
    listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen_sock.bind(("", listen_port))
    listen_sock.listen()
    listen_sock.setblocking(False)

    inputs.append(listen_sock)
    print(f"[#] Relay is listening on port {listen_port}")

    try:
        while True:
            readable, _, exceptional = select.select(inputs, [], inputs)
            for sock in readable:
                if sock is listen_sock:
                    accept_client(listen_sock, remote_host, remote_port, inputs)
                else:
                    data_transfer(sock, inputs)

            for sock in exceptional:
                if sock in inputs:
                    inputs.remove(sock)
                close_relay(sock)
    except Exception:
        print("\n[#] Relay is shutting down...")
    finally:
        for sock in inputs:
            sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Concurrent TCP Relay")
    parser.add_argument("host", help="Target server host")
    parser.add_argument("port", type=int, help="Target server port")
    parser.add_argument("relay_port", type=int, help="Relay listening port")
    args = parser.parse_args()
    run(args.relay_port, args.host, args.port)
