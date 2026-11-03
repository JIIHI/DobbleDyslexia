"""Start the Word Spot online server:  python -m wordspot.online [--port 8000]"""

import argparse

import uvicorn

from wordspot.online.server import app, lan_address


def main() -> None:
    parser = argparse.ArgumentParser(description="Word Spot online game server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    ip = lan_address()
    print("\n  Word Spot is running!")
    print(f"  On this computer:      http://localhost:{args.port}")
    if ip:
        print(f"  On iPads and phones:   http://{ip}:{args.port}   (same wifi)")
    print("  Press Ctrl+C to stop.\n")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
