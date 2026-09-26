import argparse
from pathlib import Path
import uvicorn
from app import create_app

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=19877)
    parser.add_argument('--data-dir', type=Path, default=Path(__file__).resolve().parents[1] / 'data')
    args = parser.parse_args()
    uvicorn.run(create_app(args.data_dir), host='127.0.0.1', port=args.port, access_log=False)
