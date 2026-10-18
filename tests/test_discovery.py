import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import update_jobs as u
NOW = '2026-10-18T05:00:00+00:00'

def entry(title='上海某中学2027年教师招聘公告', **kw):
    return dict(title=title, summary=kw.get('summary', ''),
                url=kw.get('url', 'https://example.edu.cn/job?id=1'), date=kw.get('date', '2026-10-15'))

class DiscoveryTests(unittest.TestCase):
    def test_general_notice_without_subject(self):
        j=u.candidate(entry(), '上海', NOW)
        self.assertEqual(j['fit'], 'D')
        self.assertFalse(j['discovery_evidence']['math_in_snippet'])
        self.assertIn('是否含数学',j['role'])
        self.assertEqual(j['verified_at'], '')

    def test_subject_in_summary_and_local_district(self):
        self.assertIsNotNone(u.candidate(entry('肥西某中学公开招聘公告',summary='面向应届毕业生，招聘数学老师'), '合肥', NOW))

    def test_negative_cases(self):
        for title,city in [('经开区中学数学教师招聘公告','合肥'),
                           ('南京某中学数学教师招聘公告','上海'),
                           ('上海高校数学教师主页','上海'),
                           ('上海教师招聘会顺利举行','上海'),
                           ('上海中小学数学教学改革新闻','上海'),
                           ('上海科技公司数学算法工程师校园招聘','上海'),
                           ('上海中学数学教师拟聘公示','上海')]:
            with self.subTest(title=title): self.assertIsNone(u.candidate(entry(title),city,NOW))

    def test_dates(self):
        self.assertIsNone(u.candidate(entry(date='2025-10-17'),'上海',NOW))
        self.assertIsNone(u.candidate(entry(date='2027-10-17'),'上海',NOW))
        self.assertIsNone(u.candidate(entry(date='2026-02-30'),'上海',NOW))
        self.assertEqual(u.candidate(entry(date=''),'上海',NOW)['date'],'')
        self.assertEqual(u.parse_date('2026-02-30'),'')
        self.assertEqual(u.parse_date('2026-10-17T20:00:00Z'),'2026-10-18')

    def test_url_identity(self):
        self.assertEqual(u.normalized_url('https://EXAMPLE.com/job?b=2&utm_source=x&a=1#foo'),
                         u.normalized_url('https://example.com/job?a=1&b=2'))
        self.assertNotEqual(u.normalized_url('https://example.com/?id=1'),u.normalized_url('https://example.com/?id=2'))
        self.assertNotEqual(u.normalized_url('https://example.com/job'),u.normalized_url('https://example.com/job/'))

    def test_parser(self):
        self.assertEqual(len(list(u.parse_rss(b'<rss><channel/></rss>'))),0)
        with self.assertRaises(ValueError):list(u.parse_rss(b'<html/>'))
        atom=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Example</title><link href="https://example.com"/><updated>2026-10-15T00:00:00Z</updated></entry></feed>'
        self.assertEqual(list(u.parse_rss(atom))[0]['date'],'2026-10-15')

    def test_real_snapshot(self):
        feeds=json.loads((ROOT/'tests/fixtures/observed_20261018.json').read_text())
        entries=[(f['city'],x) for f in feeds for x in f['items']]
        accepted=[u.candidate(x,c,NOW) for c,x in entries if u.candidate(x,c,NOW)]
        self.assertEqual(len(entries),250)
        self.assertEqual(len(accepted),3)
        self.assertTrue(all(x['fit']=='D' for x in accepted))
        self.assertTrue(all(not x['discovery_evidence']['math_in_snippet'] for x in accepted))

    def test_isolated_run_preserves_curated_and_dedupes(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d); base=out/'data';base.mkdir()
            curated=json.loads((ROOT/'data/jobs_curated.json').read_text())
            original=(ROOT/'data/jobs_curated.json').read_bytes()
            u.save_json(base/'jobs_curated.json',curated)
            fixture=out/'feeds';fixture.mkdir()
            xml='<rss><channel><item><title>上海某中学数学教师招聘公告</title><link>https://example.edu.cn/job?id=1</link></item></channel></rss>'
            (fixture/'shanghai1.xml').write_text(xml);(fixture/'shanghai2.xml').write_text(xml)
            first=u.run(fixture,out,out/'audit');second=u.run(fixture,out)
            jobs=json.loads((out/'site/data/latest.json').read_text())['jobs']
            self.assertEqual(len(curated),33)
            self.assertEqual(jobs[:33],curated)
            self.assertEqual(len(jobs),34)
            self.assertEqual(first['new_candidates'],1)
            self.assertEqual(first['duplicate_hits'],1)
            self.assertEqual(second['new_candidates'],0)
            self.assertEqual((ROOT/'data/jobs_curated.json').read_bytes(),original)
            # A matching curated link never counts as a new discovery.
            xml=xml.replace('https://example.edu.cn/job?id=1',curated[0]['source'].replace('&','&amp;'))
            (fixture/'shanghai1.xml').write_text(xml);(fixture/'shanghai2.xml').unlink()
            third=u.run(fixture,out)
            self.assertEqual(third['new_candidates'],0)
            self.assertEqual(third['curated_duplicate_hits'],1)

if __name__=='__main__':unittest.main()
