import socket
import re
import select
import sys
import argparse

BUFFER_SIZE = 4096

nextHopData = {}


socket_map = {}
inputs = []
cache = {}

def close_relay(conn):
    pair = socket_map.pop(conn, None)
    if pair in socket_map:
        del socket_map[pair]
    if conn in inputs:
        inputs.remove(conn)
    try:
        conn.close()
    except Exception as e:
        print(f"[ERROR] Closing {conn}")
    if pair:
        try:
            pair.close()
        except Exception as e:
            print(f"[ERROR] Closing {pair}")

def accept_client(listen_sock):
    try:
        client_conn, client_addr = listen_sock.accept()
        client_conn.setblocking(False)
        inputs.append(client_conn)
        socket_map[client_conn] = None
        print(f"[#] Client connected: {client_addr}")
    except Exception as e:
        print(f"[ERROR] Could not set up the relay")

def parse_host_port(request):
    host_match = re.search(r"Host:\s*([^\r\n]+)", request, re.IGNORECASE)
    if host_match:
        host_port = host_match.group(1).strip()
        if ':' in host_port:
            host, port = host_port.split(':', 1)
            return host, int(port)
        else:
            return host_port, 80
    match = re.match(r"GET\s+http://([^/:]+)(:(\d+))?/", request)
    if match:
        host = match.group(1)
        port = int(match.group(3)) if match.group(3) else 80
        return host, port
    return None, None

def handle_http_request(sock, isFinalRelay):
    try:
        data = sock.recv(BUFFER_SIZE)
        if not data:
            close_relay(sock)
            return

        request = data.decode()
        uri_match = re.match(r"GET\s+(\S+)", request)
        uri = uri_match.group(1) if uri_match else None

        if uri and uri in cache:
            print(f"Requested URI is served by the cache")
            sock.sendall(cache[uri])
            close_relay(sock)
            return

        remote_host, remote_port = parse_host_port(request)
        if not remote_host:
            close_relay(sock)
            return

        server_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if(isFinalRelay):
            try:
                print('this is remote host and port')
                print(remote_host)
                print(remote_port)
                print('This is response sent first')
                print(request)
                server_conn.connect((remote_host, remote_port))
                server_conn.sendall(data)
            except Exception as e:
                print(e)
                print('Exception sending data')
        else:
            server_conn.connect((nextHopData['ip'], nextHopData['port']))
            server_conn.sendall(data)
        # server_conn.connect((remote_host, remote_port))
        # server_conn.sendall(data)

        response = b''
        while True:
            print('Sampe sini')
            print(response)
            chunk = server_conn.recv(BUFFER_SIZE)
            if not chunk:
                break
            response += chunk

        server_conn.close()

        if uri:
            cache[uri] = response
        print('This is response sent back!')
        print(response)

        sock.sendall(response)
        close_relay(sock)

    except (ConnectionResetError, OSError) as e:
        close_relay(sock)

def run(listen_port, nextHopIp = None, nextHopPort = None):
    isFinalRelay = True
    if nextHopIp != None  and nextHopPort != None:
        print('Not acting as a final relay.')
        isFinalRelay = False
        nextHopData['ip'] = nextHopIp
        nextHopData['port'] = int(nextHopPort)
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
            readable, _, _ = select.select(inputs, [], [])
            for sock in readable:
                if sock is listen_sock:
                    accept_client(listen_sock)
                else:
                    handle_http_request(sock, isFinalRelay)
    except Exception as e:
        print(f"Shutting Down...")
        print(e)
    finally:
        for s in inputs:
            s.close()
        print(f"Relay stopped")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HTTP Relay")
    parser.add_argument("relay_port", type=int, default=9080, help="Relay port number")
    parser.add_argument("--next_hop_ip", type=str, default=None, help="IP Address of the next hop", required=False)
    parser.add_argument("--next_hop_port", type=int, default=None, help="Port number of the next hop", required=False)
    args = parser.parse_args()
    run(args.relay_port, args.next_hop_ip, args.next_hop_port)