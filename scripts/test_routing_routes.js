const assert=require('node:assert/strict');
const routing=require('../routing-routes.js');
const geo=require('../route-geometry.js');
const from={point:[38.8,-104.8],label:'Start'};
const to={point:[38.8,-104.75],label:'End'};
const coords=[[-104.8,38.8],[-104.77,38.81],[-104.75,38.8]];
const route=(pts=coords)=>({distance:5000,duration:420,
 geometry:{type:'LineString',coordinates:pts}});
const data={code:'Ok',routes:[route(),{...route(),distance:5400,duration:460,
 geometry:{type:'LineString',coordinates:[[-104.8,38.8],[-104.78,38.78],[-104.75,38.8]]}}]};
assert.equal(routing.readAlternatives(data,from,to,geo).length,2);
assert.equal(routing.readAlternatives({code:'Ok',routes:[route(),route()]},from,to,geo).length,1);
assert.throws(()=>routing.readAlternatives({code:'NoRoute',routes:[]},from,to,geo),/No driving route/);
assert.throws(()=>routing.readAlternatives({code:'Ok',routes:[route([[-104.8,38.8],[0,0]])]},from,to,geo),/does not match/);
assert.throws(()=>routing.readAlternatives({code:'Ok',routes:[route([[-104.8,38.8],[123,0],[-104.75,38.8]])]},from,to,geo),/does not match/);
assert.throws(()=>routing.readAlternatives({code:'Ok',routes:[{...route(),duration:-1}]},from,to,geo),/incomplete/);
assert.throws(()=>routing.readAlternatives({code:'Ok',routes:[{...route(),geometry:{coordinates:coords}}]},from,to,geo),/incomplete/);
console.log('Driving alternative validation tests passed');
