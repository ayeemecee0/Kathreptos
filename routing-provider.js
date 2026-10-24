/* Browser-only provider transport: no route history, cookies or secret keys. */
(function(root,factory){const api=factory();if(typeof module!=='undefined'&&module.exports)module.exports=api;if(root)root.KatoptronProvider=api;})(typeof window!=='undefined'?window:null,function(){
'use strict';
const MAX_BYTES=6000000;
function base(input){
 const u=new URL(input);
 if(u.protocol!=='https:'||u.username||u.password||u.search||u.hash||u.port)
  throw new Error('Configured provider must use credential-free HTTPS base URL');
 return u.href.replace(/\/$/,'');
}
function client(fetcher=(...args)=>fetch(...args),clock=()=>Date.now(),delay=ms=>new Promise(r=>setTimeout(r,ms))){
 const health={routing:{failures:0,until:0},geocoding:{failures:0,until:0}};
 function status(kind){const h=health[kind];if(!h)throw Error('Unrecognized provider');return {available:clock()>=h.until,failures:h.failures};}
 function failed(kind,limited=false){const h=health[kind];h.failures++;if(limited||h.failures>=2)h.until=clock()+45000;}
 function succeeded(kind){health[kind]={failures:0,until:0};}
 async function json(kind,url,timeout,signal){
  if(!status(kind).available)throw Error('Location service temporarily unavailable; try later.');
  const u=new URL(url);
  base(u.origin);
  if(u.username||u.password)throw Error('Provider URL credentials disallowed');
  if(!Number.isInteger(timeout)||timeout<1000||timeout>30000)throw Error('Bad provider deadline');
  const controller=new AbortController();
  const cancel=()=>controller.abort();
  const timer=setTimeout(()=>controller.abort(),timeout);
  signal?.addEventListener('abort',cancel,{once:true});
  if(signal?.aborted)controller.abort();
  try{
   for(let attempt=0;attempt<2;attempt++){
    if(controller.signal.aborted)break;
    try{
     const r=await fetcher(u.href,{signal:controller.signal,cache:'no-store',
      credentials:'omit',redirect:'error',referrerPolicy:'no-referrer',
      headers:{Accept:'application/json'}});
     if(r.status===429){failed(kind,true);throw Error('Location service rate limited; try later.');}
     if(r.status>=500&&r.status<600){
      if(attempt===0){await delay(350);continue;}
      failed(kind);throw Error('Location service unavailable (HTTP '+r.status+').');
     }
     if(!r.ok){failed(kind);throw Error('Location provider rejected request (HTTP '+r.status+').');}
     if(!/\bjson\b/i.test(r.headers.get('content-type')||''))throw Error('Location provider returned invalid format');
     const reported=Number(r.headers.get('content-length')||0);
     if(!Number.isFinite(reported)||reported>MAX_BYTES)throw Error('Location response too large');
     // Streaming bounded read avoids materializing oversized upstream replies.
     let value='',size=0;
     if(r.body?.getReader){
      const reader=r.body.getReader();const decoder=new TextDecoder();
      try{while(true){
       const step=await reader.read();if(step.done)break;
       size+=step.value.byteLength;
       if(size>MAX_BYTES)throw Error('Location response too large');
       value+=decoder.decode(step.value,{stream:true});
      }value+=decoder.decode();}finally{reader.releaseLock();}
     }else{value=await r.text();if(value.length>MAX_BYTES)throw Error('Location response too large');}
     if(!value)throw Error('Location provider returned empty data');
     let decoded;
     try{decoded=JSON.parse(value);}catch{throw Error('Location provider returned invalid JSON');}
     succeeded(kind);return decoded;
    }catch(err){
     if(controller.signal.aborted)break;
     if(err instanceof TypeError && attempt===0){await delay(350);continue;}
     if(!/rate limited|unavailable \(HTTP|rejected request/.test(String(err.message)))failed(kind);
     throw err;
    }
   }
   if(signal?.aborted){const e=Error('Location request canceled');e.name='AbortError';throw e;}
   failed(kind);throw Error('Location provider timed out; route results are unknown.');
  }finally{clearTimeout(timer);signal?.removeEventListener('abort',cancel);}
 }
 return Object.freeze({json,status});
}
return Object.freeze({base,client});
});