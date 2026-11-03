import sys,unittest
import io
from unittest.mock import patch
from urllib.error import HTTPError
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from availability import parse,latest_report,fetch

class AvailabilityTests(unittest.TestCase):
 def sample(self,kind='Initial Report',day='2026-11-02',hour='18:00:00',zone='ET'):
  return {'ReportType':kind,'publishDate':day,'postedTime':hour,'conferenceTimeZone':zone,'footer':{'date':'2026-11-07'},'games':[{'teamName':'Boston College','rows':[{'name':'QB #1 Example Player','status':'Out'}]},{'teamName':'Florida State','rows':[]}]}
 def parse(self,**args):return parse({'r':self.sample(**args)},'ACC','2026-11-03T00:29:00+00:00',{'boston college':'103','florida state':'52'})[0]
 def test_pending_does_not_mean_healthy(self):
  r=self.parse(kind='Report Pending');self.assertEqual(r['status'],'pending');self.assertEqual(r['teams'][0]['concerns'],[]);self.assertIn('not confirmed',r['teams'][0]['summary']);self.assertIsNone(r['teams'][0]['reportPublished'])
 def test_future_publication_is_pending_even_without_label(self):self.assertEqual(self.parse(day='2026-11-04')['status'],'pending')
 def test_conference_timezone_matters(self):self.assertEqual(self.parse(hour='19:00:00',zone='CT')['status'],'pending')
 def test_unknown_timezone_does_not_fake_published_report(self):self.assertEqual(self.parse(zone='UNKNOWN')['status'],'unverified')
 def test_reported_concern_remains(self):self.assertEqual(self.parse()['teams'][0]['concerns'][0]['unit'],'Quarterback')
 def test_future_placeholder_does_not_replace_published_report(self):self.assertEqual(latest_report([self.parse(),self.parse(kind='Report Pending',day='2026-11-04')])['status'],'reported')
 def test_transient_server_failure_gets_one_retry(self):
  with patch('availability.urllib.request.urlopen',side_effect=[HTTPError('https://example.test',504,'Gateway Timeout',{},None),io.StringIO('{}')]) as opened:
   self.assertIsNone(fetch('ACC')[3]);self.assertEqual(opened.call_count,2)
 def test_access_error_is_not_retried(self):
  with patch('availability.urllib.request.urlopen',side_effect=HTTPError('https://example.test',403,'Forbidden',{},None)) as opened:
   self.assertIsNotNone(fetch('ACC')[3]);self.assertEqual(opened.call_count,1)
