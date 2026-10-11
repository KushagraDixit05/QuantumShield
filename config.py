from pathlib import Path
import yaml

def load(path="configs/mvp.yaml"):
    return yaml.safe_load((Path(__file__).parent / path).read_text())
