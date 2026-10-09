from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent / 'verifier'))
from specchoice_evidence.verify import BundleVerificationError, verify_bundle
try:
    verify_bundle(Path(__file__).parent)
except BundleVerificationError as error:
    print(str(error), file=sys.stderr)
    raise SystemExit(2)
print('bundle verified')
