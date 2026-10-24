"""Owner-reviewed original-government GIS inputs; never from untrusted Esri search.

Adding a JSON entry does NOT authorize a source for publication: a separate,
DB-owner-approved source row is mandatory. HTTP workers accept only exact
normalized pinned HTTPS layer and agency URLs supplied by this audited file.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

FILE=Path(__file__).with_name('reviewed_first_party_gis_sources.json')
KEY=re.compile(r'^agency_[a-z0-9_]{5,46}$')
LAYER=re.compile(r'^/[A-Za-z0-9_/-]+/(?:MapServer|FeatureServer)/[0-9]+$')
MAX_SOURCES=100

def original_domain(host):
    if not isinstance(host,str) or not re.fullmatch(r'[a-z0-9.-]{4,180}',host):
        return None
    labels=host.split('.')
    if len(labels)<2 or any(not x or x.startswith('-') or x.endswith('-') for x in labels):
        return None
    # A shared state/local-government namespace such as city.wa.us or
    # county.co.us does not grant other municipalities the same authority.
    # Compare one additional owner label for state-code and reserved .us
    # suffixes instead of trusting the shared "wa.us"/"co.us" suffix.
    if labels[-1]=='us' and (len(labels[-2])==2 or
            labels[-2] in {'k12','state','pvt','fed','dni','isa','kids','nsn','lib','gen'}):
        return '.'.join(labels[-3:]) if len(labels)>=3 else None
    return '.'.join(labels[-2:])

def _url(url,layer=False):
    if not isinstance(url,str) or len(url)>450:
        raise ValueError('Reviewed government GIS URLs malformed')
    parsed=urlsplit(url)
    if (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password
        or parsed.port is not None or parsed.query or parsed.fragment):
        raise ValueError('Reviewed government GIS requires exact HTTPS URL without credentials or redirect query')
    if layer and not LAYER.fullmatch(parsed.path):
        raise ValueError('Reviewed GIS layer must identify an exact original ArcGIS feature layer')
    return parsed

def validate_source(row):
    required={'source_key','jurisdiction','original_gis_page','public_gis_anchor',
              'layer','bounds_south','bounds_west','bounds_north','bounds_east',
              'review_basis'}
    if not isinstance(row,dict) or set(row)!=required:
        raise ValueError('Reviewed agency source schema must exactly match the approved fields')
    if not isinstance(row['source_key'],str) or not KEY.fullmatch(row['source_key']):
        raise ValueError('Invalid reviewed agency source identity')
    if (not isinstance(row['jurisdiction'],str) or
        not re.fullmatch(r'[A-Za-z .-]{3,90}, [A-Z]{2}',row['jurisdiction']) or
        not isinstance(row['review_basis'],str) or len(row['review_basis'].strip())<130):
        raise ValueError('Explicit human-reviewed original agency source explanation required')
    page=_url(row['original_gis_page'])
    portal=_url(row['public_gis_anchor'])
    layer=_url(row['layer'],layer=True)
    domain=original_domain(page.hostname)
    if (not domain or domain!=original_domain(portal.hostname)
        or domain!=original_domain(layer.hostname)):
        raise ValueError('Original agency GIS portal and layer must be on the reviewed original-agency domain')
    bounds=[row[k] for k in ('bounds_south','bounds_west','bounds_north','bounds_east')]
    if (any(type(n) not in (int,float) for n in bounds) or
        not (17<=bounds[0]<bounds[2]<=72 and -180<=bounds[1]<bounds[3]<=-64)
        or bounds[2]-bounds[0]>2.5 or bounds[3]-bounds[1]>2.5):
        raise ValueError('Reviewed source requires finite, narrow US camera-location bounds')
    return dict(row)

def load_sources():
    raw=json.loads(FILE.read_text(encoding='utf8'))
    if not isinstance(raw,list) or not 1<=len(raw)<=MAX_SOURCES:
        raise ValueError('No valid bounded reviewed agency-source inventory')
    sources=[validate_source(x) for x in raw]
    if len({x['source_key'] for x in sources})!=len(sources) or \
       len({x['layer'] for x in sources})!=len(sources):
        raise ValueError('Duplicate reviewed source ID or ArcGIS layer')
    return tuple(sources)
