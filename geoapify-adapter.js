/* Optional Geoapify free-tier adapter. Key is a browser-visible, origin-restricted
 * PUBLIC API key. Never publish a secret or unscoped billable credential.
 * Not active until account setup and owner opts in via config.js.
 * Docs: https://apidocs.geoapify.com/docs/routing/
 */
(function(root,factory){const api=factory();if(typeof module!=='undefined'&&module.exports)module.exports=api;if(root)root.KatoptronGeoapify=api;})(typeof window!=='undefined'?window:null,function(){
'use strict';
const ENDPOINT='https://api.geoapify.com';
function publicKey(config){
 if(config?.locationProvider!=='geoapify')throw new Error('Geoapify is not enabled');
 const key=config.geoapifyPublicKey;
 if(typeof key!=='string'||!/^[a-zA-Z0-9_-]{20,160}$/.test(key))
  throw new Error('Geoapify free-tier key is missing or invalid; no external request sent');
 return key;
}
function geocodeUrl(query,config){
 const key=publicKey(config);
 if(typeof query!=='string'||query.trim().length<3||query.length>160)
  throw new Error('Enter a more specific location');
 const q=new URLSearchParams({text:query,format:'json',
  filter:'countrycode:us',limit:'5',lang:'en',apiKey:key});
 return ENDPOINT+'/v1/geocode/search?'+q.toString();
}
function geocodeAsPhoton(data){
 if(!Array.isArray(data?.results))throw new Error('Geoapify geocoder returned no verified results list');
 return {features:data.results.filter(x=>x&&Number.isFinite(x.lat)&&
  Number.isFinite(x.lon)&&String(x.country_code||'').toUpperCase()==='US')
  .map(x=>({geometry:{type:'Point',coordinates:[x.lon,x.lat]},
   properties:{countrycode:'US',name:String(x.name||x.formatted||'').slice(0,180),
    city:String(x.city||''),state:String(x.state||''),
    postcode:String(x.postcode||'')}}))};
}
function routeUrls(from,to,config){
 const key=publicKey(config);
 for(const p of [from?.point,to?.point]){
  if(!Array.isArray(p)||p.length!==2||!Number.isFinite(p[0])||!Number.isFinite(p[1])||
     p[0]<17||p[0]>72||p[1]<-180||p[1]>-64)
    throw new Error('Invalid US route endpoint');
 }
 const coords=[from.point,to.point].map(p=>p[0]+','+p[1]).join('|');
 return ['balanced','short'].map(type=>{
  const q=new URLSearchParams({waypoints:coords,mode:'drive',
   type,format:'geojson',apiKey:key});
  return ENDPOINT+'/v1/routing?'+q.toString();
 });
}
function routingAsOsrm(responses){
 if(!Array.isArray(responses)||!responses.length)throw new Error('No routing results available');
 const routes=[];
 for(const data of responses){
  if(!data)continue;
  if(data.type!=='FeatureCollection'||!Array.isArray(data.features))
    throw new Error('Geoapify route response invalid');
  for(const f of data.features.slice(0,3)){
   const geometry=f?.geometry;
   if(geometry?.type!=='MultiLineString'||!Array.isArray(geometry.coordinates)||
     geometry.coordinates.length===0)throw new Error('Unexpected Geoapify road geometry');
   const lines=geometry.coordinates;
   const coords=[];
   for(const line of lines) {
    if(!Array.isArray(line)||line.length<2)throw new Error('Incomplete route segment');
    for(let i=0;i<line.length;i++) {
     if(!Array.isArray(line[i])||line[i].length<2||
        !Number.isFinite(line[i][0])||!Number.isFinite(line[i][1]))
      throw new Error('Invalid route coordinates');
     if(coords.length && i===0 &&
       coords[coords.length-1][0]===line[i][0] &&
       coords[coords.length-1][1]===line[i][1])continue;
     coords.push([line[i][0],line[i][1]]);
    }
   }
   const distance=f.properties?.distance;
   const duration=f.properties?.time;
   if(!Number.isFinite(distance)||distance<=0||
     !Number.isFinite(duration)||duration<=0)
    throw new Error('Geoapify returned invalid route distance or time');
   routes.push({geometry:{type:'LineString',coordinates:coords},
    distance,duration});
  }
 }
 return {code:routes.length?'Ok':'NoRoute',routes};
}
return Object.freeze({publicKey,geocodeUrl,geocodeAsPhoton,routeUrls,routingAsOsrm});
});
