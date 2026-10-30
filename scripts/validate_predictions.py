"""CLI for the shared prediction protocol checks."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from worldnav.protocol import load_json, validate, validate_zip

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prediction", type=Path)
    parser.add_argument("--split", choices=["val_seen", "val_unseen", "test"], required=True)
    parser.add_argument("--manifest", type=Path,
                        help="Official JSON with episodes, or JSON array of official IDs")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    expected = None
    if args.manifest:
        manifest = load_json(args.manifest.read_text())
        expected = [x["episode_id"] for x in manifest["episodes"]] if isinstance(manifest, dict) else manifest
    print(json.dumps(validate(load_json(args.prediction.read_text()), args.split,
                              expected, args.full), indent=2))
