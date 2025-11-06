import sys
import warnings
from pathlib import Path

from pydantic.json_schema import PydanticJsonSchemaWarning

# Ensure the project root is available on the Python path when running the tests.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

warnings.filterwarnings("ignore", category=PydanticJsonSchemaWarning)
