"""One-time safety probe: government-operated Peoria AZ Flock camera layer.

Never publishes records. Inspect exact owner-hosted point layer metadata and
bounded live query, report only counts and field validity.
"""
import json
import urllib.parse
import urllib.request

SERVICE='https://gis.peoriaaz.gov/arcgis/rest/services/PM/pmPublicWorks/MapServer'
LAYER=SERVICE+'/286'
def read(url):
  req=urllib.request.Request(url,headers={'User-Agent':'Katoptron/1.0 public GIS verification','Accept':'application/json'})
  with urllib.request.urlopen(req,timeout=24) as response:
    if response.geturl()!=url: raise ValueError('Redirected government GIS service')
    body=response.read(2_000_001)
  if len(body)>2_000_000:raise ValueError('Too-large government GIS response')
  obj=json.loads(body)
  if obj.get('error'): raise ValueError('Government GIS returned an error')
  return obj

def main():
  meta=read(LAYER+'?f=json')
  service=read(SERVICE+'?f=json')
  fields=meta.get('fields',[])
  names={f.get('name') for f in fields if isinstance(f,dict)}
  if meta.get('name')!='Flock Cameras' or meta.get('geometryType')!='esriGeometryPoint' or meta.get('type')!='Feature Layer':
    raise ValueError('Not an original government Flock point layer')
  if not {'OBJECTID','CameraID','Location'}.issubset(names):
    raise ValueError('Cannot identify individual government GIS camera points')
  layers={x.get('id'):x.get('name') for x in service.get('layers',[])}
  if layers.get(286)!='Flock Cameras':
    raise ValueError('County GIS service does not list the exact Flock camera layer')
  qs=urllib.parse.urlencode({'where':'1=1','outFields':'OBJECTID,CameraID,Location',
   'returnGeometry':'true','outSR':'4326','resultRecordCount':1000,'f':'json'})
  rows=read(LAYER+'/query?'+qs)
  features=rows.get('features')
  if not isinstance(features,list) or not features or len(features)>=1000 or rows.get('exceededTransferLimit'):
    raise ValueError('GIS source empty, truncated, or too big to reconcile')
  ok=0;bad=0
  for f in features:
    a=f.get('attributes') or {};g=f.get('geometry') or {}
    if (type(a.get('OBJECTID')) is int and str(a.get('CameraID') or '').strip()
      and type(g.get('x')) in (int,float) and type(g.get('y')) in (int,float)
      and 33.2 <=g['y']<=34.5 and -113<=g['x']<=-111.4):
      ok+=1
    else:bad+=1
  print('Government GIS source verified:',SERVICE)
  print('Layer:',meta.get('name'))
  print('Positive individual camera points:',ok)
  print('Held points with missing ID or out-of-area coordinates:',bad)
  print('Total GIS features:',len(features))
  if ok<1:raise ValueError('No independently locatable Flock camera points')
if __name__=='__main__':main()
