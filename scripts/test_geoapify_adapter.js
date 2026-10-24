const assert=require('node:assert/strict');
const A=require('../geoapify-adapter.js');
const cfg={locationProvider:'geoapify',geoapifyPublicKey:'a'.repeat(30)};
const from={point:[38.5816,-121.4944]},to={point:[38.6779,-121.1761]};
assert.throws(()=>A.publicKey({locationProvider:'geoapify',geoapifyPublicKey:''}),/missing/);
assert.throws(()=>A.publicKey({locationProvider:'demo',geoapifyPublicKey:'a'.repeat(30)}),/not enabled/);
const geocode=A.geocodeUrl('Sacramento, California',cfg);
assert.ok(geocode.startsWith('https://api.geoapify.com/v1/geocode/search?'));
assert.ok(geocode.includes('filter=countrycode%3Aus'));
const converted=A.geocodeAsPhoton({results:[
 {lat:38.5816,lon:-121.4944,country_code:'us',name:'Sacramento',state:'California'},
 {lat:51.5,lon:-0.12,country_code:'gb',name:'London'}]});
assert.equal(converted.features.length,1);
assert.deepEqual(converted.features[0].geometry.coordinates,[-121.4944,38.5816]);
assert.throws(()=>A.geocodeAsPhoton({features:[]}),/no verified/);
const urls=A.routeUrls(from,to,cfg);
assert.equal(urls.length,2);
assert.ok(urls[0].includes('type=balanced'));
assert.ok(urls[1].includes('type=short'));
assert.ok(urls.every(x=>x.includes('mode=drive')));
const fixture=d=>({type:'FeatureCollection',features:[{
 geometry:{type:'MultiLineString',coordinates:[
 [[-121.4944,38.5816],[-121.48,38.59]],
 [[-121.48,38.59],[-121.1761,38.6779]]]},
 properties:{distance:d,time:1200}}]});
const osrm=A.routingAsOsrm([fixture(28000),fixture(29500)]);
assert.equal(osrm.code,'Ok');
assert.equal(osrm.routes.length,2);
assert.equal(osrm.routes[0].geometry.coordinates.length,3);
assert.deepEqual(osrm.routes[0].geometry.coordinates[0],[-121.4944,38.5816]);
assert.throws(()=>A.routingAsOsrm([{type:'FeatureCollection',features:[
 {geometry:{type:'Point',coordinates:[-121,38]},properties:{distance:10,time:10}}]}]),/Unexpected/);
assert.throws(()=>A.routeUrls({point:[0,0]},to,cfg),/Invalid/);
console.log('Optional free Geoapify API geocoder and real-route compatibility tests passed');
