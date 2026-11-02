"""Fail the workflow if Pages did not actually serve the new release."""
import json
import os
from pathlib import Path
import time
import urllib.request

root = Path(__file__).resolve().parents[1]
expected = json.loads((root/'refresh-status.json').read_text())['runId']
base = os.environ['DART_PUBLIC_URL'].rstrip('/')
for attempt in range(12):
    try:
        req = urllib.request.Request(base+'/refresh-status.json?run='+expected, headers={'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(req, timeout=20) as response:
            actual = json.load(response)
        if actual['runId'] == expected:
            with urllib.request.urlopen(base+'/model.json?run='+expected, timeout=20) as response:
                model = json.load(response)
            if model.get('refreshRunId') == expected:
                print('Verified published release', expected)
                break
    except Exception as error:
        print('Waiting for published release:', type(error).__name__, flush=True)
    time.sleep(10)
else:
    raise SystemExit('The public site did not serve the new model; deployment is not verified')
