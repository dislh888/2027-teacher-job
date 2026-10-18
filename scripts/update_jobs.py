#!/usr/bin/env python3
"""Daily RSS discovery for 2027 mathematics teacher roles in Hefei and Shanghai.

Important: search discovery is NOT eligibility verification. New results always have fit=D.
Dependencies: Python 3.11+ standard library; no API keys or scraping login sites.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
import hashlib
import html
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data'
SITE = ROOT / 'site' / 'data'
TZO = timezone(timedelta(hours=8))
SEARCHES = [
    # Overlapping queries make failures of individual news indexes less harmful.
    ('上海', '上海 教师招聘 公告'),
    ('上海', '上海 数学教师 招聘'),
    ('上海', '上海 2027届 数学教师 招聘'),
    ('上海', '上海 2027 数学 教师 校园招聘 初中 高中'),
    ('上海', '上海 2027 数学 中职 高职 专任教师 招聘'),
    ('上海', '上海 2027 数学 教师 site:edu.sh.gov.cn'),
    ('上海', '上海 数学教师 2027 site:gov.cn'),
    ('上海', '浦东 宝山 闵行 2027 数学 教师招聘'),
    ('合肥', '合肥 教师招聘 公告'),
    ('合肥', '合肥 数学教师 招聘'),
    ('合肥', '合肥 2027届 数学教师 招聘'),
    ('合肥', '合肥 2027 数学 教师 校园招聘 初中 高中'),
    ('合肥', '合肥 2027 数学 中职 高职 专任教师 招聘'),
    ('合肥', '合肥 数学教师 2027 site:gov.cn'),
    ('合肥', '肥西 肥东 长丰 2027 数学教师 招聘'),
    ('合肥', '安徽合肥 2027 数学教师 site:edu.cn'),
]
CITY_WORDS = {
 '上海': re.compile('上海|浦东|宝山|闵行|徐汇|静安|黄浦|杨浦|虹口|奉贤|崇明|松江|嘉定|青浦|金山|普陀|长宁'),
 '合肥': re.compile('合肥|肥西|肥东|长丰|庐江|巢湖|蜀山|瑶海|包河|庐阳'),
}
RE_RECRUIT = re.compile('招聘|招录|招募|诚聘|选聘|引进.*教师')
RE_NOTICE = re.compile('公告|简章|岗位|计划|启事|诚聘')
RE_NON_JOB = re.compile('招聘会|招聘办法|职称评审|教师主页|师资缺口|招聘结果|拟聘|录用公示|面试成绩|笔试成绩')
RE_MATH = re.compile('数学|数学学科|计算数学|基础数学|应用数学')
RE_TEACH = re.compile('教师|老师|教学|任教|教研|师资|教职|招聘|教员|专任')
RE_SCHOOL = re.compile('学校|中学|中职|技工|职业|高中|初中|专科|高职|高校|学院|教育|师范|教师')
RE_EARLY = re.compile('2027|应届|毕业生|校园招聘|校招|储备教师|招聘')
RE_EXCLUDE = re.compile('（讲座）|考研复试|学科竞赛培训|招生简章|中考真题|高考真题|试卷解析|招生录取|数学建模大赛')
UA = 'Mozilla/5.0 (compatible; 2027MathTeacherJobsBot/1.0; public RSS monitoring)'


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def read_json(path, fallback):
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return fallback


def strip_markup(text):
    text = re.sub(r'<[^>]+>', ' ', text or '')
    text = html.unescape(text)
    return ' '.join(text.replace('\xa0',' ').split())[:1800]


def parse_date(value):
    if not value:
        return ''
    try:
        d = parsedate_to_datetime(value)
        if d.tzinfo is None:
            d = d.replace(tzinfo=TZO)
        return d.astimezone(TZO).date().isoformat()
    except Exception:
        pass
    try:
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if d.tzinfo is None:
            d = d.replace(tzinfo=TZO)
        return d.astimezone(TZO).date().isoformat()
    except ValueError:
        pass
    m = re.search(r'20\d{2}-\d{2}-\d{2}', value)
    if m:
        try:
            return datetime.fromisoformat(m.group()).date().isoformat()
        except ValueError:
            pass
    return ''


def parse_rss(content):
    root = ET.fromstring(content)
    if root.tag not in ('rss', '{http://www.w3.org/2005/Atom}feed'):
        raise ValueError('response is not an RSS/Atom feed')
    for item in root.findall('.//item'):
        yield {
            'title': strip_markup(item.findtext('title') or ''),
            'url': (item.findtext('link') or '').strip(),
            'summary': strip_markup(item.findtext('description') or ''),
            'date': parse_date(item.findtext('pubDate') or ''),
        }
    # Fallback for Atom feeds.
    for item in root.findall('.//{http://www.w3.org/2005/Atom}entry'):
        link = next((x.attrib.get('href','') for x in item.findall('{http://www.w3.org/2005/Atom}link') if x.attrib.get('href')), '')
        ns = '{http://www.w3.org/2005/Atom}'
        yield {'title':strip_markup(item.findtext(ns+'title') or ''),
               'url':link,'summary':strip_markup(item.findtext(ns+'summary') or ''),
               'date':parse_date(item.findtext(ns+'published') or item.findtext(ns+'updated') or '')}


def feed_urls():
    for city, query in SEARCHES:
        q = urllib.parse.quote(query)
        yield city, 'bing', 'https://www.bing.com/search?format=rss&q='+q
        yield city, 'google_news', 'https://news.google.com/rss/search?q='+q+'&hl=zh-CN&gl=CN&ceid=CN%3Azh-Hans'


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent':UA, 'Accept':'application/rss+xml, application/xml, text/xml, */*'})
    with urllib.request.urlopen(req, timeout=14) as response:
        raw = response.read(3_000_000)
        if len(raw) == 3_000_000:
            raise ValueError('feed exceeds size limit')
        return raw


def normalized_url(url):
    try:
        p=urllib.parse.urlsplit(url)
        if p.scheme not in ('http', 'https') or not p.netloc:
            return ''
        # Strip only common analytics tags; some job sites need query parameters.
        q=urllib.parse.parse_qsl(p.query, keep_blank_values=True)
        q=[(k,v) for k,v in q if not k.lower().startswith('utm_') and k.lower() not in {'fbclid','gclid'}]
        return urllib.parse.urlunsplit((p.scheme, p.netloc.lower(),p.path or '/',urllib.parse.urlencode(sorted(q)),'')).strip()
    except ValueError:
        return ''


def rejection_reason(entry, query_city, seen_time):
    title = entry['title']
    blob = title+' '+entry['summary']
    if not normalized_url(entry['url']): return 'invalid_url'
    if len(title) < 7: return 'short_title'
    if RE_EXCLUDE.search(title) or RE_NON_JOB.search(title): return 'not_job_notice'
    today = datetime.fromisoformat(seen_time.replace('Z', '+00:00')).astimezone(TZO).date()
    if entry['date']:
        try:
            published = datetime.fromisoformat(entry['date']).date()
        except ValueError:
            return 'invalid_date'
        if published < today - timedelta(days=180): return 'older_than_180_days'
        if published > today + timedelta(days=1): return 'future_date'
    # Never infer locality from the query. Generic 高新区/经开区 are ambiguous.
    if not CITY_WORDS[query_city].search(blob): return 'missing_city'
    other = '合肥' if query_city == '上海' else '上海'
    if other in title and not CITY_WORDS[query_city].search(title): return 'conflicting_city'
    if not RE_RECRUIT.search(blob): return 'missing_recruitment'
    if not RE_SCHOOL.search(blob): return 'missing_school'
    if not RE_TEACH.search(blob): return 'missing_teaching'
    # General school teacher notices are useful leads even if subject tables are absent.
    # Require an explicit teacher notice; generic corporate campus recruitment stays out.
    if not RE_MATH.search(blob):
        if not (re.search('教师|师资|教员|专任', title) and RE_NOTICE.search(title)):
            return 'missing_math_or_teacher_notice'
    return ''


def candidate(entry, query_city, seen_time):
    if rejection_reason(entry, query_city, seen_time): return None
    title = entry['title']
    source = normalized_url(entry['url'])
    summary = entry['summary']
    city = query_city
    has_math = bool(RE_MATH.search(title+' '+summary))
    stage = '待核实'
    if re.search('高职|职业技术学|高等专科|大专|高校',title):stage='高职/大专'
    elif re.search('中专|中职|中等职业|技工',title):stage='中职/中专'
    elif '高中' in title:stage='高中'
    elif '初中' in title:stage='初中'
    # Anchor ID to normalized URL. Opaque engine redirect URLs remain distinct.
    candidate_id='rss-'+hashlib.sha256(source.encode('utf-8')).hexdigest()[:18]
    return {
        'id':candidate_id, 'school':title[:100], 'city':city,
        'district':'待核实', 'sector':'待核实', 'stage':stage,
        'role':('数学教师相关招聘线索（岗位待确认）' if has_math else '教师招聘公告（是否含数学岗位待核实）'), 'places':'未公布', 'fit':'D',
        'license':'尚未核验：请确认2027届身份、专业、教资取得时点及学历要求',
        'note':'自动检索摘要：'+summary[:240] if summary else '每日自动发现的检索结果。请点开原公告核对是否真实在招，以及是否招聘数学教师。',
        'source':source,'apply':'','email':'','phone':'',
        'date':entry['date'],'deadline':'',
        'method':'仅供发现线索，不代表已核实招聘资格或报名入口；请从原公告寻找正式投递渠道',
        'source_type':'RSS自动检索·未经人工核验',
        'discovery_evidence':{'math_in_snippet':has_math,'city_in_snippet':True, 'publication_date_known':bool(entry['date'])},
        'origin':'rss', 'verified_at':'','first_seen':seen_time,'last_seen':seen_time,
    }


def run(fixture=None, output_root=None, audit_dir=None):
    base = (output_root / "data") if output_root else BASE
    site = (output_root / "site" / "data") if output_root else SITE
    now=datetime.now(timezone.utc).isoformat(timespec='seconds')
    curated=read_json(base/'jobs_curated.json',[])
    previous=read_json(base/'candidates.json',[])
    old={x['id']:x for x in previous}
    latest=read_json(site/'latest.json',{})
    prevstatus=latest.get('status',{})
    issues=[]; results=[]; successes=0; failures=0
    feed_stats=[]; audit=[]
    if fixture:
        for f in fixture.glob('*.xml'):
            try:
                city='上海' if 'shanghai' in f.name.lower() else '合肥'
                feed=list(parse_rss(f.read_bytes()))
                feed_stats.append({'source':f.name,'city':city,'hits':len(feed)})
                results.extend((city, x) for x in feed)
                successes+=1
            except Exception as e:
                issues.append(f.name+': '+str(e)[:120]); failures+=1
    else:
        jobs=list(feed_urls())
        with ThreadPoolExecutor(max_workers=8) as pool:
            wait={pool.submit(fetch,url):(city,kind,url) for city,kind,url in jobs}
            for fut in as_completed(wait):
                city,engine,url=wait[fut]
                try:
                    raw=fut.result()
                    feed=list(parse_rss(raw))
                    feed_stats.append({'engine':engine,'city':city,'url':url,'hits':len(feed)})
                    if audit_dir:
                        audit_dir.mkdir(parents=True,exist_ok=True)
                        (audit_dir/(hashlib.sha256(url.encode()).hexdigest()[:16]+'.xml')).write_bytes(raw)
                    successes+=1
                    results.extend((city, x) for x in feed)
                except Exception as e:
                    failures+=1
                    if len(issues)<12:
                        issues.append(f'{engine}/{city}: {type(e).__name__}: {str(e)[:100]}')
    new=0; matched=0; duplicates=0; curated_duplicates=0
    reasons=Counter()
    known_links={normalized_url(x.get('source','')) for x in curated}
    run_seen=set()
    for city, item in results:
        reason=rejection_reason(item,city,now)
        audit.append({'query_city':city,**item,'decision':reason or 'accepted'})
        if reason:
            reasons[reason]+=1
            continue
        x=candidate(item,city,now)
        matched+=1
        if x['source'] in known_links:
            curated_duplicates+=1
            continue
        if x['id'] in run_seen:
            duplicates+=1
            continue
        run_seen.add(x['id'])
        if x['id'] in old:
            former=old[x['id']]
            x['first_seen']=former.get('first_seen',now)
        else:
            new+=1
        old[x['id']]=x
    # Keep historical discoveries for 120 days; lack of search reappearance does NOT prove expiry.
    age=datetime.now(timezone.utc)-timedelta(days=120)
    candidates=[]
    for j in old.values():
        try:
            d=datetime.fromisoformat(j.get('last_seen',now).replace('Z','+00:00'))
            if d<age: continue
        except ValueError:
            pass
        candidates.append(j)
    candidates.sort(key=lambda j:j.get('first_seen',''),reverse=True)
    # A cap limits website payload, preserving most recent first.
    candidates=candidates[:750]
    status={
        'last_run':now, 'last_successful_search':now if successes else prevstatus.get('last_successful_search'),
        'successful_feeds':successes, 'failed_feeds':failures,
        'new_candidates':new, 'total_candidates':sum(normalized_url(j['source']) not in known_links for j in candidates),
        'raw_search_hits':len(results),'relevant_hits':matched,
        'rejection_counts':dict(reasons),'duplicate_hits':duplicates,
        'curated_duplicate_hits':curated_duplicates,
        'empty_feeds':sum(f['hits']==0 for f in feed_stats),'feeds':feed_stats,
        'discovery_health':('no_feed' if not successes else 'no_candidates' if not run_seen else 'leads_found'),
        'issues':issues[:12], 'mode':'rss_daily_discovery',
        'curated_snapshot':'2026-10-17',
    }
    # Never replace the known curated jobs with unreviewed search results.
    # Dedupe candidate from curated URLs, even when title differs.
    separate=[j for j in candidates if normalized_url(j['source']) not in known_links]
    merged=curated+separate
    save_json(base/'candidates.json',candidates)
    save_json(site/'latest.json',{'status':status,'jobs':merged})
    if audit_dir:
        save_json(audit_dir/'decisions.json',{'status':status,'entries':audit})
    if successes and not run_seen:
        print('::warning::Feeds responded but no new distinct unverified leads passed screening; inspect rejection_counts and audit artifact.')
    print(f'RSS feeds: {successes} succeeded; {failures} failed; {len(results)} hits, {matched} relevant; new {new}, total {len(separate)} unverified records')
    if not successes:
        print('::warning::No RSS feeds succeeded; this is NOT a successful recruitment data refresh.')
    print('Status:',json.dumps(status,ensure_ascii=False))
    return status


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--fixture-dir',type=Path,default=None,help='For testing only. Parse *.xml files instead of network feeds.')
    p.add_argument('--output-root',type=Path,help='Write isolated output instead of production data')
    p.add_argument('--audit-dir',type=Path,help='Save raw feeds and per-entry decisions')
    args=p.parse_args()
    run(args.fixture_dir,args.output_root,args.audit_dir)