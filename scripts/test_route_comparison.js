const assert=require('node:assert/strict');
const Geo=require('../route-geometry.js');
const C=require('../route-comparison.js');
const route={points:[[38.83,-104.81],[38.83,-104.79]],distance:2400,duration:220};
const at=(key,lat,lon,other={})=>({
 record_key:key,latitude:lat,longitude:lon,location_accuracy:'exact',
 last_source_recheck_at:new Date().toISOString(),...other});
const first=at('verified-1',38.83,-104.8);
const other=at('verified-2',38.836,-104.8);
const provisional=at('provisional-1',38.83,-104.8,
 {evidence_tier:'independently_corroborated'});
const approx=at('area-1',38.834,-104.8,
 {location_accuracy:'approximate',uncertainty_radius_m:500});
let summary=C.summarize(route,[first,first,other,provisional,approx],Geo);
assert.equal(summary.nearby,1,'same camera must not count twice');
assert.equal(summary.approx,1);
assert.equal(summary.overdue,0);
assert.equal(summary.unknown,0);
assert.equal(C.summarize(route,[provisional],Geo).nearby,0);
assert.equal(C.summarize(route,[],Geo).nearby,0);
assert.ok(!('riskScore' in summary),'no invented confidence or risk score');
summary=C.summarize(route,[at('stale',38.83,-104.8,{
  last_source_recheck_at:'2024-01-01T00:00:00Z'}),
  at('unknown',38.83,-104.8,{last_source_recheck_at:null})],Geo);
assert.equal(summary.overdue,1);
assert.equal(summary.unknown,1);
assert.equal(C.reviewFreshness({last_confirmed_on:'2026-01-01'}),'unknown');
assert.throws(()=>C.summarize(route,[{record_key:'x',latitude:'bad'}],Geo),/Invalid/);
assert.throws(()=>C.summarize(route,[first],null),/Cannot compare/);
console.log('Evidence-aware driving-route comparison tests passed');
