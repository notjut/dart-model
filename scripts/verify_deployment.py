"""Fail the workflow if Pages did not actually serve the new release."""
import json
import datetime as dt
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
                retrieved = dt.datetime.fromisoformat(model['inputRetrievedAt'].replace('Z', '+00:00'))
                age = dt.datetime.now(dt.timezone.utc) - retrieved
                if not dt.timedelta(0) <= age < dt.timedelta(hours=30):
                    raise ValueError('Published model inputs are not fresh')
                with urllib.request.urlopen(base+'/availability.json?run='+expected, timeout=20) as response:
                    availability = json.load(response)
                supplemental = availability.get('supplementalCheck', {})
                if supplemental.get('runId') != expected or supplemental != actual.get('supplementalInjuryCheck'):
                    raise ValueError('Published injury check does not match this release')
                print('Verified published release', expected)
                break
    except Exception as error:
        print('Waiting for published release:', type(error).__name__, flush=True)
    time.sleep(10)
else:
    raise SystemExit('The public site did not serve the new model; deployment is not verified')
