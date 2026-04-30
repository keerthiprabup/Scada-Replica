import socket
import time
import threading
import argparse

def generate_payload(size):
    # Create a dummy payload of given size
    return b'A' * size

def send_packets(target, port, rate, payload_size, duration):
    interval = 1.0 / rate
    payload = generate_payload(payload_size)

    end_time = time.time() + duration
    sent = 0

    while time.time() < end_time:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect((target, port))

            s.sendall(payload)
            sent += 1

            s.close()
        except Exception:
            pass

        time.sleep(interval)

    print(f"[+] Sent {sent} packets")

def main():
    parser = argparse.ArgumentParser(description="Controlled Traffic Generator (for IDS testing)")
    parser.add_argument("--target", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--rate", type=int, default=100, help="Packets per second")
    parser.add_argument("--size", type=int, default=100, help="Payload size in bytes")
    parser.add_argument("--duration", type=int, default=10, help="Duration in seconds")
    parser.add_argument("--threads", type=int, default=1)

    args = parser.parse_args()

    threads = []
    for _ in range(args.threads):
        t = threading.Thread(
            target=send_packets,
            args=(args.target, args.port, args.rate, args.size, args.duration)
        )
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

if __name__ == "__main__":
    main()