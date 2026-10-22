/* Executable geometry regression tests; node scripts/test_route_geometry.js */
const assert=require('node:assert/strict');
const g=require('../route-geometry.js');
const lat=38.8,lon=-104.8;
const route=[[lat,lon],[lat,lon+0.02]];
const midpoint=[lat,lon+0.01];
const found=g.closestOnRoute(midpoint,route);
assert.ok(found.distance<1, 'point on segment must match');
assert.ok(Math.abs(found.progress-0.5)<0.001, 'travel fraction uses true lengths');
assert.ok(g.closestOnRoute([lat+0.02,lon+0.01],route).distance>1000);
const weird=[[lat,lon],[lat,lon+.0001],[lat,lon+.02]];
assert.ok(Math.abs(g.closestOnRoute(midpoint,weird).progress-0.5)<0.001,
  'dense vertex near origin cannot distort travel time');
const at=g.pointAtProgress(weird,0.5);
assert.ok(Math.abs(at[1]-(lon+.01))<0.00001);
const interstate=[[38.8,-104.8],[39,-104],[39,-100],[39,-95],[39,-85]];
const boxes=g.corridorBoxes(interstate);
assert.ok(boxes.length>=3&&boxes.length<32,'long trip segmented');
for(let i=0;i<=100;i++){
  const p=[39,-104+19*i/100];
  assert.ok(boxes.some(b=>b.south<=p[0]&&b.north>=p[0]&&
    b.west<=p[1]&&b.east>=p[1]),'all road segments lie in query coverage');
}
assert.throws(()=>g.corridorBoxes([[0,0],[1,1]]),/outside/);
assert.throws(()=>g.corridorBoxes([[39,-104],[39,0]],{maxBoxes:1}));
assert.throws(()=>g.closestOnRoute([99,0],route));
console.log('Route geometry tests passed: segment proximity, elapsed-distance timing, nationwide corridor completeness');
