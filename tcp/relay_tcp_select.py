import socket
import select
import sys
import argparse

BUFFER_SIZE = 4096

socket_map = {}
inputs = []

def close_relay(conn):
    pair = socket_map.pop(conn, None)
    if pair in socket_map:
        del socket_map[pair]
    if conn in inputs:
        inputs.remove(conn)
    if pair in inouts:
        inouts.remove(pair)

    try:
        conn.close()
    except Exception as e:
        print(f"[ERROR] Closing {conn}")
    if pair:
        try:
            pair.close()
        except Exception as e:
            print(f"[ERROR] Closing {pair}")


def accept_client(listen_sock, remote_host, remote_port):
    try:
        client_conn, client_addr = listen_sock.accept()
        client_conn.setblocking(False)

        server_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_conn.connect((remote_host, remote_port))
        server_conn.setblocking(False)

        inputs.append(client_conn)
        inputs.append(server_conn)

        socket_map[client_conn] = server_conn
        socket_map[server_conn] = client_conn

        print(f"New relay: {client_addr} -> {remote_host}:{remote_port}")

    except Exception as e:
        print(f"[ERROR] Could not set up the relay")
        print(e)

def  data_transfer(sock, remote_host, remote_port):
    try:
        data = sock.recv(BUFFER_SIZE)

        if data:
            paired_sock = socket_map.get(sock)
            if paired_sock:
                paired_sock.sendall(data)
            else:
                close_relay(sock)
        else:
            close_relay(sock)
    except (ConnectionResetError, OSError):
        close_relay(sock)


def run(listen_port, remote_host, remote_port):
    listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        listen_sock.bind(("", listen_port))
    except Exception as e:
        print(f"[ERROR] Could not bind to port {listen_port}")
        sys.exit(1)
    listen_sock.listen()
    listen_sock.setblocking(False)

    inputs.append(listen_sock)

    print(f"[#] Relay running on port {listen_port}")

    try:
        while inputs:
            readable, _, _ = select.select(inputs, [], inputs)

            for sock in readable:
                if sock is listen_sock:
                    accept_client(listen_sock, remote_host, remote_port)
                else:
                    data_transfer(sock, remote_host, remote_port)
    except Exception as e:
        print(f"Shutting Down...")
        print(e)
    finally:
        for sock in inputs:
            if sock is not listen_sock:
                close_pair(sock)
            else:
                sock.close()
        print(f"Relay stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple TCP Relay")
    parser.add_argument("host", help="Host address of server")
    parser.add_argument("port", type=int, help="Port number of server")
    parser.add_argument("relay_port", type=int, default=9080, help="Replay port number")
    args = parser.parse_args()
    run(args.relay_port, args.host, args.port)

