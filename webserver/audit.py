def audit(logPath, uriFragment):
    requests = {}
    connectedClients = []

    with open(logPath, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split(';')
            if not parts or len(parts) < 3:
                continue

            record_type = parts[0]
            requestId = parts[1]

            if record_type == "REQUEST":
                if len(parts) >= 6:
                    uri = parts[5]
                    clientIp = parts[3].strip("()").split(",")[0].replace("'", "")
                    time = parts[2]
                    requests[requestId] = (time, uri, clientIp)

            elif record_type == "RESPONSE":
                if len(parts) >= 7:
                    size = int(parts[6])
                    status = int(parts[5])
                    if size > 0 and requestId in requests:
                        time, uri, clientIp = requests[requestId]
                        if uriFragment.lower() in uri.lower():
                            connectedClients.append({"clientIp": clientIp, 'time': time, 'size': size, 'status': status})

    print(f"Clients that accessed '{uriFragment}':")
    for connectedClient in connectedClients:
        print(f"client {connectedClient['clientIp']} connected at {connectedClient['time']} and received status {connectedClient['status']} with size {connectedClient['size']}", )


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print('Invalid parameters')
        sys.exit(1)
    
    audit(sys.argv[1], sys.argv[2])
