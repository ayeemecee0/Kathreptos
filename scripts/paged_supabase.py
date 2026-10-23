"""Fail-closed bounded PostgREST pagination for nationwide GIS source registries.

Do not treat the first 100 rows or a truncated HTTP response as the full
camera-source inventory. Each page uses a stable unique sort column and a
bounded result size; any malformed page stops downstream publication.
"""
from urllib.parse import parse_qsl, urlencode

def fetch_all(request, endpoint, sort_key, page_size=25, max_records=3000):
    if (not callable(request) or not endpoint or not sort_key or
        not (5<=page_size<=50) or not (page_size<=max_records<=10000)):
        raise ValueError("Invalid bounded government source registry pagination")
    if "?" not in endpoint:
        raise ValueError("Supabase source endpoint must have a SELECT query")
    path, raw=endpoint.split("?",1)
    pairs=[(k,v) for k,v in parse_qsl(raw,keep_blank_values=True)
           if k not in ("limit","offset","order")]
    if not path or not any(k=="select" for k,_ in pairs):
        raise ValueError("Only explicitly selected source columns may be paged")
    if not sort_key.replace("_","").isalnum():
        raise ValueError("Unsafe stable sort column")
    result=[]
    for offset in range(0,max_records,page_size):
        params=pairs+[("order",sort_key+".asc"),
                      ("limit",str(page_size)),("offset",str(offset))]
        response=request(path+"?"+urlencode(params))
        if not isinstance(response,list) or len(response)>page_size:
            raise ValueError("Government GIS registry response invalid or truncated")
        result.extend(response)
        if len(response)<page_size:
            return result
    raise ValueError("Government GIS registry exceeds supported scan capacity; fail closed")
